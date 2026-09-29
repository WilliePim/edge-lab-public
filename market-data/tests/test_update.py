"""Aggiornamento incrementale con un fornitore finto: copertura registrata, coda dei lavori, sedute ripetute, eventi, riusi."""
import datetime as dt
import json
import urllib.parse

import pyarrow.parquet as pq
import pytest

from market_data.config import Limiti
from market_data.eodhd import download as D
from market_data.eodhd import update as U
from market_data.eodhd.client import Client
from market_data.quality import calendario as K
from market_data.store import normalize as N
from market_data.store.raw import Grezzo

CHIAVE = "0123456789abcd" + "." + "12345678"
TESTA = b"Date,Open,High,Low,Close,Adjusted_close,Volume\n"
SCARICATO = dt.datetime(2026, 9, 14, 12, tzinfo=dt.timezone.utc)
ZITTO = lambda *_: None  # noqa: E731


def test_sedute_mancanti():
    sedute = ["2026-09-14", "2026-09-15", "2026-09-16", "2026-09-17"]
    assert U.sedute_mancanti(dt.date(2026, 9, 15), sedute, dt.date(2026, 9, 16)) == ["2026-09-16"]
    assert U.sedute_mancanti(None, sedute, dt.date(2026, 9, 15)) == ["2026-09-14", "2026-09-15"]


def test_ticker_riusati():
    prima = [{"Code": "RE", "Isin": "US3", "Name": "Vecchia Spa"}, {"Code": "SAME", "Isin": "US1", "Name": "Uno Inc"},
             {"Code": "NOISIN", "Isin": "", "Name": "Pandora Media Inc"}, {"Code": "RINOMINATA", "Isin": "", "Name": "Acme Corp"},
             {"Code": "DUE", "Isin": "US7", "Name": "Due attiva"}]
    prima_delistati = [{"Code": "DUE", "Isin": "US6", "Name": "Due delistata"}]          # stesso codice nelle due liste
    dopo = [{"Code": "RE", "Isin": "US5", "Name": "Vecchia Spa"}, {"Code": "SAME", "Isin": "US1", "Name": "Uno Incorporated"},
            {"Code": "NOISIN", "Isin": "", "Name": "Everpure, Inc."}, {"Code": "RINOMINATA", "Isin": "", "Name": "ACME Corp."},
            {"Code": "NUOVO", "Isin": "US9", "Name": "Nuovo"}, {"Code": "DUE", "Isin": "US7", "Name": "Due attiva"}]
    assert [r["Code"] for r in U.ticker_riusati(prima, prima_delistati, dopo)] == ["NOISIN", "RE"]
    #  prima solo delistato con un altro ISIN, ora attivo: riuso
    assert [r["Code"] for r in U.ticker_riusati([], prima_delistati, dopo)] == ["DUE"]


def test_esito_seduta():
    assert U.esito_seduta(False, 100, 100, 0) == "fallito"
    assert U.esito_seduta(True, 60, 100, 0) == "ok"
    assert U.esito_seduta(True, 40, 100, 0) == "corto"
    assert U.esito_seduta(True, 0, None, 1) == "corto"
    assert U.esito_seduta(True, 40, 100, 2) == "corto accettato"      # terzo giorno diverso


def test_calendario_senza_sedute_nella_finestra():
    assert K.sessioni("US", "2026-09-19", "2026-09-20") == []                        # un fine settimana: vuoto, non errore


def barra(giorno, codice, close):
    return {"code": codice, "exchange_short_name": "US", "date": giorno, "open": close, "high": close, "low": close,
            "close": close, "adjusted_close": close, "volume": 10}


