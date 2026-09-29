"""Download in massa con un fornitore finto: piano, filtri, ripartenza, fermate, attesa del tetto. Nessuna chiamata reale."""
import datetime as dt
import json

import pytest

from market_data.config import Limiti
from market_data.eodhd import download as D
from market_data.eodhd.client import Client
from market_data.store.raw import Grezzo

CHIAVE = "0123456789abcd" + "." + "12345678"
LISTA_ATT = [{"Code": "AAA", "Type": "Common Stock", "Isin": "US0000000001", "Name": "A", "Currency": "USD"},
             {"Code": "EEE", "Type": "ETF", "Isin": "", "Name": "E", "Currency": "USD"},
             {"Code": "PPP", "Type": "Preferred Stock", "Isin": "", "Name": "P", "Currency": "USD"}]
LISTA_DEL = [{"Code": "OLD_old", "Type": "Common Stock", "Isin": "US0000000002", "Name": "O", "Currency": "USD"},
             {"Code": "AAA", "Type": "Common Stock", "Isin": "US0000000001", "Name": "A", "Currency": "USD"}]


class Orologio:
    def __init__(self):
        self.t = dt.datetime(2026, 9, 17, 23, 50, tzinfo=dt.timezone.utc)
        self.mono = 0.0

    def adesso(self):
        return self.t

    def dormi(self, s):
        self.t += dt.timedelta(seconds=s)
        self.mono += s


class Fornitore:
    """Risponde per endpoint; conta le richieste."""

    def __init__(self, falliti=()):
        self.richieste, self.falliti = [], set(falliti)

    def __call__(self, url):
        self.richieste.append(url)
        percorso = url.split("/api/", 1)[1].split("?", 1)[0]
        if any(f in percorso for f in self.falliti):
            return 404, b"Ticker Not Found."
        if percorso.startswith("eod/"):
            return 200, b"Date,Open,High,Low,Close,Adjusted_close,Volume\n2020-01-02,1,1,1,1,1,100\n"
        if percorso.startswith("div/"):
            return 200, b"[]"
        if percorso.startswith("splits/"):
            return 200, b'[{"date": "2020-01-02", "split": "2.000000/1.000000"}]'
        return 200, b"[]"


def prepara(tmp_path, monkeypatch, fornitore, limiti=Limiti(100_000, 1_000), libero=100 * 1024 ** 3):
    monkeypatch.setattr(D, "BLOCCHI", {"9": {"nome": "prova", "borse": ("US",)}})
    monkeypatch.setattr(D, "STIMA", {"9": (0.001, 0.001, 3)})
    monkeypatch.setattr(D, "INDICI", {"9": ("GSPC", "ASSENTE")})
    monkeypatch.setattr(D, "MINIMO_COMPITI", 3)
    orologio = Orologio()
    g = Grezzo(tmp_path)
    for ep, params, corpo in (("exchange-symbol-list/US", {"fmt": "json"}, LISTA_ATT),
                              ("exchange-symbol-list/US", {"delisted": "1", "fmt": "json"}, LISTA_DEL),
                              ("exchange-symbol-list/INDX", {"fmt": "json"}, [{"Code": "GSPC"}]),
                              ("exchange-symbol-list/FOREX", {"fmt": "json"}, [{"Code": "EURUSD"}])):
        g.salva(ep, params, 200, json.dumps(corpo).encode())
    client = Client(CHIAVE, tmp_path, limiti, trasporto=fornitore, orologio=lambda: orologio.mono,
                    dormi=orologio.dormi, adesso=orologio.adesso)
    d = D.Download(tmp_path, client, g, disco_libero=lambda: libero, dormi=orologio.dormi, adesso=orologio.adesso)
    return d, orologio


def test_titoli_filtrati_per_tipo_e_senza_doppioni():
    tt = D.titoli_da_liste("US", LISTA_ATT, LISTA_DEL)
    assert [(t.codice, t.tipo, t.stato) for t in tt] == [("AAA", "Common Stock", "attivo"), ("EEE", "ETF", "attivo"),
                                                         ("OLD_old", "Common Stock", "delistato")]


def test_filtro_francoforte():
    tt = [D.Titolo("F", c, "Common Stock", "attivo", isin, "", "EUR") for c, isin in
          (("A", "DE0001"), ("B", "DE0002"), ("C", ""), ("D", "US0003"), ("E", "de0004"))]
    tenuti, conti = D.filtro_francoforte(tt, {"DE0002"})
    assert [t.codice for t in tenuti] == ["A", "E"]
    assert conti == {"senza ISIN": 1, "ISIN non tedesco": 1, "ISIN tedesco già su Xetra": 1, "tenuti": 2}


