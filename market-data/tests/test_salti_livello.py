"""Salti di livello non spiegati (docs/adr/012): regola pura ed elenco dell'API, su un archivio finto.

Nessuna rete, nessun file vero. `prices()` non ha opzioni nuove: si prova che resta com'è, riga per riga.
"""
import datetime as dt
import json

import pandas as pd
import pyarrow as pa
import pytest

from market_data import api
from market_data.quality import calendario as K
from market_data.quality import salti_livello as SL
from market_data.store import catalog, identity
from market_data.store import normalize as N
from market_data.store.raw import Grezzo

TESTA = b"Date,Open,High,Low,Close,Adjusted_close,Volume\n"


def esiti(chiusure, giorni=None, **altro):
    return [(i, e) for i, _r, e in SL.esamina(giorni or list(range(len(chiusure))), chiusure, **altro)]


# ------------------------------------------------------------------------------------------------ regola pura --

def test_salto_che_persiste_in_entrambe_le_direzioni():
    assert esiti([0.20] * 3 + [25.0, 25.4, 24.8, 24.5, 26.0, 25.1]) == [(3, SL.PRESO)]              # da centesimi a decine di dollari, e resta
    assert esiti([10.0] * 3 + [1.9, 1.8, 2.0, 2.2, 1.7, 1.9]) == [(3, SL.PRESO)]                     # verso il basso
    giu, su = [10.0] * 3 + [1.9, 1.8, 2.0, 2.2, 1.7, 1.9], [0.20] * 3 + [25.0, 25.4, 24.8, 24.5, 26.0, 25.1]
    #  regola adottata: solo i rialzi; la variante «alla lettera» prende anche i ribassi
    assert SL.salti(list(range(9)), su) == [3] and SL.salti(list(range(9)), giu) == []
    assert SL.salti(list(range(9)), giu, direzione=SL.ENTRAMBE) == [3] and SL.salti(list(range(9)), su, direzione=SL.ENTRAMBE) == [3]
    with pytest.raises(ValueError, match="sconosciuta"):
        SL.salti(list(range(9)), su, direzione="ribassi")


def test_esenzione_dei_movimenti_veri():
    su, g = [0.20] * 3 + [25.0, 25.4, 24.8, 24.5, 26.0, 25.1], list(range(100, 109))
    assert SL.salti(g, su) == [3]
    assert SL.salti(g, su, esenti=[103]) == []                           # il giorno del salto è un «movimento vero» di ADR 010
    assert SL.salti(g, su, esenti=[102, 104]) == [3]                     # un altro giorno non esenta
    assert SL.salti(g, su, direzione=SL.ENTRAMBE, esenti=[103]) == []


def test_soglie_comprese():
    dopo = [50.0] * 5
    assert esiti([10.0, 50.0] + dopo) == [(1, SL.PRESO)]                                              # esattamente 5
    assert esiti([10.0, 49.9] + [49.9] * 5) == []                                                     # poco meno di 5
    assert esiti([10.0, 2.0] + [2.0] * 5) == [(1, SL.PRESO)]                                          # esattamente 0,2
    assert esiti([10.0, 2.01] + [2.01] * 5) == []
    assert esiti([10.0, 50.0, 75.0, 25.0, 50.0, 50.0, 50.0]) == [(1, SL.PRESO)]                       # ±50% esatto: resta
    assert esiti([10.0, 50.0, 75.1, 50.0, 50.0, 50.0, 50.0]) == [(1, SL.NON_PERSISTE)]
    assert esiti([10.0, 50.0, 50.0, 50.0, 50.0, 50.0, 24.9]) == [(1, SL.NON_PERSISTE)]                # anche la quinta conta
    assert esiti([10.0, 50.0, 50.0, 50.0, 50.0, 50.0, 50.0, 24.0]) == [(1, SL.PRESO)]                 # la sesta no


def test_una_barra_che_torna_non_persiste_ma_il_ritorno_si():
    #  per questo le barre isolate si tolgono prima (ADR 012): il ritorno di una barra isolata «persiste»
    assert esiti([0.50, 0.50, 350.0, 0.50, 0.49, 0.50, 0.49, 0.50, 0.51]) == [(2, SL.NON_PERSISTE), (3, SL.PRESO)]


def test_meno_di_cinque_barre_dopo():
    assert esiti([10.0, 60.0, 60.0, 60.0, 60.0, 60.0]) == [(1, SL.POCHE_BARRE)]                       # quattro
    assert esiti([10.0, 60.0]) == [(1, SL.POCHE_BARRE)] and esiti([10.0]) == [] and esiti([]) == []


