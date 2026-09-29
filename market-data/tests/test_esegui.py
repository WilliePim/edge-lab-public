"""Fase 4 su un archivio finto, con EDGAR e Yahoo finti (nessuna chiamata reale)."""
import datetime as dt
import json

import pytest

from market_data import api
from market_data.quality import calendario as K
from market_data.quality import esegui as X
from market_data.quality import esterni as E
from market_data.store import identity
from market_data.store import normalize as N
from market_data.store.raw import Grezzo

TESTA = "Date,Open,High,Low,Close,Adjusted_close,Volume\n"


def csv_da(prezzi, volumi, inizio=dt.date(2019, 1, 2)):
    giorni, d = [], inizio
    while len(giorni) < len(prezzi):
        if d.weekday() < 5:
            giorni.append(d)
        d += dt.timedelta(days=1)
    righe = ["{},{p},{p},{p},{p},{p},{v}".format(g.isoformat(), p=p, v=v) for g, p, v in zip(giorni, prezzi, volumi)]
    return (TESTA + "\n".join(righe) + "\n").encode(), giorni


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path))
    g = Grezzo(tmp_path)
    attivi = [{"Code": "JMP", "Name": "Jump Corp", "Exchange": "NASDAQ", "Currency": "USD", "Type": "Common Stock", "Isin": "US0000000001"},
              {"Code": "FLAT", "Name": "Flat Inc", "Exchange": "NYSE", "Currency": "USD", "Type": "Common Stock", "Isin": "US0000000002"}]
    delistati = [{"Code": "GONE", "Name": "Gone Holdings Inc", "Exchange": "NYSE", "Currency": "USD", "Type": "Common Stock", "Isin": "US0000000003"}]
    g.salva("exchange-symbol-list/US", {"fmt": "json"}, 200, json.dumps(attivi).encode())
    g.salva("exchange-symbol-list/US", {"delisted": "1", "fmt": "json"}, 200, json.dumps(delistati).encode())
    corpo, giorni_jmp = csv_da([50.0] * 30 + [5.1] * 30, [1000] * 30 + [11000] * 30)
    g.salva("eod/JMP.US", {"fmt": "csv"}, 200, corpo)
    corpo, _ = csv_da([12.0] * 10 + [12.5] * 25 + [13.0] * 5, [500] * 10 + [0] * 25 + [700] * 5)
    g.salva("eod/FLAT.US", {"fmt": "csv"}, 200, corpo)
    corpo, giorni_gone = csv_da([8.0] * 40, [300] * 40)
    g.salva("eod/GONE.US", {"fmt": "csv"}, 200, corpo)
    for c in ("JMP", "FLAT", "GONE"):
        g.salva("splits/{}.US".format(c), {"fmt": "json"}, 200, b"[]")
    g.salva("id-mapping", {"filter[ex]": "US", "fmt": "json"}, 200, json.dumps({"data": [
        {"symbol": "JMP.US", "cik": "0000000111"}, {"symbol": "GONE.US", "cik": "0000000222"},
        {"symbol": "FLAT.US", "cik": "0000000333"}]}).encode())
    n = N.Normalizzatore(tmp_path, log=lambda *_: None)
    n.per_titolo({"prezzi", "split"}, None)
    n.identificativi()
    identity.Anagrafica(tmp_path, log=lambda *_: None).costruisci(["US"])
    K.scrivi_calendario(tmp_path, ["US"], fine="2019-12-31")
    api.refresh()
    yield tmp_path, giorni_jmp, giorni_gone
    api.refresh()


