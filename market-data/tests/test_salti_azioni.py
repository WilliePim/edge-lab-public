"""Verifica dei salti sospetti con le azioni in circolazione: regola pura e opzione di `api.prices`, su un archivio finto.

Nessuna rete, nessun file vero. La cosa più importante che si prova: senza l'opzione i prezzi puliti sono quelli di
prima, con o senza i file della SEC.
"""
import datetime as dt
import json
import zipfile

import pandas as pd
import pyarrow as pa
import pytest

from market_data import api
from market_data import sec as S
from market_data.quality import calendario as K
from market_data.quality import salti_azioni as SA
from market_data.store import catalog, identity
from market_data.store import normalize as N
from market_data.store.raw import Grezzo

TESTA = b"Date,Open,High,Low,Close,Adjusted_close,Volume\n"
G = dt.date(2021, 6, 15)                       # giorno del salto, uguale per tutti
D = dt.date
VOCI = S.VOCI_AZIONI


def oss(fine, valore, depositato, accn="a", inizio=None):
    return (inizio, fine, float(valore), depositato, accn)


# ------------------------------------------------------------------------------------------------ regola pura --

def test_giudizio_tolleranze():
    assert SA.giudizio(100, 100, 0.5) == SA.MOVIMENTO_VERO
    assert SA.giudizio(100, 124, 0.5) == SA.MOVIMENTO_VERO and SA.giudizio(100, 81, 0.5) == SA.MOVIMENTO_VERO
    assert SA.giudizio(100, 126, 0.5) is None and SA.giudizio(100, 79, 0.5) is None        # oltre ±25%: non si sa
    assert SA.giudizio(100, 200, 0.5) == SA.SPLIT_VERO and SA.giudizio(100, 170, 0.5) == SA.SPLIT_VERO
    assert SA.giudizio(100, 10, 10) == SA.SPLIT_VERO                                        # raggruppamento 1 a 10
    assert SA.giudizio(100, 100000, 0.5) is None                                            # errore di scala: non si sa
    assert SA.giudizio(0, 100, 0.5) is None and SA.giudizio(100, None, 0.5) is None


def test_dettaglio_della_segnalazione():
    assert SA.leggi_dettaglio("salto del 2021-03-15: rapporto 0.5100 vicino a 0.5, fascia sopra 1, volume coerente") == \
        (D(2021, 3, 15), 0.51, 0.5)
    assert SA.leggi_dettaglio("salto del 2013-05-20: rapporto 99.5000 vicino a 100, fascia sopra 1, volume coerente; non "
                              "verificato sui bilanci per scelta (fuori ambito)")[2] == 100.0
    assert SA.leggi_dettaglio("prova") is None and SA.leggi_dettaglio(None) is None


def test_prima_e_dopo_il_salto():
    frontespizio = [oss(D(2021, 4, 30), 100, D(2021, 5, 5)), oss(D(2021, 1, 31), 90, D(2021, 2, 20)),
                    oss(D(2021, 7, 30), 101, D(2021, 8, 5)), oss(D(2021, 10, 29), 150, D(2021, 11, 4))]
    assert SA.attorno(frontespizio, G) == ((100.0, D(2021, 4, 30)), (101.0, D(2021, 7, 30)))
    #  un comparativo riesposto dopo uno split: stessa data di prima, ma depositato dopo il salto -> non è «prima»
    riesposto = [oss(D(2021, 3, 31), 100, D(2021, 5, 5), "q1"), oss(D(2021, 3, 31), 200, D(2021, 8, 5), "q2"),
                 oss(D(2021, 6, 30), 200, D(2021, 8, 5), "q2")]
    assert SA.attorno(riesposto, G) == ((100.0, D(2021, 3, 31)), (200.0, D(2021, 6, 30)))
    #  finestra di 200 giorni
    lontane = [oss(D(2020, 11, 20), 100, D(2020, 11, 25)), oss(D(2022, 1, 10), 100, D(2022, 1, 15))]
    assert SA.attorno(lontane, G) == (None, None)
    #  due classi nello stesso deposito: sommate
    classi = [oss(D(2021, 4, 30), 60, D(2021, 5, 5), "q"), oss(D(2021, 4, 30), 40, D(2021, 5, 5), "q"), oss(D(2021, 7, 30), 100, D(2021, 8, 5))]
    assert SA.attorno(classi, G)[0] == (100.0, D(2021, 4, 30))
    #  media ponderata: solo trimestri, il «dopo» deve iniziare dopo il salto
    media = [oss(D(2021, 3, 31), 100, D(2021, 5, 5), "q1", D(2021, 1, 1)), oss(D(2021, 6, 30), 120, D(2021, 8, 5), "q2", D(2021, 4, 1)),
             oss(D(2021, 9, 30), 200, D(2021, 11, 5), "q3", D(2021, 7, 1)), oss(D(2021, 9, 30), 150, D(2021, 11, 5), "q3", D(2021, 1, 1))]
    assert SA.attorno(media, G, media=True) == ((100.0, D(2021, 3, 31)), (200.0, D(2021, 9, 30)))