def test_soglia_dei_fallimenti():
    assert not D.troppi_fallimenti(40, 1_000, minimo=1_500)                  # troppo presto per giudicare
    assert not D.troppi_fallimenti(40, 2_000, minimo=1_500)                  # 2,0%: non sopra
    assert D.troppi_fallimenti(41, 2_000, minimo=1_500)                      # 2,05%
    assert D.troppi_fallimenti(3, 100, minimo=1_500, finale=True)            # a fine blocco vale sempre


def test_mezzanotte_utc_e_esiti():
    assert D.secondi_alla_mezzanotte_utc(dt.datetime(2026, 9, 17, 23, 0, tzinfo=dt.timezone.utc)) == 3600 + 120
    assert D.esito_di(200, b"Date,Open\n", "prezzi") == "vuoto"
    assert D.esito_di(200, b"Date,Open\n2020-01-02,1\n", "prezzi") == "ok"
    assert D.esito_di(200, b"[]", "dividendi") == "vuoto"
    assert D.esito_di(404, b"", "prezzi") == "definitivo" and D.esito_di(503, b"", "split") == "temporaneo"


def test_blocco_completo_e_ripartenza_senza_nuove_chiamate(tmp_path, monkeypatch):
    f = Fornitore()
    d, _ = prepara(tmp_path, monkeypatch, f)
    conti = d.esegui_blocco("9", ["9"])
    assert conti == {"ok": 7, "vuoto": 3, "definitivo": 0, "temporaneo": 0}      # 3 titoli x 3 + 1 indice
    piano = json.loads((tmp_path / "eodhd/manifest/piano_9.json").read_text(encoding="utf-8"))
    assert piano["non_elencati_dal_fornitore"]["indici"] == ["ASSENTE"] and piano["conteggi"]["titoli"] == 3
    fatte = len(f.richieste)
    d3 = D.Download(tmp_path, d.client, Grezzo(tmp_path), disco_libero=lambda: 100 * 1024 ** 3)
    d3.esegui_blocco("9", ["9"])
    assert len(f.richieste) == fatte                              # tutto già nel grezzo: nessuna chiamata
    assert any("eod/AAA.US" in u and "fmt=csv" in u for u in f.richieste)


def test_fermo_sopra_il_due_per_cento(tmp_path, monkeypatch):
    f = Fornitore(falliti=("AAA.US",))
    d, _ = prepara(tmp_path, monkeypatch, f)
    with pytest.raises(D.Fermo, match="sopra il 2%"):
        d.esegui_blocco("9", ["9"])
    esiti = [json.loads(x) for x in (tmp_path / "eodhd/manifest/esiti_9.jsonl").read_text().split("\n") if x.strip()]
    assert any(e["esito"] == "definitivo" for e in esiti)


def test_fermo_per_spazio(tmp_path, monkeypatch):
    d, _ = prepara(tmp_path, monkeypatch, Fornitore(), libero=1024 ** 3)       # 1 GB: sotto il margine di 5 GB
    with pytest.raises(D.Fermo, match="spazio insufficiente"):
        d.esegui_blocco("9", ["9"])


def test_file_stop(tmp_path, monkeypatch):
    d, _ = prepara(tmp_path, monkeypatch, Fornitore())
    (tmp_path / "eodhd/manifest/STOP").write_text("", encoding="utf-8")
    with pytest.raises(D.Fermo, match="STOP"):
        d.esegui_blocco("9", ["9"])


def test_tetto_giornaliero_aspetta_e_riprende(tmp_path, monkeypatch):
    f = Fornitore()
    d, orologio = prepara(tmp_path, monkeypatch, f, limiti=Limiti(5, 1_000))    # 90% di 5 = 4 chiamate al giorno
    conti = d.esegui_blocco("9", ["9"])
    assert conti["ok"] + conti["vuoto"] == 10
    assert orologio.t.date() > dt.date(2026, 9, 18)                              # ha atteso almeno un azzeramento
    log = (tmp_path / "eodhd/manifest/download.log").read_text(encoding="utf-8")
    assert "tetto giornaliero" in log


# ---------------------------------------------------------------- correzioni dopo la revisione (17-09-2026) --
class FornitoreProgrammato(Fornitore):
    """Stato HTTP per endpoint da una tabella modificabile; il resto come Fornitore."""

    def __init__(self, stati=None):
        super().__init__()
        self.stati = dict(stati or {})

    def __call__(self, url):
        percorso = url.split("/api/", 1)[1].split("?", 1)[0]
        for chiave, stato in self.stati.items():
            if chiave in percorso:
                self.richieste.append(url)
                return stato, b"Forbidden"
        return super().__call__(url)


