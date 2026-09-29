"""Catena completa su un archivio finto: grezzo → Parquet → anagrafica → calendario → viste → market_data.api."""
import datetime as dt
import json

import pyarrow as pa
import pytest

from market_data import api
from market_data.quality import calendario as K
from market_data.store import catalog, identity
from market_data.store import normalize as N
from market_data.store.raw import Grezzo

TESTA = b"Date,Open,High,Low,Close,Adjusted_close,Volume\n"


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path))
    g = Grezzo(tmp_path)
    attivi = [{"Code": "P", "Name": "Everpure, Inc.", "Exchange": "NYSE", "Currency": "USD", "Type": "Common Stock", "Isin": "US74624M1027"}]
    delistati = [{"Code": "P_old", "Name": "Pandora Media Inc", "Exchange": "NYSE", "Currency": "USD", "Type": "Common Stock", "Isin": "US6983541078"}]
    g.salva("exchange-symbol-list/US", {"fmt": "json"}, 200, json.dumps(attivi).encode())
    g.salva("exchange-symbol-list/US", {"delisted": "1", "fmt": "json"}, 200, json.dumps(delistati).encode())
    giorni, d = [], dt.date(2015, 10, 6)
    while len(giorni) < 25:                                              # 25 sedute di Pandora fino al 2015-10-06
        if d.weekday() < 5:
            giorni.insert(0, d)
        d -= dt.timedelta(days=1)
    pandora = [(gg, 11.0 if gg == dt.date(2015, 10, 6) else round(10.0 + i / 10, 2), 650 + i) for i, gg in enumerate(giorni)]
    riga = lambda gg, c, v: "{},1,1,1,{},{},{}\n".format(gg.isoformat(), c, c, v).encode()  # noqa: E731
    g.salva("eod/P_old.US", {"fmt": "csv"}, 200, TESTA + b"".join(riga(*x) for x in pandora))
    g.salva("eod/P.US", {"fmt": "csv"}, 200, TESTA + b"".join(riga(*x) for x in pandora)      # storia copiata da Pandora
            + b"2015-10-07,1,1,1,16.01,16.01,900\n2015-10-08,1,1,1,15.93,15.93,800\n")
    g.salva("splits/P.US", {"fmt": "json"}, 200, b"[]")
    g.salva("div/P_old.US", {"fmt": "json"}, 200, json.dumps([{"date": "2015-10-05", "value": 0.1, "unadjustedValue": 0.1,
                                                               "currency": "USD"}]).encode())
    g.salva("eod/EURUSD.FOREX", {"fmt": "csv"}, 200, TESTA + b"2015-10-06,1.12,1.13,1.11,1.125,1.125,0\n")
    g.salva("id-mapping", {"filter[ex]": "US", "fmt": "json"}, 200,
            json.dumps({"data": [{"symbol": "P_old.US", "isin": "US6983541078", "cik": "0001230276"}]}).encode())
    n = N.Normalizzatore(tmp_path, log=lambda *_: None)
    n.per_titolo({"prezzi", "dividendi", "split", "cambi"}, None)
    n.identificativi()
    identity.Anagrafica(tmp_path, log=lambda *_: None).costruisci(["US"])
    K.scrivi_calendario(tmp_path, ["US"], fine="2015-12-31")
    api.refresh()
    yield tmp_path
    api.refresh()


def test_prezzi_e_ticker_riusato(archivio):
    p = api.prices("P.US")
    assert [str(d)[:10] for d in p["date"]] == ["2015-10-07", "2015-10-08"]      # la barra di Pandora è tolta da P
    vecchio = api.prices(["P_old.US"], start="2015-10-06")
    assert list(vecchio["close"]) == [11.0]
    ana = api.listings(ticker="P")
    assert list(ana["code"]) == ["P_old", "P"] and list(ana["isin"]) == ["US6983541078", "US74624M1027"]
    riga_old = ana[ana["code"] == "P_old"].iloc[0]
    assert riga_old["cik"] == "0001230276" and riga_old["twins"] == "P" and riga_old["status"] == "delistato"
    assert int(ana[ana["code"] == "P"].iloc[0]["removed_bars"]) == 25