def test_classifica_voci_ordine_disaccordo_e_dati_mancanti():
    fermo = [oss(D(2021, 4, 30), 100, D(2021, 5, 5)), oss(D(2021, 7, 30), 101, D(2021, 8, 5))]
    doppio = [oss(D(2021, 3, 31), 100, D(2021, 5, 5)), oss(D(2021, 6, 30), 200, D(2021, 8, 5))]
    r = SA.classifica({VOCI[0]: fermo}, VOCI, G, 0.5)
    assert (r["esito"], r["voce"], r["azioni_prima"], r["azioni_dopo"], r["motivo"]) == (SA.MOVIMENTO_VERO, VOCI[0], 100.0, 101.0, None)
    assert SA.classifica({VOCI[1]: doppio}, VOCI, G, 0.5)["esito"] == SA.SPLIT_VERO
    assert SA.classifica({VOCI[0]: fermo}, VOCI, G, 2.0)["esito"] == SA.MOVIMENTO_VERO          # rialzo vero
    r = SA.classifica({VOCI[0]: fermo, VOCI[1]: doppio}, VOCI, G, 0.5)
    assert r["esito"] == SA.NON_DETERMINABILE and "disaccordo" in r["motivo"]
    scala = [oss(D(2021, 4, 30), 100, D(2021, 5, 5)), oss(D(2021, 7, 30), 100000, D(2021, 8, 5))]
    assert SA.classifica({VOCI[0]: scala, VOCI[1]: fermo}, VOCI, G, 0.5)["esito"] == SA.MOVIMENTO_VERO   # decide la voce che dice qualcosa
    r = SA.classifica({VOCI[0]: scala}, VOCI, G, 0.5)
    assert r["esito"] == SA.NON_DETERMINABILE and r["rapporto_azioni"] == 1000.0
    r = SA.classifica({VOCI[0]: fermo[:1]}, VOCI, G, 0.5)
    assert r["esito"] == SA.NON_DETERMINABILE and "entro 200 giorni" in r["motivo"]
    assert SA.classifica({}, VOCI, G, 0.5)["esito"] == SA.NON_DETERMINABILE


# ------------------------------------------------------------------------------------------- archivio finto --

CODICI = {"CROLLO": (1001, 0.5), "SPLIT": (1002, 0.5), "RIALZO": (1003, 2.0), "IGNOTO": (1004, 0.5), "NOCIK": (None, 0.5),
          "SANO": (1006, None)}


def fatto(end, val, filed, accn):
    return {"end": end, "val": val, "accn": accn, "fy": 2021, "fp": "Q2", "form": "10-Q", "filed": filed}


