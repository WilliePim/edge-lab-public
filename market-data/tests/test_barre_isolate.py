"""Barre isolate (docs/adr/011): regola pura e opzione di `api.prices`, su un archivio finto.

Nessuna rete, nessun file vero. La cosa più importante che si prova: senza l'opzione i prezzi puliti sono quelli di
prima, riga per riga.
"""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

from market_data import api
from market_data.quality import barre_isolate as BI
from market_data.quality import calendario as K
from market_data.store import identity
from market_data.store import normalize as N
from market_data.store.raw import Grezzo

TESTA = b"Date,Open,High,Low,Close,Adjusted_close,Volume\n"


def giorni(n, salta=()):
    """`n` giorni di calendario consecutivi come interi, senza quelli in `salta` (posizioni)."""
    return [k for k in range(n) if k not in salta]


# ------------------------------------------------------------------------------------------------ regola pura --

def test_la_barra_che_va_e_torna_si_scarta():
    assert list(BI.isolate(giorni(5), [0.52, 0.50, 350.0, 0.50, 0.49])) == [False, False, True, False, False]   # una chiusura che va a centinaia di dollari e torna
    assert list(BI.isolate(giorni(5), [4.0, 4.1, 0.02, 4.05, 4.1])) == [False, False, True, False, False]      # verso il basso


def test_soglie_50_e_10_per_cento():
    assert not BI.isolate(giorni(3), [100, 150.0, 100]).any()            # +50% esatto: non «oltre»
    assert BI.isolate(giorni(3), [100, 150.01, 100])[1]
    assert not BI.isolate(giorni(3), [100, 50.0, 100]).any()             # −50% esatto: non «oltre»
    assert BI.isolate(giorni(3), [100, 49.99, 100])[1]
    assert BI.isolate(giorni(3), [100, 400, 109.9])[1]                   # la successiva entro il 10% dalla precedente
    assert not BI.isolate(giorni(3), [100, 400, 110.5]).any()            # oltre il 10%: non torna
    assert BI.isolate(giorni(3), [100, 30, 90])[1] and not BI.isolate(giorni(3), [100, 30, 89]).any()
    assert not BI.isolate(giorni(3), [100, 160, 107]).any()              # +60% dalla precedente ma solo +49,5% dalla successiva


def test_un_crollo_o_uno_split_che_non_tornano_restano():
    assert not BI.isolate(giorni(5), [100, 100, 40, 41, 39]).any()       # crollo vero
    assert not BI.isolate(giorni(5), [100, 100, 50, 50, 50]).any()       # split non registrato
    assert not BI.isolate(giorni(5), [10, 10, 30, 31, 29]).any()         # rialzo che resta


def test_prima_e_ultima_barra_e_vicine_lontane_non_valutabili():
    assert not BI.isolate(giorni(3), [350, 0.50, 0.50]).any() and not BI.isolate(giorni(3), [0.50, 0.50, 350]).any()
    assert not BI.isolate([0, 1], [1, 400]).any() and not BI.isolate([], []).any()
    assert BI.isolate([0, 10, 20], [1, 400, 1])[1]                       # 10 giorni di calendario: ancora vicine
    assert not BI.isolate([0, 11, 12], [1, 400, 1]).any() and not BI.isolate([0, 1, 12], [1, 400, 1]).any()


def test_valori_mancanti_o_non_positivi():
    nan = float("nan")
    assert not BI.isolate(giorni(3), [1, nan, 1]).any() and not BI.isolate(giorni(3), [nan, 400, 1]).any()
    assert not BI.isolate(giorni(3), [1, 400, 0]).any() and not BI.isolate(giorni(3), [1, -5, 1]).any()