class Fornitore:
    """Liste nuove: NEW attivo senza serie, PREF di tipo non scaricato, RE riusato (ISIN cambiato), RE_old delistato nuovo.
    `risposte[(percorso, giorno o "")]` sostituisce la risposta; `dopo[percorso]` è chiamato dopo averla data."""

    def __init__(self):
        self.richieste = []
        self.risposte, self.dopo = {}, {}
        self.tipo_re, self.isin_re = "Common Stock", "US5"
        self.attivi_tolti, self.attivi_aggiunti, self.attivi_vuoti = set(), [], False

    def __call__(self, url):
        percorso, query = url.split("/api/", 1)[1].split("?", 1)
        percorso = urllib.parse.unquote(percorso)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(query).items() if k != "api_token"}
        self.richieste.append(percorso + "?" + urllib.parse.urlencode(sorted(q.items())))
        giorno = q.get("date", "")
        risposta = self.risposte.get((percorso + ("?" + q["type"] if "type" in q else ""), giorno)) or self.base(percorso, q, giorno)
        if percorso.startswith("exchange-symbol-list/") and q.get("delisted") != "1" and risposta[0] == 200:
            righe = [] if self.attivi_vuoti else [r for r in json.loads(risposta[1]) if r["Code"] not in self.attivi_tolti]
            risposta = (200, json.dumps(righe + self.attivi_aggiunti).encode())
        if percorso in self.dopo:
            self.dopo[percorso](q)
        return risposta

    def base(self, percorso, q, giorno):
        if percorso == "exchange-symbol-list/US":
            if q.get("delisted") == "1":
                return 200, json.dumps([{"Code": "RE_old", "Type": "Common Stock", "Isin": "US3", "Currency": "USD"}]).encode()
            return 200, json.dumps([{"Code": "OLD", "Type": "Common Stock", "Isin": "US1", "Currency": "USD"},
                                    {"Code": "KEEP", "Type": "Common Stock", "Isin": "US2", "Currency": "USD"},
                                    {"Code": "RE", "Type": self.tipo_re, "Isin": self.isin_re, "Currency": "USD"},
                                    {"Code": "NEW", "Type": "Common Stock", "Isin": "US4", "Currency": "USD"},
                                    {"Code": "PREF", "Type": "Preferred Stock", "Currency": "USD"}]).encode()
        if percorso == "eod-bulk-last-day/US":
            if q.get("type") == "splits":
                return 200, (json.dumps([{"code": "OLD", "exchange": "US", "date": giorno, "split": "2.000000/1.000000"}])
                             if giorno == "2026-09-15" else "[]").encode()
            if q.get("type") == "dividends":
                return 200, (json.dumps([{"code": "KEEP", "exchange": "US", "date": giorno, "dividend": "0.25", "currency": "USD",
                                          "unadjustedValue": "0.25"}]) if giorno == "2026-09-14" else "[]").encode()
            return 200, json.dumps([barra(giorno, c, 5.0) for c in ("OLD", "KEEP", "RE", "PREF")]).encode()
        serie = {"eod/OLD.US": b"2026-09-11,10,10,10,10,5,10\n2026-09-14,10,10,10,10,5,10\n2026-09-15,5,5,5,5,5,10\n",
                 "eod/KEEP.US": b"2026-09-11,4,4,4,4,3.8,7\n2026-09-14,4,4,4,4,4,7\n",
                 "eod/RE.US": b"2026-09-11,30,30,30,30,30,1\n2026-09-14,31,31,31,31,31,1\n",
                 "eod/RE_old.US": b"2020-01-02,2,2,2,2,2,1\n",
                 "eod/NEW.US": b"2026-09-14,1,1,1,1,1,1\n2026-09-15,1,1,1,1,1,1\n"}
        if percorso in serie:
            return 200, TESTA + serie[percorso]
        if percorso == "id-mapping":
            pagina = int(q["page[offset]"]) // 1000
            righe = {0: [{"symbol": "A.US", "isin": "US0A"}], 1: [{"symbol": "B.US", "isin": "US0B"}]}.get(pagina, [])
            return 200, json.dumps({"data": righe, "links": {"next": "x" if pagina == 0 else None}}).encode()
        return 200, b"[]"


def archivio_iniziale(tmp_path, dividendi_re=False):
    g = Grezzo(tmp_path)
    salva = lambda ep, par, corpo: g.salva(ep, par, 200, corpo, adesso=SCARICATO)  # noqa: E731
    salva("exchange-symbol-list/US", {"fmt": "json"}, json.dumps([
        {"Code": "OLD", "Type": "Common Stock", "Isin": "US1"}, {"Code": "KEEP", "Type": "Common Stock", "Isin": "US2"},
        {"Code": "RE", "Type": "Common Stock", "Isin": "US3", "Name": "Vecchia"}]).encode())
    salva("exchange-symbol-list/US", {"delisted": "1", "fmt": "json"}, b"[]")
    salva("eod/OLD.US", {"fmt": "csv"}, TESTA + b"2026-09-11,10,10,10,10,10,10\n")
    salva("eod/KEEP.US", {"fmt": "csv"}, TESTA + b"2026-09-11,4,4,4,4,4,7\n")
    vecchia = b"".join("2020-01-{:02d},2,2,2,2,2,1\n".format(g).encode() for g in range(2, 12))   # 10 barre della società vecchia
    salva("eod/RE.US", {"fmt": "csv"}, TESTA + vecchia + b"2026-09-11,2,2,2,2,2,1\n")
    if dividendi_re:
        salva("div/RE.US", {"fmt": "json"}, json.dumps([{"date": "2020-01-05", "value": 0.5, "unadjustedValue": 0.5,
                                                         "currency": "USD"}]).encode())
    salva("eod/SAMPLE.US", {"fmt": "json"}, b"[]")                     # campione JSON della fase 1: non sposta la copertura
    g.salva("eod/SAMPLE.US", {"fmt": "json"}, 200, b"[]", adesso=SCARICATO - dt.timedelta(days=30))
    salva("div/KEEP.US", {"fmt": "json"}, json.dumps([{"date": "2026-06-01", "value": 0.2, "unadjustedValue": 0.2,
                                                       "currency": "USD"}]).encode())
    N.Normalizzatore(tmp_path, log=ZITTO).per_titolo({"prezzi", "dividendi"}, None)