def test_dividendi_split_cambi_calendario(archivio):
    assert list(api.dividends("P_old.US")["value"]) == [0.1]
    assert len(api.splits("P.US")) == 0
    assert list(api.fx("EURUSD")["close"]) == [1.125]
    giorni = api.trading_days("US", "2015-11-25", "2015-11-30")
    assert giorni == [dt.date(2015, 11, 25), dt.date(2015, 11, 27), dt.date(2015, 11, 30)]      # Thanksgiving chiuso


def test_prezzi_puliti_e_verifiche(archivio):
    base, man = archivio / "eodhd" / "parquet", archivio / "eodhd" / "manifest"
    part = N.Partizione(base, man, "segnalazioni", "US")
    part.aggiungi(pa.table({"code": ["P_old"], "controllo": ["salto_sospetto"], "from_date": [dt.date(2015, 10, 1)],
                            "to_date": [dt.date(2015, 10, 5)], "detail": ["prova"], "esclude": [True]},
                               schema=catalog.SCHEMA_SEGNALAZIONI))
    part.chiudi([])
    api.refresh()
    puliti = [str(d)[:10] for d in api.prices("P_old.US")["date"]]
    assert "2015-10-05" not in puliti and "2015-10-01" not in puliti and "2015-10-06" in puliti and len(puliti) == 22
    assert len(api.prices("P_old.US", clean=False)) == 25
    assert len(api.flags("P_old.US")) == 1
    (archivio / "eodhd" / "verifiche.jsonl").write_text(json.dumps({
        "code": "P_old", "exchange": "US", "controllo": "salto_sospetto", "from_date": "2015-10-01", "to_date": "2015-10-05",
        "source": "IWM 2015-09-30", "note": "prezzo implicito uguale"}) + "\n", encoding="utf-8")
    api.refresh()
    assert len(api.prices("P_old.US")) == 25


def test_simbolo_senza_borsa(archivio):
    with pytest.raises(ValueError, match="CODICE.BORSA"):
        api.prices("AAPL")


def test_tabelle_assenti_danno_viste_vuote(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path))
    api.refresh()
    assert len(api.prices("X.US")) == 0 and len(api.listings()) == 0 and api.trading_days("US") == []
    api.refresh()


def test_verifiche_tolleranti_e_simboli_ripetuti(archivio):
    righe = [json.dumps({"code": "P_old", "exchange": "US", "controllo": "salto_sospetto", "from_date": "2015-10-01",
                         "to_date": "2015-10-05", "source": "IWM"}),
             "{non json", json.dumps({"code": "X", "exchange": "US"}), ""]
    (archivio / "eodhd" / "verifiche.jsonl").write_text("﻿" + "\n".join(righe), encoding="utf-8")
    api.refresh()
    assert len(api.verifications()) == 1 and len(api.verification_problems()) == 2
    assert len(api.prices(["P.US", "P.US"])) == len(api.prices("P.US"))                         # nessun doppione


def test_flags_con_verificato_e_refresh_in_altri_thread(archivio):
    import threading
    base, man = archivio / "eodhd" / "parquet", archivio / "eodhd" / "manifest"
    risultati = []
    t = threading.Thread(target=lambda: risultati.append(len(api.flags())))
    t.start(); t.join()
    part = N.Partizione(base, man, "segnalazioni", "US")
    part.aggiungi(pa.table({"code": ["P_old"], "controllo": ["volume_zero"], "from_date": [dt.date(2015, 10, 5)],
                            "to_date": [dt.date(2015, 10, 5)], "detail": ["x"], "esclude": [True]},
                               schema=catalog.SCHEMA_SEGNALAZIONI))
    part.chiudi([])
    api.refresh()
    t = threading.Thread(target=lambda: risultati.append(len(api.flags())))
    t.start(); t.join()
    assert risultati == [0, 1]
    f = api.flags("P_old.US")
    assert bool(f["verified"].iloc[0]) is False


def test_catalogo_su_disco_con_verifiche(archivio):
    import duckdb
    p = catalog.costruisci_catalogo(archivio, log=lambda *_: None)
    con = duckdb.connect(str(p), read_only=True)
    assert con.execute("SELECT count(*) FROM prezzi_puliti WHERE code = 'P'").fetchone()[0] == 2
    con.close()