def test_split_registrato_in_quella_data():
    serie, g = [1.0, 1.0, 10.0, 10.2, 9.9, 10.0, 10.1, 10.0], list(range(100, 108))
    assert esiti(serie, g) == [(2, SL.PRESO)]
    assert esiti(serie, g, split=[(102, 0.1)]) == [(2, SL.SPLIT)]                                     # raggruppamento 1 a 10 quel giorno
    assert esiti(serie, g, split=[(102, 0.125)]) == [(2, SL.SPLIT)]                                   # 1 a 8: entro il 25%
    assert esiti(serie, g, split=[(102, 0.5)]) == [(2, SL.PRESO)]                                     # fattore non compatibile
    assert esiti(serie, g, split=[(102, 10.0)]) == [(2, SL.PRESO)]                                    # split dalla parte sbagliata
    assert esiti(serie, g, split=[(101, 0.1)]) == [(2, SL.PRESO)] and esiti(serie, g, split=[(103, 0.1)]) == [(2, SL.PRESO)]   # altra data
    assert esiti(serie, g, note=[102]) == [(2, SL.SPLIT)]                                             # nota `split_del_fornitore`
    giu = [40.0, 40.0, 4.0, 4.1, 3.9, 4.0, 4.0, 4.2]
    assert esiti(giu, g, split=[(102, 10.0)]) == [(2, SL.SPLIT)] and esiti(giu, g) == [(2, SL.PRESO)]


def test_barre_lontane_non_valutate():
    serie = [1.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    assert esiti(serie, [0, 10, 11, 12, 13, 14, 15]) == [(1, SL.PRESO)]                               # 10 giorni: ancora consecutive
    assert esiti(serie, [0, 11, 12, 13, 14, 15, 16]) == [(1, SL.LONTANE)]
    assert esiti(serie, [0, 1, 40, 80, 120, 160, 200]) == [(1, SL.PRESO)]                             # dopo il salto la distanza non conta


def test_valori_non_validi_e_varianti():
    nan = float("nan")
    assert esiti([10.0, nan, 60.0, 60.0, 60.0, 60.0, 60.0, 60.0]) == []                               # nessun rapporto valido
    assert esiti([10.0, 0.0, 60.0] + [60.0] * 5) == []
    assert esiti([10.0, 60.0, 60.0, nan, 60.0, 60.0, 60.0]) == [(1, SL.NON_PERSISTE)]
    tre = [10.0, 35.0, 35.0, 35.0, 35.0, 35.0, 35.0]
    assert esiti(tre) == [] and esiti(tre, soglia=3.0) == [(1, SL.PRESO)]
    largo = [10.0, 60.0, 80.0, 60.0, 60.0, 60.0, 60.0]
    assert esiti(largo) == [(1, SL.PRESO)] and esiti(largo, persistenza=0.25) == [(1, SL.NON_PERSISTE)]


def test_due_salti_vicini():
    assert esiti([1.0, 6.0, 6.0, 40.0, 40.0, 40.0, 40.0, 40.0, 40.0]) == [(1, SL.NON_PERSISTE), (3, SL.PRESO)]


# ------------------------------------------------------------------------------------------- elenco dell'API --

SERIE = {"SANO": {}, "LIVELLO": {k: (60.0, 60.0, 900) for k in range(9, 20)}, "GIU": {k: (1.5, 1.5, 2_000_000) for k in range(9, 20)},
         "SPLIT": {k: (100.0, 10.0, 500) for k in range(9, 20)}, "NOTA": {k: (100.0, 10.0, 500) for k in range(9, 20)},
         "PICCO": {9: (350.0, 350.0, 10)}, "FINE": {k: (80.0, 80.0, 500) for k in range(16, 20)}}


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path))
    g = Grezzo(tmp_path)
    g.salva("exchange-symbol-list/US", {"fmt": "json"}, 200, json.dumps(
        [{"Code": c, "Name": c + " Inc", "Exchange": "NASDAQ", "Currency": "USD", "Type": "Common Stock",
          "Isin": "US00000002{:02d}".format(i)} for i, c in enumerate(SERIE, 1)]).encode())
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
    g.salva("splits/SPLIT.US", {"fmt": "json"}, 200, json.dumps([{"date": date[9].isoformat(), "split": "1.000000/10.000000"}]).encode())
    n = N.Normalizzatore(tmp_path, log=lambda *_: None)
    n.per_titolo({"prezzi", "split"}, None)
    identity.Anagrafica(tmp_path, log=lambda *_: None).costruisci(["US"])
    K.scrivi_calendario(tmp_path, ["US"], fine="2021-12-31")
    part = N.Partizione(tmp_path / "eodhd" / "parquet", tmp_path / "eodhd" / "manifest", "segnalazioni", "US")
    part.aggiungi(pa.table({"code": ["NOTA"], "controllo": ["split_del_fornitore"], "from_date": [date[9]], "to_date": [date[9]],
                            "detail": ["salto del {}: la rettificata non salta".format(date[9])], "esclude": [False]},
                           schema=catalog.SCHEMA_SEGNALAZIONI))
    part.chiudi([])
    api.refresh()
    yield tmp_path, date
    api.refresh()