def test_due_barre_sbagliate_di_fila_non_sono_prese_e_l_estensione_le_prende():
    v = [1, 1, 400, 410, 1, 1]
    assert not BI.isolate(giorni(6), v).any()
    assert list(BI.gruppi(giorni(6), v)) == [False, False, True, True, False, False]
    assert not BI.gruppi(giorni(5), [1, 1, 400, 1, 1]).any()             # la barra singola è di `isolate`, non dei gruppi
    assert list(BI.gruppi(giorni(7), [1, 1, 400, 410, 405, 1, 1])) == [False, False, True, True, True, False, False]
    assert not BI.gruppi(giorni(8), [1, 1, 400, 410, 405, 402, 1, 1]).any()          # quattro: oltre il massimo
    assert not BI.gruppi(giorni(6), [1, 1, 400, 410, 2, 2]).any()        # non torna


def test_serie_che_alterna_due_livelli():
    alterna = [60, 7.5, 60, 7.5, 60, 7.5, 60]
    assert list(BI.isolate(giorni(7), alterna)) == [False, True, True, True, True, True, False]   # tutte tranne le estreme: dichiarato
    a_tratti = [60, 60, 7.5, 7.5, 60, 60, 7.5, 7.5, 60]
    assert not BI.isolate(giorni(9), a_tratti).any()


def test_varianti_con_il_volume():
    v, g = [1, 400, 1, 1, 400, 2, 2], giorni(7)
    vol = [5000, 10, 5000, 5000, 999, 5000, 5000]
    assert list(BI.isolate(g, v)) == [False, True, False, False, False, False, False]
    assert list(BI.isolate(g, v, vol, BI.PREZZO_E_VOLUME)) == [False, True, False, False, False, False, False]
    assert list(BI.isolate(g, v, vol, BI.PREZZO_O_VOLUME)) == [False, True, False, False, True, False, False]   # va, torna a metà, volume < 1.000
    assert not BI.isolate(g, v, [5000, 1000, 5000, 5000, 1000, 5000, 5000], BI.PREZZO_E_VOLUME).any()            # 1.000 non è «sotto»
    with pytest.raises(ValueError):
        BI.isolate(g, v, None, BI.PREZZO_E_VOLUME)
    with pytest.raises(ValueError):
        BI.isolate(g, v, vol, "altro")


def test_non_itera():
    #  tolta la barra a 400, la barra a 30 resterebbe fra 10 e 10: ma si valuta una volta sola, sulla serie di partenza
    assert list(BI.isolate(giorni(5), [10, 400, 10.5, 30, 10])) == [False, True, False, True, False]
    assert list(BI.isolate(giorni(4), [10, 400, 30, 10])) == [False, False, False, False]


# ------------------------------------------------------------------------------------- opzione di api.prices --

SERIE = {"SANO": {}, "PICCO": {9: (350.0, 350.0, 10)}, "RETT": {9: (10.0, 0.05, 700)}, "CROLLO": {k: (4.0, 4.0, 900) for k in range(9, 20)},
         "ULTIMA": {19: (350.0, 350.0, 10)}}


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path))
    g = Grezzo(tmp_path)
    g.salva("exchange-symbol-list/US", {"fmt": "json"}, 200, json.dumps(
        [{"Code": c, "Name": c + " Inc", "Exchange": "NASDAQ", "Currency": "USD", "Type": "Common Stock",
          "Isin": "US00000001{:02d}".format(i)} for i, c in enumerate(SERIE, 1)]).encode())
    date, d = [], dt.date(2021, 6, 1)
    while len(date) < 20:
        if d.weekday() < 5:
            date.append(d)
        d += dt.timedelta(days=1)
    for codice, diverse in SERIE.items():
        corpo = TESTA
        for k, gg in enumerate(date):
            c, a, v = diverse.get(k, (10.0, 10.0, 500))
            corpo += "{},1,1,1,{},{},{}\n".format(gg.isoformat(), c, a, v).encode()
        g.salva("eod/{}.US".format(codice), {"fmt": "csv"}, 200, corpo)
    n = N.Normalizzatore(tmp_path, log=lambda *_: None)
    n.per_titolo({"prezzi"}, None)
    identity.Anagrafica(tmp_path, log=lambda *_: None).costruisci(["US"])
    K.scrivi_calendario(tmp_path, ["US"], fine="2021-12-31")
    api.refresh()
    yield tmp_path, date
    api.refresh()