def aggiornamento(tmp_path, f, giorno):
    adesso = dt.datetime.combine(giorno, dt.time(12), tzinfo=dt.timezone.utc)
    client = Client(CHIAVE, tmp_path, Limiti(100_000, 1_000), trasporto=f, orologio=lambda: 0.0, dormi=ZITTO,
                    adesso=lambda: adesso)
    return U.Aggiornamento(tmp_path, client, Grezzo(tmp_path), log=ZITTO, adesso=lambda: adesso, dormi=ZITTO)


def prezzi(tmp_path):
    righe = pq.read_table(tmp_path / "eodhd/parquet/prezzi/exchange=US").to_pylist()
    return lambda c: [(str(r["date"]), r["adjusted_close"]) for r in righe if r["code"] == c]


def registro(tmp_path, tipo):
    righe = [json.loads(r) for r in (tmp_path / "eodhd/manifest/aggiornamenti.jsonl").read_text().splitlines()]
    return [r for r in righe if r["tipo"] == tipo]


def test_aggiornamento_completo(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    agg = aggiornamento(tmp_path, f, dt.date(2026, 9, 16))
    assert agg.copertura_iniziale("US") == dt.date(2026, 9, 13)
    piano = agg.piano(["US"], dt.date(2026, 9, 15))
    assert piano["US"]["sedute"] == ["2026-09-14", "2026-09-15"] and piano["US"]["chiamate_in_blocco"] == 600
    esito = agg.esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"] == {"sedute": 2, "sedute_coperte": 2, "sedute_non_coperte": [], "sedute_rimandate": 0, "titoli_nuovi": 1,
                           "delistati_nuovi": 1, "riusati": 1, "riusati_non_tenuti": 0, "eventi": 2, "lavori_chiusi": 5,
                           "lavori_aperti": 0, "falliti": 0}
    assert esito["extra"] == {"cambi_indici": 0, "tesoro": 0, "pagine_identificativi": 0, "identificativi_salvati": False,
                              "falliti": 0}
    per_titolo = sorted(r.split("?")[0] for r in f.richieste if not r.startswith(("eod-bulk", "exchange-symbol")))
    assert per_titolo == sorted(["eod/NEW.US", "div/NEW.US", "splits/NEW.US", "eod/RE_old.US", "div/RE_old.US", "splits/RE_old.US",
                                 "eod/RE.US", "div/RE.US", "splits/RE.US",                  # riusato
                                 "eod/OLD.US", "div/OLD.US", "splits/OLD.US",               # split del 15
                                 "eod/KEEP.US", "div/KEEP.US"])                             # dividendo del 14
    assert len([u for u in f.richieste if u.startswith("eod-bulk-last-day")]) == 6
    assert [(r["data"], r["esito"]) for r in registro(tmp_path, "seduta")] == [("2026-09-14", "ok"), ("2026-09-15", "ok")]

    #  seconda esecuzione: sedute coperte, nessun lavoro ripetuto, solo le liste
    f.richieste.clear()
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert sorted(r.split("?")[0] for r in f.richieste) == ["exchange-symbol-list/US", "exchange-symbol-list/US"]
    assert esito["US"]["riusati"] == 0 and esito["US"]["sedute"] == 0 and esito["US"]["lavori_chiusi"] == 0

    U.ricostruisci(tmp_path, ["US"], log=ZITTO)
    serie = prezzi(tmp_path)
    assert serie("OLD") == [("2026-09-11", 5.0), ("2026-09-14", 5.0), ("2026-09-15", 5.0)]     # riscaricata dopo lo split
    assert serie("KEEP") == [("2026-09-11", 3.8), ("2026-09-14", 4.0), ("2026-09-15", 5.0)]    # riscaricata + blocco del 15
    assert serie("RE") == [("2026-09-11", 30.0), ("2026-09-14", 31.0), ("2026-09-15", 5.0)]    # società nuova, più corta ma usata
    assert serie("RE_old") == [("2020-01-02", 2.0)]
    assert serie("NEW") == [("2026-09-14", 1.0), ("2026-09-15", 1.0)]
    assert serie("PREF") == []                                                                 # tipo non scaricato: fuori
    div = pq.read_table(tmp_path / "eodhd/parquet/dividendi/exchange=US").to_pylist()
    assert [(r["code"], str(r["date"]), r["value"]) for r in div] == [("KEEP", "2026-06-01", 0.2), ("KEEP", "2026-09-14", 0.25)]
    assert (tmp_path / "eodhd/qualita/qualita.json").exists() and (tmp_path / "catalog.duckdb").exists()