def azioni_sec(prima, dopo):
    righe = [fatto("2021-04-30", prima, "2021-05-05", "q1")]
    if dopo is not None:
        righe.append(fatto("2021-07-30", dopo, "2021-08-05", "q2"))
    return {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": righe}}}}}


def scrivi_sec(cartella):
    cartella.mkdir(parents=True, exist_ok=True)
    f = cartella / S.FILE["companyfacts"]
    with zipfile.ZipFile(f, "w") as z:
        for cik, d in ((1001, azioni_sec(1e6, 1.02e6)), (1002, azioni_sec(1e6, 2e6)), (1003, azioni_sec(1e6, 1e6)),
                       (1004, azioni_sec(1e6, None))):
            z.writestr("CIK{:010d}.json".format(cik), json.dumps(d))
    (cartella / "manifest.json").write_text(json.dumps({"companyfacts": {"byte": f.stat().st_size, "sha256": "finta"}}), encoding="utf-8")


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path))
    g = Grezzo(tmp_path)
    g.salva("exchange-symbol-list/US", {"fmt": "json"}, 200, json.dumps(
        [{"Code": c, "Name": c + " Inc", "Exchange": "NASDAQ", "Currency": "USD", "Type": "Common Stock",
          "Isin": "US00000000{:02d}".format(i)} for i, c in enumerate(CODICI, 1)]).encode())
    giorni, d = [], G - dt.timedelta(days=14)
    while len(giorni) < 20:
        if d.weekday() < 5:
            giorni.append(d)
        d += dt.timedelta(days=1)
    for codice, (_cik, k) in CODICI.items():
        corpo = TESTA
        for gg in giorni:
            c = 10.0 if (k is None or gg < G) else 10.0 * k
            corpo += "{},1,1,1,{},{},500\n".format(gg.isoformat(), c, c).encode()
        g.salva("eod/{}.US".format(codice), {"fmt": "csv"}, 200, corpo)
    g.salva("id-mapping", {"filter[ex]": "US", "fmt": "json"}, 200, json.dumps({"data": [
        {"symbol": c + ".US", "isin": "US00000000{:02d}".format(i), "cik": "{:010d}".format(cik)}
        for i, (c, (cik, _k)) in enumerate(CODICI.items(), 1) if cik]}).encode())
    n = N.Normalizzatore(tmp_path, log=lambda *_: None)
    n.per_titolo({"prezzi"}, None)
    n.identificativi()
    identity.Anagrafica(tmp_path, log=lambda *_: None).costruisci(["US"])
    K.scrivi_calendario(tmp_path, ["US"], fine="2021-12-31")
    saltano = [c for c, (_cik, k) in CODICI.items() if k is not None]
    part = N.Partizione(tmp_path / "eodhd" / "parquet", tmp_path / "eodhd" / "manifest", "segnalazioni", "US")
    part.aggiungi(pa.table({
        "code": saltano, "controllo": ["salto_sospetto"] * len(saltano), "from_date": [giorni[0]] * len(saltano),
        "to_date": [G - dt.timedelta(days=1)] * len(saltano),
        "detail": ["salto del {}: rapporto {:.4f} vicino a {:g}, fascia sopra 1, volume assente".format(G, CODICI[c][1], CODICI[c][1])
                   for c in saltano], "esclude": [True] * len(saltano)}, schema=catalog.SCHEMA_SEGNALAZIONI))
    part.chiudi([])
    scrivi_sec(tmp_path / S.CARTELLA)
    S.dimentica()
    api.refresh()
    yield tmp_path, giorni
    S.dimentica()
    api.refresh()


def simboli():
    return [c + ".US" for c in CODICI]


