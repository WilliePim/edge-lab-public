"""Normalizzazione in Parquet su un livello grezzo finto."""
import datetime as dt
import json

import pyarrow.parquet as pq

from market_data.store import normalize as N
from market_data.store.raw import Grezzo

CSV = b"Date,Open,High,Low,Close,Adjusted_close,Volume\n2020-01-02,1,2,0.5,1.5,1.4,100\n2020-01-03,1.5,2,1,1.8,1.7,\n"
JSON = json.dumps([{"date": "2020-01-02", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "adjusted_close": 1.4, "volume": 100},
                   {"date": "2020-01-03", "open": 1.5, "high": 2, "low": 1, "close": 1.8, "adjusted_close": 1.7, "volume": None}]).encode()


def test_csv_e_json_danno_la_stessa_tabella():
    a = N.leggi_prezzi(CSV, "csv", "X", "USD")
    b = N.leggi_prezzi(JSON, "json", "X", "USD")
    assert a.equals(b) and a.num_rows == 2
    assert a.column("volume").to_pylist() == [100, None] and a.column("date").to_pylist()[0] == dt.date(2020, 1, 2)
    assert N.leggi_prezzi(b"Date,Open,High,Low,Close,Adjusted_close,Volume\n", "csv", "X", "").num_rows == 0


def test_date_doppie_e_disordinate():
    corpo = b"Date,Open,High,Low,Close,Adjusted_close,Volume\n2020-01-03,1,1,1,3,3,1\n2020-01-02,1,1,1,2,2,1\n2020-01-03,1,1,1,9,9,1\n"
    t = N.leggi_prezzi(corpo, "csv", "X", "")
    assert t.column("date").to_pylist() == [dt.date(2020, 1, 2), dt.date(2020, 1, 3)]
    t2, n, prima = N.leggi_prezzi_con_doppioni(corpo, "csv", "X", "")
    assert (n, prima) == (1, dt.date(2020, 1, 3)) and t2.column("close").to_pylist() == [2.0, 3.0]    # vale la prima riga


def test_simboli_gemelli_e_split():
    assert N.simbolo("eod/SMRT_old.US") == ("SMRT_old", "US")
    assert N.simbolo("eod/BRK.B.US") == ("BRK.B", "US") and N.simbolo("eod/A%20B.LSE") == ("A B", "LSE")
    delistati = {"P_old", "FRSH_old", "FRSH_old1", "FRSH1", "X1"}
    assert N.gemelli({"P", "P_old", "FRSH", "FRSH_old", "FRSH_old1", "FRSH1", "X1"}, "US", delistati) == {
        "P": ["P_old"], "FRSH": ["FRSH1", "FRSH_old", "FRSH_old1"]}
    assert N.gemelli({"QQT", "QQT3"}, "US", set()) == {}                     # cifra su un codice attivo: non è un gemello
    assert N.gemelli({"980", "9801"}, "HK", {"9801"}) == {}                  # fuori dagli USA la cifra non conta
    assert N.gemelli({"ABC", "ABC_old"}, "LSE", set()) == {"ABC": ["ABC_old"]}
    assert N.rapporto_split("2.000000/1.000000") == (2.0, 1.0, 2.0)
    assert N.rapporto_split("1.000000/10.000000")[2] == 0.1 and N.rapporto_split("x") == (None, None, None)


def csv_barre(barre):
    return b"Date,Open,High,Low,Close,Adjusted_close,Volume\n" + b"".join(
        "{},1,1,1,{},{},{}\n".format(d.isoformat(), c, c, v).encode() for d, c, v in barre)


def test_barre_copiate_dal_gemello_tolte():
    giorni = [dt.date(2011, 6, 1) + dt.timedelta(days=i) for i in range(25)]
    vecchie = [(g, 17.0 + i / 100, 3_918_500 + i) for i, g in enumerate(giorni)]
    copiate = [(g, c, v - 32) for g, c, v in vecchie]                        # volume arrotondato dal fornitore: 0,001%
    nuove = [(dt.date(2015, 10, 7), 16.01, 900)]
    attivo = N.leggi_prezzi(csv_barre(copiate + nuove), "csv", "P", "USD")
    vecchio = N.leggi_prezzi(csv_barre(vecchie), "csv", "P_old", "USD")
    t, reg = N.togli_barre_copiate(attivo, {"P_old": vecchio})
    assert t.column("date").to_pylist() == [dt.date(2015, 10, 7)]
    assert reg == [{"twin": "P_old", "removed": 25, "first_date": giorni[0], "last_date": giorni[-1]}]
    #  coincidenze isolate (meno di 20 sedute di fila) restano
    poche = N.leggi_prezzi(csv_barre(copiate[:5] + nuove), "csv", "P", "USD")
    assert N.togli_barre_copiate(poche, {"P_old": vecchio}) == (poche, [])
    #  volume troppo diverso: non è una copia
    diverse = N.leggi_prezzi(csv_barre([(g, c, v * 2) for g, c, v in vecchie]), "csv", "P", "USD")
    assert N.togli_barre_copiate(diverse, {"P_old": vecchio})[1] == []