def test_interruzione_dopo_le_liste_non_perde_i_lavori(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    stop = tmp_path / "eodhd/manifest/STOP"
    f.dopo["exchange-symbol-list/US"] = lambda q: stop.write_text("") if q.get("delisted") == "1" else None
    with pytest.raises(D.Fermo):
        aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert not [u for u in f.richieste if u.startswith("eod/")]                  # fermo prima di scaricare
    stop.unlink()
    f.dopo.clear()
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["riusati"] == 0 and esito["US"]["lavori_aperti"] == 0     # il confronto non si ripete, la coda sì
    assert {"eod/RE.US", "eod/RE_old.US", "eod/NEW.US"} <= {r.split("?")[0] for r in f.richieste}
    U.ricostruisci(tmp_path, ["US"], log=ZITTO, controlli=False)
    serie = prezzi(tmp_path)
    assert serie("RE")[0] == ("2026-09-11", 30.0) and serie("RE_old") == [("2020-01-02", 2.0)]


def test_lavori_falliti_restano_in_coda(tmp_path):
    archivio_iniziale(tmp_path, dividendi_re=True)
    f = Fornitore()
    for percorso in ("eod/KEEP.US", "eod/RE_old.US", "div/RE.US"):
        f.risposte[(percorso, "")] = (500, b"errore")
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["falliti"] == 3 and esito["US"]["lavori_aperti"] == 3     # dividendo KEEP, RE_old, riuso RE
    U.ricostruisci(tmp_path, ["US"], log=ZITTO, controlli=False)
    div = pq.read_table(tmp_path / "eodhd/parquet/dividendi/exchange=US").to_pylist()
    assert "RE" not in {r["code"] for r in div}                                  # dividendi della società vecchia: fuori
    assert prezzi(tmp_path)("RE")[0] == ("2026-09-11", 30.0)                     # prezzi della nuova già arrivati
    #  il giorno dopo il fornitore risponde: si riscarica solo ciò che manca
    f.risposte.clear()
    f.richieste.clear()
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 17)).esegui(["US"], dt.date(2026, 9, 15))
    per_titolo = sorted(r.split("?")[0] for r in f.richieste if not r.startswith(("eod-bulk", "exchange-symbol")))
    assert per_titolo == ["div/KEEP.US", "div/RE.US", "div/RE_old.US", "eod/KEEP.US", "eod/RE_old.US", "splits/RE.US",
                          "splits/RE_old.US"]    # le tabelle già riuscite no (eod/RE); quelle dopo un errore aspettavano
    assert esito["US"]["lavori_aperti"] == 0 and esito["US"]["falliti"] == 0
    U.ricostruisci(tmp_path, ["US"], log=ZITTO, controlli=False)
    assert prezzi(tmp_path)("KEEP")[0] == ("2026-09-11", 3.8) and prezzi(tmp_path)("RE_old") == [("2020-01-02", 2.0)]


def test_interruzione_durante_il_riuso(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    stop = tmp_path / "eodhd/manifest/STOP"
    f.dopo["eod/RE.US"] = lambda q: stop.write_text("")
    with pytest.raises(D.Fermo):
        aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    U.ricostruisci(tmp_path, ["US"], log=ZITTO, controlli=False)
    assert prezzi(tmp_path)("RE") == [("2026-09-11", 30.0), ("2026-09-14", 31.0)]  # la nuova, anche se più corta
    stop.unlink()
    f.dopo.clear()
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["lavori_aperti"] == 0


def test_riuso_da_un_tipo_non_tenuto(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    f.tipo_re = "FUND"
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["riusati"] == 0 and esito["US"]["riusati_non_tenuti"] == 1
    assert "eod/RE.US" not in {r.split("?")[0] for r in f.richieste}
    U.ricostruisci(tmp_path, ["US"], log=ZITTO, controlli=False)
    assert prezzi(tmp_path)("RE") == []                                          # né la vecchia, né il fondo dal blocco
    #  di nuovo: nessun nuovo segno, nessuna chiamata per RE
    aggiornamento(tmp_path, f, dt.date(2026, 9, 17)).esegui(["US"], dt.date(2026, 9, 15))
    assert len(registro(tmp_path, "riuso")) == 1


def bulk_distinti(f):
    return sorted({u for u in f.richieste if u.startswith("eod-bulk-last-day")})


def test_sedute_fallite_o_corte_ripetute_poi_accettate(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    for tipo in ("", "?splits", "?dividends"):
        f.risposte[("eod-bulk-last-day/US" + tipo, "2026-09-14")] = (500, b"errore")
    f.risposte[("eod-bulk-last-day/US", "2026-09-15")] = (200, b"[]")
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["sedute_non_coperte"] == ["2026-09-14"] and esito["US"]["sedute_rimandate"] == 1   # il 15 aspetta
    assert bulk_distinti(f) == ["eod-bulk-last-day/US?date=2026-09-14&fmt=json",
                                "eod-bulk-last-day/US?date=2026-09-14&fmt=json&type=dividends",
                                "eod-bulk-last-day/US?date=2026-09-14&fmt=json&type=splits"]
    #  il giorno dopo il 14 risponde; il 15 è vuoto (primo giorno corto)
    for tipo in ("", "?splits", "?dividends"):
        del f.risposte[("eod-bulk-last-day/US" + tipo, "2026-09-14")]
    agg = aggiornamento(tmp_path, f, dt.date(2026, 9, 17))
    assert agg.piano(["US"], dt.date(2026, 9, 15))["US"]["sedute"] == ["2026-09-14", "2026-09-15"]
    esito = agg.esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["sedute_non_coperte"] == ["2026-09-15"] and esito["US"]["eventi"] == 2
    assert agg.coperto_fino_a("US", ["2026-09-14", "2026-09-15"]) == dt.date(2026, 9, 14)
    #  stesso giorno di nuovo: solo i prezzi del 15, e il tentativo non conta come giorno diverso
    f.richieste.clear()
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 17)).esegui(["US"], dt.date(2026, 9, 15))
    assert bulk_distinti(f) == ["eod-bulk-last-day/US?date=2026-09-15&fmt=json"]
    assert esito["US"]["sedute_non_coperte"] == ["2026-09-15"]
    #  secondo giorno diverso: ancora corta; terzo: accettata e coperta
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 18)).esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["sedute_non_coperte"] == ["2026-09-15"]
    agg = aggiornamento(tmp_path, f, dt.date(2026, 9, 19))
    esito = agg.esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["sedute_non_coperte"] == [] and esito["US"]["sedute_coperte"] == 1
    assert agg.coperto_fino_a("US", ["2026-09-14", "2026-09-15"]) == dt.date(2026, 9, 15)