def edgar_finto(tmp_path, giorno_salto, ultima_gone):
    risposte = {
        E.SEC.format(111): {"name": "JUMP CORP", "filings": {"recent": {
            "filingDate": [(giorno_salto - dt.timedelta(days=5)).isoformat(), "2000-03-01"], "form": ["8-K", "8-A12B"],
            "items": ["5.03", ""], "accessionNumber": ["0000000111-19-000001", "0000000111-00-000001"],
            "primaryDocument": ["k.htm", "a.htm"]}}},
        E.SEC.format(222): {"name": "GONE HOLDINGS, INC.", "formerNames": [], "filings": {"recent": {
            "filingDate": [(ultima_gone + dt.timedelta(days=1)).isoformat()], "form": ["25-NSE"], "items": [""],
            "accessionNumber": ["0000000222-19-000009"], "primaryDocument": ["f25.htm"]}}},
        E.SEC.format(333): {"name": "FLAT INC", "filings": {"recent": {
            "filingDate": ["2018-01-10", "2019-03-01"], "form": ["S-1", "424B4"], "items": ["", ""],
            "accessionNumber": ["x-1", "x-2"], "primaryDocument": ["s1.htm", "p.htm"]}}},
    }

    def trasporto(url):
        if url in risposte:
            return 200, json.dumps(risposte[url]).encode()
        if url.endswith("/k.htm"):
            return 200, b"<p>The Board approved a 10-for-1 stock split effective at market open.</p>"
        return 404, b""

    return E.Edgar(tmp_path, user_agent="Prova prova@example.com", trasporto=trasporto, dormi=lambda s: None)


def test_controlli_completi(archivio):
    tmp_path, giorni_jmp, giorni_gone = archivio
    salto = giorni_jmp[30]

    def yahoo_finto(simboli, inizio):
        con = api._con()
        out = {}
        for s in simboli:
            righe = con.execute("SELECT strftime(date, '%Y-%m-%d'), close, adjusted_close FROM prezzi WHERE code = ?", [s]).fetchall()
            out[s] = {d: {"close": c * (1.02 if s == "JMP" and d == "2019-01-02" else 1.0), "adj": a * 1.03}      # FLAT: fuori campione
                      for d, c, a in righe}
        return out

    c = X.Controlli(tmp_path, log=lambda *_: None, edgar=edgar_finto(tmp_path, salto, giorni_gone[-1]), yahoo=yahoo_finto)
    monkey_n = X.N_DELISTATI
    out = c.esegui(["US"])
    us = out["borse"]["US"]
    assert us["salti_sospetti"]["salti"] == 1 and us["salti_sospetti"]["per_fascia"] == {"sopra 1": 1}
    assert us["salti_sospetti"]["volume"] == {"coerente": 1}
    assert us["volume_zero"] == {"sequenze": 1, "titoli": 1, "sedute": 25}
    assert us["duplicati"]["righe"] == 0 and us["prezzi_impossibili"]["chiusure_non_positive"] == 0
    assert out["salti_sopra_1_edgar"]["split_veri"] == 1 and out["salti_sopra_1_edgar"]["quota_split_veri"] == 1.0
    assert "10-for-1 stock split" in out["salti_sopra_1_edgar"]["salti"][0]["estratto"]
    dl = out["delistati_usa_edgar"]
    assert dl["campione"] == 1 and dl["coerenti"] == 1 and dl["titoli"][0]["fonte_fine"] == "Form 25/15"
    pq_ = out["prima_della_quotazione"]
    assert pq_["segnalati"] == 1 and pq_["esempi"][0]["code"] == "FLAT"           # barre dal 2019-01-02, 424B4 il 2019-03-01: oltre 30 giorni
    y = out["yahoo"]["USA"]
    assert y["date_confrontate"] > 0 and 0 < y["quota_chiusure_oltre_1pct"] < 0.1       # una sola chiusura diversa
    assert y["quota_rettificate_oltre_1pct"] == 1.0 and y["scarto_mediano_rettificate_per_titolo"] == pytest.approx(0.0291, abs=1e-3)
    api.refresh()
    flags = api.flags()
    assert set(flags["controllo"]) == {"salto_sospetto", "volume_zero", "prima_della_quotazione"}
    puliti = api.prices("JMP.US")
    assert str(puliti["date"].iloc[0])[:10] == salto.isoformat()                 # prima del salto: escluso
    assert len(api.prices("JMP.US", clean=False)) == 60
    assert X.N_DELISTATI == monkey_n