def simboli():
    return [c + ".US" for c in SERIE]


def test_il_default_non_cambia_e_l_opzione_toglie_solo_le_barre_isolate(archivio):
    _, date = archivio
    puliti = api.prices(simboli())
    assert puliti.groupby("code").size().to_dict() == {c: 20 for c in SERIE}                      # come sempre: tutte
    con = api.prices(simboli(), barre_isolate="scarta")
    assert con.groupby("code").size().to_dict() == {"SANO": 20, "PICCO": 19, "RETT": 19, "CROLLO": 20, "ULTIMA": 20}
    assert pd.Timestamp(date[9]) not in set(con[con["code"] == "PICCO"]["date"])
    assert list(con.columns) == list(puliti.columns)
    #  dopo aver usato l'opzione il default è ancora quello di prima, riga per riga
    pd.testing.assert_frame_equal(api.prices(simboli()), puliti)
    pd.testing.assert_frame_equal(api.prices(simboli(), barre_isolate=None), puliti)
    assert len(api.flags(simboli())) == 0 and len(api.verifications()) == 0                       # niente scritto nell'archivio
    assert not (archivio[0] / "eodhd" / "verifiche.jsonl").exists()


def test_le_date_chieste_non_cambiano_quali_barre_sono_isolate(archivio):
    _, date = archivio
    #  chiedendo dal giorno della barra, la barra è la prima della richiesta ma non della serie: resta scartata
    df = api.prices("PICCO.US", start=date[9], barre_isolate="scarta")
    assert len(df) == 10 and df["date"].min() == pd.Timestamp(date[10])
    assert len(api.prices("PICCO.US", end=date[9], barre_isolate="scarta")) == 9
    assert len(api.prices("PICCO.US", start=date[9], end=date[9], barre_isolate="scarta")) == 0
    assert len(api.prices("PICCO.US", start=date[9], end=date[9])) == 1                           # il default la restituisce


def test_elenco_delle_barre_scartate(archivio):
    _, date = archivio
    el = api.barre_isolate(simboli())
    assert sorted(el["code"]) == ["PICCO", "RETT"] and len(api.barre_isolate("SANO.US")) == 0
    r = el[el["code"] == "PICCO"].iloc[0]
    assert (r["date"], r["close"], r["volume"]) == (pd.Timestamp(date[9]), 350.0, 10)
    assert (r["date_prima"], r["close_prima"], r["date_dopo"], r["adjusted_dopo"]) == (pd.Timestamp(date[8]), 10.0, pd.Timestamp(date[10]), 10.0)
    assert el[el["code"] == "RETT"].iloc[0]["close"] == 10.0                                      # sbagliata solo la rettificata


def test_opzione_sconosciuta_o_con_i_prezzi_grezzi(archivio):
    with pytest.raises(ValueError, match="sconosciuta"):
        api.prices("PICCO.US", barre_isolate="togli")
    with pytest.raises(ValueError, match="clean=True"):
        api.prices("PICCO.US", clean=False, barre_isolate="scarta")
    assert len(api.prices("PICCO.US", clean=False)) == 20


def test_la_maschera_non_mescola_i_codici(archivio):
    #  l'ultima barra di ULTIMA (350) e la prima del codice dopo non fanno una barra isolata a cavallo di due codici
    df = api.prices(["ULTIMA.US", "SANO.US"])
    assert not np.asarray(api._maschera_isolate(df)).any()


def test_la_regola_pura_dall_api():
    v, g, vol = [1, 400, 1, 1, 400, 2, 2], giorni(7), [5000, 10, 5000, 5000, 999, 5000, 5000]
    assert list(api.regola_barre_isolate(g, v)) == list(BI.isolate(g, v))
    assert list(api.regola_barre_isolate(g, v, vol, "prezzo_o_volume")) == list(BI.isolate(g, v, vol, BI.PREZZO_O_VOLUME))
    assert list(api.regola_barre_isolate(giorni(6), [1, 1, 400, 410, 1, 1], gruppi=True)) == [False, False, True, True, False, False]