def test_blocco_che_non_e_una_lista(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    f.risposte[("eod-bulk-last-day/US?splits", "2026-09-15")] = (200, b'{"message": "limite"}')
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["sedute_non_coperte"] == ["2026-09-15"]
    assert registro(tmp_path, "seduta")[-1]["stati"] == {"prezzi": 200, "split": "non lista", "dividendi": 200}
    U.ricostruisci(tmp_path, ["US"], log=ZITTO, controlli=False)                 # il file rotto non ferma la normalizzazione
    del f.risposte[("eod-bulk-last-day/US?splits", "2026-09-15")]
    f.richieste.clear()
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 17)).esegui(["US"], dt.date(2026, 9, 15))
    assert [u for u in f.richieste if u.startswith("eod-bulk")] == ["eod-bulk-last-day/US?date=2026-09-15&fmt=json&type=splits"]
    assert esito["US"]["sedute_coperte"] == 1 and esito["US"]["eventi"] == 1


def test_righe_con_un_altra_data_non_contano(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    f.risposte[("eod-bulk-last-day/US", "2026-09-15")] = (200, json.dumps([barra("2026-09-14", c, 5.0) for c in ("OLD", "KEEP", "RE")]).encode())
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["sedute_non_coperte"] == ["2026-09-15"]


def test_seduta_corta_rispetto_alla_mediana(tmp_path):
    agg = aggiornamento(tmp_path, Fornitore(), dt.date(2026, 9, 16))
    for giorno in ["2026-09-07", "2026-09-08", "2026-09-09"]:
        agg.annota({"tipo": "seduta", "borsa": "US", "data": giorno, "esito": "ok", "righe": 10, "righe_nostre": 8})
    s = agg.seduta("US", "2026-09-14", {"OLD", "KEEP", "RE"}, attivi_con_serie=3)
    assert (s["righe_nostre"], s["riferimento"], s["esito"]) == (3, 8, "corto")               # 3 sotto metà di 8
    s = agg.seduta("US", "2026-09-15", {"OLD", "KEEP", "RE", "PREF", "A", "B"}, attivi_con_serie=3)
    assert (s["righe_nostre"], s["esito"]) == (4, "ok")


def test_identificativi_solo_da_una_mappatura_completa(tmp_path):
    g = Grezzo(tmp_path)
    vecchie = {0: ["A.US"], 1: ["B.US"], 2: ["GONE.US"]}
    for pagina, simboli in vecchie.items():
        c = D.compito_identificativi(pagina)
        g.salva(c.endpoint, c.parametri(), 200, json.dumps({"data": [{"symbol": s, "isin": "VECCHIO"} for s in simboli],
                                                            "links": {"next": "x" if pagina < 2 else None}}).encode(), adesso=SCARICATO)
    N.Normalizzatore(tmp_path, log=ZITTO).identificativi()
    leggi = lambda: sorted((r["symbol"], r["isin"]) for r in pq.read_table(tmp_path / "eodhd/parquet/identificativi/exchange=US").to_pylist())  # noqa: E731
    assert leggi() == [("A.US", "VECCHIO"), ("B.US", "VECCHIO"), ("GONE.US", "VECCHIO")]
    #  mappatura nuova interrotta alla pagina 1: non si salva
    f = Fornitore()
    f.risposte[("id-mapping", "")] = None
    f.dopo["id-mapping"] = lambda q: f.risposte.__setitem__(("id-mapping", ""), (500, b"errore"))
    conti = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).extra(dt.date(2026, 9, 15), identificativi=True)
    assert conti["identificativi_salvati"] is False and conti["falliti"] == 1
    N.Normalizzatore(tmp_path, log=ZITTO).identificativi()
    assert leggi() == [("A.US", "VECCHIO"), ("B.US", "VECCHIO"), ("GONE.US", "VECCHIO")]
    #  mappatura nuova completa in 2 pagine: vale solo lei, la vecchia pagina 2 non resta
    f = Fornitore()
    conti = aggiornamento(tmp_path, f, dt.date(2026, 9, 17)).extra(dt.date(2026, 9, 15), identificativi=True)
    assert conti["identificativi_salvati"] is True and conti["pagine_identificativi"] == 2
    N.Normalizzatore(tmp_path, log=ZITTO).identificativi()
    assert leggi() == [("A.US", "US0A"), ("B.US", "US0B")]