def test_rapporti_nel_testo_e_ipo():
    assert E.rapporti_nel_testo("approved a 1-for-10 reverse stock split") == [10.0]                # prezzo x10
    assert E.rapporti_nel_testo("a two-for-one stock split of our common stock") == [0.5]           # prezzo /2
    assert E.rapporti_nel_testo("shares exchanged on a one-for-one basis in the merger") == []      # nessuno split
    assert E.rapporti_nel_testo("options adjusted for any stock split or recapitalization") == []   # nessun rapporto
    ipo = [("2018-01-10", "S-1", "", "a", "d"), ("2019-03-01", "424B4", "", "b", "d"), ("2019-06-01", "10-Q", "", "c", "d")]
    assert E.data_ipo(ipo) == "2019-03-01"
    gia_pubblica = [("2009-03-01", "10-K", "", "z", "d")] + ipo                                     # quotata prima (OTC)
    assert E.data_ipo(gia_pubblica) is None
    successore = [("2017-05-01", "8-K12B", "", "y", "d")] + ipo
    assert E.data_ipo(successore) is None
    assert E.data_ipo([("2019-03-01", "424B4", "", "b", "d")]) is None                            # senza registrazione


def test_edgar_non_leggibile_non_e_nessun_deposito(tmp_path):
    ed = E.Edgar(tmp_path, user_agent="Prova prova@example.com", trasporto=lambda url: (503, b""), dormi=lambda s: None)
    assert ed.depositi(123) == (None, None)
    esito = ed.prove_split(123, dt.date(2020, 1, 2), 0.1)
    assert esito["esito"].startswith("non verificabile")


def test_giro_senza_fonti_esterne_conserva_edgar_e_yahoo(tmp_path):
    percorso = tmp_path / "qualita.json"
    assert X.sezioni_esterne_precedenti(percorso) == {}
    percorso.write_text(json.dumps({"eseguito": "2026-09-21T10:00:00+00:00", "borse": {}, "yahoo": {"US": 1},
                                    "salti_sopra_1_edgar": {"quota": 0.7}}), encoding="utf-8")
    vecchie = X.sezioni_esterne_precedenti(percorso)
    assert vecchie == {"yahoo": {"US": 1}, "salti_sopra_1_edgar": {"quota": 0.7}, "fonti_esterne_del": "2026-09-21T10:00:00+00:00"}
    percorso.write_text(json.dumps(dict(vecchie, eseguito="2026-09-25T10:00:00+00:00")), encoding="utf-8")
    assert X.sezioni_esterne_precedenti(percorso)["fonti_esterne_del"] == "2026-09-21T10:00:00+00:00"   # la data resta quella vera
    percorso.write_text("{rotto", encoding="utf-8")
    assert X.sezioni_esterne_precedenti(percorso) == {}


def test_giro_su_alcune_borse_conserva_le_altre(tmp_path):
    percorso = tmp_path / "qualita.json"
    percorso.write_text(json.dumps({"eseguito": "2026-09-21T10:00:00+00:00", "borse": {"US": {"x": 1}, "LSE": {"x": 2}},
                                    "borse_controllate_il": {"US": "2026-09-21T10:00:00+00:00",
                                                             "LSE": "2026-09-21T10:00:00+00:00"}}), encoding="utf-8")
    nuovo = {"eseguito": "2026-09-25T10:00:00+00:00", "borse": {"LSE": {"x": 3}}}
    assert X.borse_precedenti(percorso, nuovo) == {
        "borse": {"US": {"x": 1}, "LSE": {"x": 3}},
        "borse_controllate_il": {"US": "2026-09-21T10:00:00+00:00", "LSE": "2026-09-25T10:00:00+00:00"}}
    assert X.borse_precedenti(tmp_path / "manca.json", nuovo)["borse"] == {"LSE": {"x": 3}}