def simboli():
    return [c + ".US" for c in SERIE]


def test_elenco_dei_salti_e_prezzi_invariati(archivio):
    _, date = archivio
    prima = api.prices(simboli())
    adottata = api.salti_di_livello(simboli())
    #  regola adottata (default): solo i rialzi. LIVELLO preso; GIU (ribasso) e il ritorno di PICCO (ribasso) no
    assert sorted(adottata["code"]) == ["LIVELLO"] and list(adottata["direzione"]) == ["rialzo"]
    el = api.salti_di_livello(simboli(), direzione="entrambe", esenta_movimento_vero=False)       # variante «alla lettera»
    assert list(el.columns) == ["exchange", "code", "date", "date_prima", "close_prima", "close", "rapporto", "direzione", "volume"]
    assert list(adottata.columns) == list(el.columns)
    per = {r.code: r for r in el.itertuples(index=False)}
    #  LIVELLO e GIU presi; SPLIT (tabella) e NOTA (nota del fornitore) spiegati; FINE ha solo 3 barre dopo; SANO niente;
    #  PICCO senza togliere le barre isolate: il ritorno «persiste» ed è preso (per questo si tolgono prima)
    assert sorted(per) == ["GIU", "LIVELLO", "PICCO"]
    r = per["LIVELLO"]
    assert (r.date, r.date_prima, r.close_prima, r.close, r.direzione) == (pd.Timestamp(date[9]), pd.Timestamp(date[8]), 10.0, 60.0, "rialzo")
    assert per["GIU"].direzione == "ribasso" and per["GIU"].rapporto == pytest.approx(0.15) and per["GIU"].volume == 2_000_000
    assert per["PICCO"].date == pd.Timestamp(date[10])
    con = api.salti_di_livello(simboli(), barre_isolate="scarta", direzione="entrambe", esenta_movimento_vero=False)
    assert sorted(con["code"]) == ["GIU", "LIVELLO"]                                 # tolta la barra isolata, PICCO non ha salti
    assert sorted(api.salti_di_livello(simboli(), barre_isolate="scarta")["code"]) == ["LIVELLO"]
    with pytest.raises(ValueError, match="sconosciuta"):
        api.salti_di_livello(simboli(), direzione="ribassi")
    assert len(api.salti_di_livello("SANO.US")) == 0 and list(api.salti_di_livello("SANO.US").columns) == list(el.columns)
    #  l'elenco non tocca i prezzi: né il default né le righe, né le segnalazioni
    pd.testing.assert_frame_equal(api.prices(simboli()), prima)
    assert prima.groupby("code").size().to_dict() == {c: 20 for c in SERIE}
    assert len(api.flags(simboli())) == 1 and len(api.verifications()) == 0
    assert not (archivio[0] / "eodhd" / "verifiche.jsonl").exists()


def test_un_movimento_vero_di_adr_010_non_si_spezza_mai(archivio, monkeypatch):
    _, date = archivio
    assert sorted(api.salti_di_livello("LIVELLO.US")["code"]) == ["LIVELLO"]
    vero = [{"exchange": "US", "code": "LIVELLO", "esito": "movimento_vero", "data_salto": date[9]}]
    monkeypatch.setattr(api, "_righe_salti", lambda coppie: vero)
    assert len(api.salti_di_livello("LIVELLO.US")) == 0                              # esente
    assert len(api.salti_di_livello("LIVELLO.US", esenta_movimento_vero=False)) == 1  # senza esenzione è preso
    altro_giorno = [{"exchange": "US", "code": "LIVELLO", "esito": "movimento_vero", "data_salto": date[3]}]
    monkeypatch.setattr(api, "_righe_salti", lambda coppie: altro_giorno)
    assert len(api.salti_di_livello("LIVELLO.US")) == 1
    non_det = [{"exchange": "US", "code": "LIVELLO", "esito": "non_determinabile", "data_salto": date[9]}]
    monkeypatch.setattr(api, "_righe_salti", lambda coppie: non_det)
    assert len(api.salti_di_livello("LIVELLO.US")) == 1                              # solo i «movimento vero» esentano


def test_la_regola_pura_dall_api():
    serie = [10.0, 60.0, 80.0, 60.0, 60.0, 60.0, 60.0]
    assert api.regola_salti_di_livello(list(range(7)), serie) == SL.esamina(list(range(7)), serie)
    assert [e for _i, _r, e in api.regola_salti_di_livello(list(range(7)), serie, persistenza=0.25)] == [SL.NON_PERSISTE]