def test_barre_in_blocco_aggiunte_dopo_la_serie(tmp_path):
    #  Copia pubblica: `adesso` fisso, altrimenti la cartella e la data di scaricamento seguono l'orologio e il test
    #  cambia esito col passare dei giorni (differenza dichiarata rispetto al repo privato; il codice e' invariato).
    adesso = dt.datetime(2026, 9, 15, tzinfo=dt.timezone.utc)
    g = Grezzo(tmp_path)
    g.salva("exchange-symbol-list/US", {"fmt": "json"}, 200, json.dumps([{"Code": "KEEP", "Type": "Common Stock"},
                                                                          {"Code": "ONLYBULK", "Type": "ETF"}]).encode(),
            adesso=adesso)
    g.salva("eod/KEEP.US", {"fmt": "csv"}, 200, TESTA + b"2026-09-11,4,4,4,4,4,7\n", adesso=adesso)
    bulk = [{"code": c, "date": d, "open": 1, "high": 1, "low": 1, "close": x, "adjusted_close": x, "volume": 3}
            for c, d, x in (("KEEP", "2026-09-10", 99.0), ("KEEP", "2026-09-14", 4.5), ("ONLYBULK", "2026-09-14", 20.0),
                            ("NONLISTATO", "2026-09-14", 7.0))]
    g.salva("eod-bulk-last-day/US", {"date": "2026-09-14", "fmt": "json"}, 200, json.dumps(bulk).encode(),
            adesso=adesso)
    N.Normalizzatore(tmp_path, log=ZITTO).per_titolo({"prezzi"}, None)
    righe = pq.read_table(tmp_path / "eodhd/parquet/prezzi/exchange=US").to_pylist()
    assert [(r["code"], str(r["date"]), r["close"]) for r in righe] == [
        ("KEEP", "2026-09-11", 4.0), ("KEEP", "2026-09-14", 4.5)]    # prima della serie: ignorata; solo nel blocco: fuori


#  ---- seconda revisione

def lavori_aperti(tmp_path):
    chiusi = {(r["borsa"], r["codice"], r["motivo"], r["data"]) for r in registro(tmp_path, "fatto")}
    return sorted((r["codice"], r["motivo"]) for r in registro(tmp_path, "lavoro")
                  if (r["borsa"], r["codice"], r["motivo"], r["data"]) not in chiusi)