def test_cache_edgar_compressa_e_valida_7_giorni(tmp_path):
    import gzip
    import os
    chiamate = []

    def trasporto(url):
        chiamate.append(url)
        return 200, b'{"filings": {"recent": {}}}' * 100

    oggi = [dt.date(2026, 9, 19)]
    e = E.Edgar(tmp_path, user_agent="Nome Cognome a@b.it", trasporto=trasporto, dormi=lambda s: None, oggi=lambda: oggi[0])
    assert e.get("https://data.sec.gov/x.json", un_giorno=True).startswith(b'{"filings"')
    f = next((tmp_path / "eodhd/edgar_cache").glob("*.bin.gz"))
    assert f.stat().st_size < 2_000 and gzip.decompress(f.read_bytes()).count(b"filings") == 100      # compressa
    oggi[0] = dt.date(2026, 9, 21)
    e.get("https://data.sec.gov/x.json", un_giorno=True)
    assert len(chiamate) == 1                                                     # due giorni dopo: dalla cache
    vecchio = dt.datetime(2026, 9, 10).timestamp()
    os.utime(f, (vecchio, vecchio))
    e.get("https://data.sec.gov/x.json", un_giorno=True)
    assert len(chiamate) == 2                                                     # oltre 7 giorni: di nuovo
    e.get("https://www.sec.gov/Archives/doc.htm")
    os.utime(next(p for p in (tmp_path / "eodhd/edgar_cache").glob("*.bin.gz") if p != f), (vecchio, vecchio))
    e.get("https://www.sec.gov/Archives/doc.htm")
    assert len(chiamate) == 3                                                     # un documento non scade


def test_applica_esiti_bilanci():
    """Il salto confermato dal bilancio smette di escludere e diventa una nota sul giorno del salto; gli altri
    restano e si portano dietro il motivo."""
    salto = dt.date(2000, 9, 29)
    segnalazioni = [
        {"code": "AAPL", "controllo": "salto_sospetto", "from_date": dt.date(1984, 9, 7),
         "to_date": salto - dt.timedelta(days=1), "esclude": True, "detail": "salto del 2000-09-29: rapporto 0,4813"},
        {"code": "ICON", "controllo": "salto_sospetto", "from_date": dt.date(1990, 1, 22),
         "to_date": dt.date(2015, 12, 16), "esclude": True, "detail": "salto del 2015-12-17: rapporto 0,1046"},
        {"code": "OTHER", "controllo": "volume_zero", "from_date": dt.date(2001, 1, 1),
         "to_date": dt.date(2001, 3, 1), "esclude": True, "detail": "40 sedute"},
    ]
    esiti = {("AAPL", salto): ("vero", "10-K dell'esercizio 2000-09-30: massimo dichiarato 75,19"),
             ("ICON", dt.date(2015, 12, 17)): ("fuori scala", "massimo dichiarato 44,81; fuori scala di 9,56 volte")}
    fuori = X.applica_esiti_bilanci(segnalazioni, esiti)

    aapl = next(r for r in fuori if r["code"] == "AAPL")
    assert aapl["controllo"] == "salto_confermato" and aapl["esclude"] is False
    assert aapl["from_date"] == aapl["to_date"] == salto          # la nota copre il giorno, non la storia prima

    icon = next(r for r in fuori if r["code"] == "ICON")
    assert icon["controllo"] == "salto_sospetto" and icon["esclude"] is True
    assert "9,56 volte" in icon["detail"]

    altro = next(r for r in fuori if r["code"] == "OTHER")
    assert altro == segnalazioni[2]                               # gli altri controlli non si toccano


def test_salto_fuori_ambito_lo_dice():
    """Fuori dall'ambito la verifica non si fa per scelta, e la segnalazione lo scrive."""
    salto = dt.date(2005, 6, 1)
    riga = {"code": "PINKY", "controllo": "salto_sospetto", "from_date": dt.date(2000, 1, 3),
            "to_date": salto - dt.timedelta(days=1), "esclude": True, "detail": "salto del 2005-06-01"}
    fuori = X.applica_esiti_bilanci([riga], {})
    assert fuori[0]["esclude"] is True
    assert "non verificato sui bilanci per scelta" in fuori[0]["detail"]