def test_classificazione_dei_salti_sull_archivio(archivio):
    df = api.salti_classificati(simboli()).set_index("code")
    assert list(df.columns) == [c for c in SA.COLONNE if c != "code"]
    assert df.loc["CROLLO", "esito"] == SA.MOVIMENTO_VERO and df.loc["RIALZO", "esito"] == SA.MOVIMENTO_VERO
    assert df.loc["SPLIT", "esito"] == SA.SPLIT_VERO and df.loc["SPLIT", "rapporto_azioni"] == 2.0
    assert df.loc["IGNOTO", "esito"] == SA.NON_DETERMINABILE and "entro 200 giorni" in df.loc["IGNOTO", "motivo"]
    assert df.loc["NOCIK", "esito"] == SA.NON_DETERMINABILE and df.loc["NOCIK", "motivo"] == "titolo senza CIK"
    assert "SANO" not in df.index and df.loc["CROLLO", "data_salto"] == pd.Timestamp(G)
    assert set(api.salti_classificati()["code"]) == set(CODICI) - {"SANO"}        # senza simboli: tutti i segnalati USA


def test_il_default_non_cambia_e_l_opzione_riammette_solo_i_movimenti_veri(archivio):
    _, giorni = archivio
    prima_del_salto = sum(1 for g_ in giorni if g_ < G)
    puliti = api.prices(simboli())
    conta = puliti.groupby("code").size().to_dict()
    assert conta == {c: (20 if k is None else 20 - prima_del_salto) for c, (_cik, k) in CODICI.items()}   # come sempre
    con = api.prices(simboli(), verifica_salti="azioni")
    conta_con = con.groupby("code").size().to_dict()
    assert conta_con["CROLLO"] == 20 and conta_con["RIALZO"] == 20                 # movimento vero: la storia torna
    assert conta_con["SPLIT"] == conta["SPLIT"] and conta_con["IGNOTO"] == conta["IGNOTO"] and conta_con["NOCIK"] == conta["NOCIK"]
    assert conta_con["SANO"] == 20
    #  dopo aver usato l'opzione il default è ancora quello di prima, riga per riga
    pd.testing.assert_frame_equal(api.prices(simboli()), puliti)
    pd.testing.assert_frame_equal(api.prices(simboli(), verifica_salti=None), puliti)
    assert len(api.flags(simboli())) == 5 and not api.flags(simboli())["verified"].any()   # le segnalazioni non sono toccate
    assert len(api.verifications()) == 0 and not (archivio[0] / "eodhd" / "verifiche.jsonl").exists()
    #  filtro sulle date anche con l'opzione
    assert len(api.prices("CROLLO.US", start=G, verifica_salti="azioni")) == 20 - prima_del_salto


def test_il_default_non_legge_i_file_sec(archivio):
    tmp, _ = archivio
    S.dimentica()
    for f in (tmp / S.CARTELLA).iterdir():
        if f.is_file():
            f.unlink()
    api.refresh()
    assert len(api.prices(simboli())) > 0                                           # senza file SEC il default funziona
    with pytest.raises(S.FileMancante):
        api.prices(simboli(), verifica_salti="azioni")                              # l'opzione no: errore chiaro, nessun ripiego


def test_opzione_sconosciuta_o_con_i_prezzi_grezzi(archivio):
    with pytest.raises(ValueError, match="sconosciuta"):
        api.prices("CROLLO.US", verifica_salti="bilanci")
    with pytest.raises(ValueError, match="clean=True"):
        api.prices("CROLLO.US", clean=False, verifica_salti="azioni")


def test_una_verifica_a_mano_resta_valida_e_separata(archivio):
    tmp, giorni = archivio
    (tmp / "eodhd" / "verifiche.jsonl").write_text(json.dumps({
        "code": "IGNOTO", "exchange": "US", "controllo": "salto_sospetto", "from_date": giorni[0].isoformat(),
        "to_date": (G - dt.timedelta(days=1)).isoformat(), "source": "prova", "note": ""}) + "\n", encoding="utf-8")
    api.refresh()
    assert len(api.prices("IGNOTO.US")) == 20 and len(api.prices("IGNOTO.US", verifica_salti="azioni")) == 20
    assert len(api.prices("CROLLO.US")) < 20                                        # la verifica automatica non è diventata manuale
    assert len((tmp / "eodhd" / "verifiche.jsonl").read_text(encoding="utf-8").splitlines()) == 1