def test_riuso_con_404_resta_aperto_e_poi_arriva(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    f.risposte[("eod/RE.US", "")] = (404, b"Ticker Not Found.")
    aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert ("RE", "riuso") in lavori_aperti(tmp_path)
    assert not [v for v in Grezzo(tmp_path)._storia.values() for x in v if x["endpoint"] == "eod/RE.US" and x["stato"] != 200]
    f.risposte.clear()
    aggiornamento(tmp_path, f, dt.date(2026, 9, 17)).esegui(["US"], dt.date(2026, 9, 15))
    assert lavori_aperti(tmp_path) == []
    U.ricostruisci(tmp_path, ["US"], log=ZITTO, controlli=False)
    assert prezzi(tmp_path)("RE") == [("2026-09-11", 30.0), ("2026-09-14", 31.0), ("2026-09-15", 5.0)]


def test_404_in_5_giorni_chiude_e_il_nuovo_torna_dopo_30(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    for tabella in ("eod", "div", "splits"):
        f.risposte[(tabella + "/NEW.US", "")] = (404, b"Ticker Not Found.")
    for giorno in range(16, 21):
        aggiornamento(tmp_path, f, dt.date(2026, 9, giorno)).esegui(["US"], dt.date(2026, 9, 15), identificativi=False)
        assert (("NEW", "nuovo") in lavori_aperti(tmp_path)) == (giorno < 20)
    assert [r["esito"] for r in registro(tmp_path, "fatto") if r["codice"] == "NEW"] == ["non disponibile"]
    manifest = (tmp_path / "eodhd/manifest/grezzo.jsonl").read_text()
    assert "NEW.US" not in manifest                                                  # le 404 non vanno nel grezzo
    f.richieste.clear()
    aggiornamento(tmp_path, f, dt.date(2026, 10, 10)).esegui(["US"], dt.date(2026, 9, 15), identificativi=False)
    assert not [u for u in f.richieste if "NEW.US" in u]                             # 20 giorni: non ancora
    aggiornamento(tmp_path, f, dt.date(2026, 10, 21)).esegui(["US"], dt.date(2026, 9, 15), identificativi=False)
    assert ("NEW", "nuovo") in lavori_aperti(tmp_path)                               # 31 giorni: di nuovo in coda


def test_nuovo_uscito_dalle_liste_si_chiude(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    for tabella in ("eod", "div", "splits"):
        f.risposte[(tabella + "/NEW.US", "")] = (404, b"Ticker Not Found.")
    aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert ("NEW", "nuovo") in lavori_aperti(tmp_path)
    f.attivi_tolti = {"NEW"}
    f.richieste.clear()
    aggiornamento(tmp_path, f, dt.date(2026, 9, 17)).esegui(["US"], dt.date(2026, 9, 15))
    assert [r["esito"] for r in registro(tmp_path, "fatto") if r["codice"] == "NEW"] == ["uscito dalle liste"]
    assert not [u for u in f.richieste if "NEW.US" in u]


def test_dividendi_e_split_della_societa_vecchia_non_passano_alla_nuova(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    f.isin_re = "US3"                                                                # primo giro: ancora la società vecchia
    f.risposte[("eod-bulk-last-day/US?dividends", "2026-09-14")] = (200, json.dumps(
        [{"code": "RE", "exchange": "US", "date": "2026-09-14", "dividend": "0.50", "currency": "USD"}]).encode())
    f.risposte[("eod-bulk-last-day/US?splits", "2026-09-15")] = (200, json.dumps(
        [{"code": "RE", "exchange": "US", "date": "2026-09-15", "split": "1.000000/10.000000"}]).encode())
    aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    f.isin_re = "US5"                                                                # secondo giro: RE riusato
    aggiornamento(tmp_path, f, dt.date(2026, 9, 18)).esegui(["US"], dt.date(2026, 9, 15))
    assert len(registro(tmp_path, "riuso")) == 1
    U.ricostruisci(tmp_path, ["US"], log=ZITTO, controlli=False)
    for tabella in ("dividendi", "split"):
        righe = pq.read_table(tmp_path / "eodhd/parquet/{}/exchange=US".format(tabella)).to_pylist()
        assert "RE" not in {r["code"] for r in righe}, tabella


def test_riuso_non_tenuto_e_un_dividendo_non_riportano_la_serie(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    f.tipo_re = "FUND"
    f.risposte[("eod-bulk-last-day/US?dividends", "2026-09-15")] = (200, json.dumps(
        [{"code": "RE", "exchange": "US", "date": "2026-09-15", "dividend": "0.10", "currency": "USD"}]).encode())
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["riusati_non_tenuti"] == 1
    assert not [u for u in f.richieste if u.startswith(("eod/RE.US", "div/RE.US"))]
    U.ricostruisci(tmp_path, ["US"], log=ZITTO, controlli=False)
    assert prezzi(tmp_path)("RE") == []


def test_titoli_che_falliscono_sempre_non_fermano_l_aggiornamento(tmp_path):
    archivio_iniziale(tmp_path)
    rotti = ["ROTTO{}".format(i) for i in range(12)]

    class Rotto(Fornitore):
        def base(self, percorso, q, giorno):
            if percorso == "exchange-symbol-list/US" and q.get("delisted") != "1":
                righe = json.loads(super().base(percorso, q, giorno)[1])
                righe += [{"Code": c, "Type": "Common Stock", "Isin": "US9" + c, "Currency": "USD"} for c in rotti]
                return 200, json.dumps(righe).encode()
            if "/" in percorso and percorso.split("/")[1].rsplit(".", 1)[0] in rotti:
                return 503, b"Service Unavailable"
            return super().base(percorso, q, giorno)

    f = Rotto()
    pause = []
    adesso = dt.datetime(2026, 9, 16, 12, tzinfo=dt.timezone.utc)
    client = Client(CHIAVE, tmp_path, Limiti(100_000, 1_000), trasporto=f, orologio=lambda: 0.0, dormi=ZITTO, adesso=lambda: adesso)
    agg = U.Aggiornamento(tmp_path, client, Grezzo(tmp_path), log=ZITTO, adesso=lambda: adesso, dormi=pause.append)
    esito = agg.esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["sedute_coperte"] == 2 and pause == []                        # nessuna pausa da un minuto per la coda
    assert esito["US"]["falliti"] == 12                                             # una chiamata per titolo rotto, non tre
    assert sum(1 for u in f.richieste if u.startswith("user")) == 1                 # dopo 10 di fila: il fornitore risponde
    assert len([a for a in lavori_aperti(tmp_path) if a[0].startswith("ROTTO")]) == 12


def test_fornitore_giu_ferma_l_aggiornamento(tmp_path):
    archivio_iniziale(tmp_path)

    class Giu(Fornitore):
        def base(self, percorso, q, giorno):
            if percorso.startswith("exchange-symbol-list"):
                return super().base(percorso, q, giorno)
            return 503, b"giu"

    f = Giu()
    f.attivi_aggiunti = [{"Code": "T{}".format(i), "Type": "Common Stock", "Isin": "US8{}".format(i)} for i in range(12)]
    with pytest.raises(D.Fermo, match="non risponde"):
        aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert lavori_aperti(tmp_path)                                                   # la coda resta per la volta dopo


def test_lista_vuota_o_dimezzata_non_diventa_il_confronto(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()
    f.attivi_vuoti = True
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["falliti"] >= 1 and esito["US"]["titoli_nuovi"] == 0
    f.attivi_vuoti = False
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 17)).esegui(["US"], dt.date(2026, 9, 15))
    assert esito["US"]["riusati"] == 1                                               # confronto con le liste vere di prima


def test_francoforte_dopo_xetra_con_le_liste_nuove(tmp_path):
    g = Grezzo(tmp_path)
    salva = lambda ep, par, corpo: g.salva(ep, par, 200, corpo, adesso=SCARICATO)  # noqa: E731
    for borsa in ("XETRA", "F"):
        salva("exchange-symbol-list/" + borsa, {"fmt": "json"}, json.dumps(
            [{"Code": "VEC", "Type": "Common Stock", "Isin": "DE000VEC"}]).encode())
        salva("exchange-symbol-list/" + borsa, {"delisted": "1", "fmt": "json"}, b"[]")
        salva("eod/VEC." + borsa, {"fmt": "csv"}, TESTA + b"2026-09-11,1,1,1,1,1,1\n")
    nuova = [{"Code": "VEC", "Type": "Common Stock", "Isin": "DE000VEC"}, {"Code": "NUO", "Type": "Common Stock", "Isin": "DE000NUO"}]

    class Tedesco(Fornitore):
        def base(self, percorso, q, giorno):
            if percorso.startswith("exchange-symbol-list/"):
                return 200, (b"[]" if q.get("delisted") == "1" else json.dumps(nuova).encode())
            return 200, b"[]"

    f = Tedesco()
    esito = aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["F", "XETRA"], dt.date(2026, 9, 15), identificativi=False)
    assert esito["XETRA"]["titoli_nuovi"] == 1 and esito["F"]["titoli_nuovi"] == 0  # NUO è già su Xetra
    assert "eod/NUO.F" not in {u.split("?")[0] for u in f.richieste}


def test_primo_salvataggio_identificativi_interrotto(tmp_path):
    g = Grezzo(tmp_path)
    for pagina, simbolo in ((0, "A.US"), (1, "GONE.US")):
        c = D.compito_identificativi(pagina)
        g.salva(c.endpoint, c.parametri(), 200, json.dumps({"data": [{"symbol": simbolo, "isin": "VECCHIO"}],
                                                            "links": {"next": "x" if pagina == 0 else None}}).encode(), adesso=SCARICATO)
    agg = aggiornamento(tmp_path, Fornitore(), dt.date(2026, 9, 16))
    agg.annota({"tipo": "identificativi", "stato": "salvataggio"})
    c = D.compito_identificativi(0)                                                  # una sola pagina nuova salvata, poi il crollo
    g2 = Grezzo(tmp_path)
    g2.salva(c.endpoint, c.parametri(), 200, json.dumps({"data": [{"symbol": "A.US", "isin": "NUOVO"}], "links": {"next": "x"}}).encode(),
             adesso=dt.datetime(2026, 9, 16, 12, 0, 5, tzinfo=dt.timezone.utc))
    N.Normalizzatore(tmp_path, log=ZITTO).identificativi()
    righe = pq.read_table(tmp_path / "eodhd/parquet/identificativi/exchange=US").to_pylist()
    assert sorted((r["symbol"], r["isin"]) for r in righe) == [("A.US", "VECCHIO"), ("GONE.US", "VECCHIO")]


def test_evento_del_giorno_prima_su_un_codice_riusato(tmp_path):
    archivio_iniziale(tmp_path)
    f = Fornitore()                                                                  # riuso di RE scoperto il 16
    f.risposte[("eod-bulk-last-day/US?splits", "2026-09-15")] = (200, json.dumps(
        [{"code": "RE", "exchange": "US", "date": "2026-09-15", "split": "1.000000/10.000000"}]).encode())
    aggiornamento(tmp_path, f, dt.date(2026, 9, 16)).esegui(["US"], dt.date(2026, 9, 15))
    U.ricostruisci(tmp_path, ["US"], log=ZITTO, controlli=False)
    righe = pq.read_table(tmp_path / "eodhd/parquet/split/exchange=US").to_pylist()
    assert "RE" not in {r["code"] for r in righe}                                    # il giorno prima era dell'altra società