def test_riga_troncata_negli_esiti_non_blocca_la_ripartenza(tmp_path, monkeypatch):
    f = Fornitore()
    d, _ = prepara(tmp_path, monkeypatch, f)
    d.esegui_blocco("9", ["9"])
    with (tmp_path / "eodhd/manifest/esiti_9.jsonl").open("ab") as fh:
        fh.write(b'{"quando": "2026-09-1')                                   # interruzione a metà riga
    d2 = D.Download(tmp_path, d.client, Grezzo(tmp_path), disco_libero=lambda: 100 * 1024 ** 3)
    assert d2.esegui_blocco("9", ["9"])["ok"] == 7
    D.Download(tmp_path, d.client, Grezzo(tmp_path)).registra_esito("9", D.compiti_titolo(D.Titolo("US", "Z", "ETF", "attivo", "", "", ""))[0], 200, "ok", 1)
    ultime = (tmp_path / "eodhd/manifest/esiti_9.jsonl").read_bytes().split(b"\n")
    assert ultime[-2].startswith(b'{"quando"') and b"eod/Z.US" in ultime[-2]                # riga nuova non incollata


def test_403_isolato_si_ripete_alla_ripartenza(tmp_path, monkeypatch):
    f = FornitoreProgrammato({"div/AAA.US": 403})
    d, _ = prepara(tmp_path, monkeypatch, f)
    monkeypatch.setattr(D, "MINIMO_COMPITI", 1_000)
    with pytest.raises(D.Fermo):                                             # 1 fallito su 10 a fine blocco: sopra il 2%
        d.esegui_blocco("9", ["9"])
    f.stati.clear()                                                          # il fornitore torna a rispondere
    d2 = D.Download(tmp_path, d.client, Grezzo(tmp_path), disco_libero=lambda: 100 * 1024 ** 3)
    conti = d2.esegui_blocco("9", ["9"])
    assert conti["temporaneo"] == 0 and conti["definitivo"] == 0 and any("div/AAA.US" in u for u in f.richieste[-3:])


def test_403_di_fila_fermano_per_autorizzazione(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "MAX_AUTORIZZAZIONE_DI_FILA", 3)
    f = FornitoreProgrammato({"eod/": 403, "div/": 403, "splits/": 403})
    d, _ = prepara(tmp_path, monkeypatch, f)
    with pytest.raises(D.Fermo, match="chiave o abbonamento"):
        d.esegui_blocco("9", ["9"])


def test_402_aspetta_l_azzeramento_e_riprova(tmp_path, monkeypatch):
    class Una402(Fornitore):
        def __init__(self):
            super().__init__()
            self.fatto = False

        def __call__(self, url):
            if "eod/AAA.US" in url and not self.fatto:
                self.fatto = True
                self.richieste.append(url)
                return 402, b"limit"
            return super().__call__(url)

    f = Una402()
    d, orologio = prepara(tmp_path, monkeypatch, f)
    conti = d.esegui_blocco("9", ["9"])
    assert conti["temporaneo"] == 0 and orologio.t.date() > dt.date(2026, 9, 17)
    assert "402" in (tmp_path / "eodhd/manifest/download.log").read_text(encoding="utf-8")


def test_contatore_illeggibile_ferma_e_contatore_alto_allinea(tmp_path, monkeypatch):
    d, orologio = prepara(tmp_path, monkeypatch, Fornitore())
    d._contatore = lambda: None
    d.controlla_contatore()
    d.controlla_contatore()
    with pytest.raises(D.Fermo, match="non leggibile"):
        d.controlla_contatore()
    d._contatore_illeggibile = 0
    d._contatore = lambda: (500, orologio.t.date().isoformat())
    d.controlla_contatore()
    assert d.client.usate_oggi() == 500                                      # il registro segue il fornitore
    d._contatore = lambda: (99_999, "2026-09-16")                            # conteggio di ieri: oggi vale zero
    d.controlla_contatore()
    assert d.client.usate_oggi() == 500


def test_chiavistello(tmp_path):
    man = tmp_path / "m"
    with D.Chiavistello(man, vivo=lambda pid: False):
        assert (man / "download.lock").exists()
    assert not (man / "download.lock").exists()
    man.mkdir(parents=True, exist_ok=True)
    (man / "download.lock").write_text("424242", encoding="utf-8")
    with pytest.raises(SystemExit, match="già in corso"):
        with D.Chiavistello(man, vivo=lambda pid: True):
            pass
    with D.Chiavistello(man, vivo=lambda pid: False):                        # PID morto: il chiavistello si riprende
        pass