def test_versione_corta_non_sostituisce():
    storia = [{"endpoint": "eod/Y.US", "file": "a", "righe": 5000}, {"endpoint": "eod/Y.US", "file": "b", "righe": 0}]
    scelta, mancata = N.scegli_versione(storia)
    assert scelta["file"] == "a" and mancata["scartata"] == "b"
    storia = [{"endpoint": "eod/Y.US", "file": "a", "righe": 5000}, {"endpoint": "eod/Y.US", "file": "b", "righe": 5003}]
    assert N.scegli_versione(storia) == (storia[1], None)


def test_normalizzazione_completa_e_ripetibile(tmp_path):
    g = Grezzo(tmp_path)
    g.salva("exchange-symbol-list/US", {"fmt": "json"}, 200, json.dumps([{"Code": "P", "Currency": "USD"}]).encode())
    g.salva("eod/P.US", {"fmt": "csv"}, 200, b"Date,Open,High,Low,Close,Adjusted_close,Volume\n"
                                           b"2011-06-15,1,1,1,17.42,17.42,500\n2015-10-07,1,1,1,16.01,16.01,900\n")
    g.salva("eod/P_old.US", {"fmt": "json"}, 200, json.dumps([{"date": "2011-06-15", "open": 1, "high": 1, "low": 1,
                                                               "close": 17.42, "adjusted_close": 17.42, "volume": 500}]).encode())
    g.salva("eod/P.US", {"fmt": "json"}, 200, b"[]")              # JSON vecchio del campione: vale il CSV
    g.salva("div/P.US", {"fmt": "json"}, 200, json.dumps([{"date": "2016-01-04", "declarationDate": None, "recordDate": None,
                                                           "paymentDate": None, "period": None, "value": 0.1,
                                                           "unadjustedValue": 0.1, "currency": "USD"}]).encode())
    g.salva("splits/P.US", {"fmt": "json"}, 200, b'[{"date": "2020-01-02", "split": "3.000000/1.000000"}]')
    g.salva("eod/EURUSD.FOREX", {"fmt": "csv"}, 200, b"Date,Open,High,Low,Close,Adjusted_close,Volume\n2020-01-02,1.1,1.2,1.0,1.12,1.12,0\n")
    g.salva("ust/yield-rates", {"filter[year]": "2020", "fmt": "json"}, 200,
            json.dumps({"data": [{"date": "2020-01-02", "tenor": "10Y", "rate": 1.88}]}).encode())
    g.salva("id-mapping", {"filter[ex]": "US", "fmt": "json"}, 200,
            json.dumps({"data": [{"symbol": "P_old.US", "isin": "US6983541078", "cik": "0001230276"}]}).encode())
    n = N.Normalizzatore(tmp_path, log=lambda *_: None)
    esito = n.per_titolo({"prezzi", "dividendi", "split", "cambi"}, None)
    assert esito["prezzi US"] == 3 and esito["barre_tolte US"] == 0 and esito["dividendi US"] == 1 and esito["cambi FOREX"] == 1
    prezzi = pq.read_table(tmp_path / "eodhd/parquet/prezzi/exchange=US").to_pylist()
    assert [(r["code"], str(r["date"]), r["currency"]) for r in prezzi] == [
        ("P", "2011-06-15", "USD"), ("P", "2015-10-07", "USD"), ("P_old", "2011-06-15", None)]   # una barra uguale sola: resta
    div = pq.read_table(tmp_path / "eodhd/parquet/dividendi/exchange=US").to_pylist()
    assert div[0]["currency"] == "USD" and div[0]["currency_from_listing"] is False
    assert pq.read_table(tmp_path / "eodhd/parquet/split/exchange=US").to_pylist()[0]["factor"] == 3.0
    assert n.tesoro() == 1 and n.identificativi() == {"US": 1}
    righe_man = (tmp_path / "eodhd/manifest/normalizzato.jsonl").read_text().strip().split("\n")
    assert all(json.loads(r)["sha256"] for r in righe_man)
    n.per_titolo({"prezzi"}, None)                                  # di nuovo: stessa partizione, nessun doppione
    assert pq.read_table(tmp_path / "eodhd/parquet/prezzi/exchange=US").num_rows == 3
    assert not list((tmp_path / "eodhd/parquet/prezzi").glob(".tmp_*")) and not list((tmp_path / "eodhd/parquet/prezzi").glob(".old_*"))


def test_manifest_con_riga_troncata(tmp_path):
    g = Grezzo(tmp_path)
    g.salva("eod/X.US", {"fmt": "csv"}, 200, CSV)
    with (tmp_path / "eodhd/manifest/grezzo.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"chiave": "eod/Y.US?fmt=csv", "file": "eodhd/raw/2026')           # interruzione a metà riga
    g2 = Grezzo(tmp_path)
    assert g2.righe_illeggibili == 1 and g2.gia_scaricato("eod/X.US", {"fmt": "csv"}) is not None


def test_identificativi_vuoti_diventano_mancanti(tmp_path):
    g = Grezzo(tmp_path)
    g.salva("id-mapping", {"filter[ex]": "US", "fmt": "json"}, 200, json.dumps({"data": [
        {"symbol": "A.US", "isin": "US1", "cik": "", "cusip": " ", "figi": None}]}).encode())
    N.Normalizzatore(tmp_path, log=lambda *_: None).identificativi()
    r = pq.read_table(tmp_path / "eodhd/parquet/identificativi/exchange=US").to_pylist()[0]
    assert (r["isin"], r["cik"], r["cusip"], r["figi"]) == ("US1", None, None, None)