def test_pagina_identificativi_fallita_contata_e_ripassata(tmp_path, monkeypatch):
    class Pagine(Fornitore):
        def __init__(self):
            super().__init__()
            self.errori = 0

        def __call__(self, url):
            if "/api/id-mapping" in url:
                self.richieste.append(url)
                if "page%5Boffset%5D=1000" in url and self.errori < 20:
                    self.errori += 1
                    return 503, b""
                pagina = 0 if "page%5Boffset%5D=0" in url else 1
                return 200, json.dumps({"data": [{"symbol": "X{}.US".format(pagina)}],
                                        "links": {"next": "x" if pagina == 0 else None}}).encode()
            return super().__call__(url)

    monkeypatch.setattr(D, "PAUSA_RETE", 0.0)
    monkeypatch.setattr(D, "RIPROVE_RETE", 1)
    f = Pagine()
    d, _ = prepara(tmp_path, monkeypatch, f)
    p = d.piano("9")
    p["identificativi"] = True
    (tmp_path / "eodhd/manifest/piano_9.json").write_text(json.dumps(p), encoding="utf-8")
    monkeypatch.setattr(D, "SOGLIA_FALLIMENTI", 0.5)
    conti = d.esegui_blocco("9", ["9"])
    esiti = [json.loads(x) for x in (tmp_path / "eodhd/manifest/esiti_9.jsonl").read_text().split("\n") if x.strip()]
    assert any(e["endpoint"] == "id-mapping" and e["esito"] == "temporaneo" for e in esiti)
    assert conti["ok"] >= 8 and "mappatura identificativi" in (tmp_path / "eodhd/manifest/download.log").read_text(encoding="utf-8")


def test_esito_busta_vuota_e_ordine_dei_blocchi(tmp_path, monkeypatch):
    assert D.esito_di(200, b'{"meta": {"total": 0}, "data": [], "links": {"next": null}}', "tesoro") == "vuoto"
    assert D.esito_di(200, b'{"data": [{"date": "2020-01-02"}]}', "tesoro") == "ok"
    assert D.esito_di(403, b"", "prezzi") == "temporaneo" and D.esito_di(404, b"", "prezzi") == "definitivo"
    d, _ = prepara(tmp_path, monkeypatch, Fornitore())
    monkeypatch.setattr(D, "STIMA", {"1": (1, 1, 1), "2": (1, 1, 1), "3": (1, 1, 1)})
    assert d.frazioni_mancanti("2", 0, 10, ["2", "1", "3"]) == {"1": 1.0, "2": 1.0, "3": 1.0}
    assert d.frazioni_mancanti("1", 5, 10, ["2", "1", "3"]) == {"1": 0.5, "2": 0.0, "3": 1.0}


def test_fermata_a_meta_blocco_con_soglia_minima_ridotta(tmp_path, monkeypatch):
    f = FornitoreProgrammato({"AAA.US": 404, "EEE.US": 404})
    d, _ = prepara(tmp_path, monkeypatch, f)
    with pytest.raises(D.Fermo, match="compiti falliti su [3-6] "):         # fermo nel ciclo, non solo a fine blocco
        d.esegui_blocco("9", ["9"])


def test_spazio_solo_per_il_grezzo_del_download():
    stima = {"1": (2.0, 3.0, 10), "2": (4.0, 5.0, 10)}
    atteso = D.FATTORE_SPAZIO * (2.0 * 0.5 + 4.0 * 1.0) * 1024 ** 3 + D.MARGINE_SPAZIO     # il Parquet non conta
    assert D.spazio_necessario({"1": 0.5, "2": 1.0}, stima) == atteso


def test_spazio_per_ricostruire(tmp_path):
    from market_data.store import ricostruisci as R
    stima = {"1": (2.0, 3.0, 10), "2": (4.0, 1.0, 10)}
    libero, serve = R.spazio_per_ricostruire(tmp_path, stima, libero=7)
    assert libero == 7 and serve == D.FATTORE_SPAZIO * 4.0 * 1024 ** 3 + D.MARGINE_SPAZIO
    cartella = tmp_path / "eodhd/parquet/prezzi/exchange=US"
    cartella.mkdir(parents=True)
    (cartella / "part-00000.parquet").write_bytes(b"x" * 1024)
    assert R.spazio_per_ricostruire(tmp_path, stima, libero=7)[1] == serve - 1024           # quello che c'è già si sostituisce


def test_processo_vivo_con_pid_vero_e_morto():
    import os
    assert D.processo_vivo(str(os.getpid())) is True
    assert D.processo_vivo("999999") is False and D.processo_vivo("") is False
