"""I controlli in SQL danno gli stessi risultati delle funzioni Python di riferimento (`quality/checks.py`)."""
import datetime as dt
import random

import duckdb
import pyarrow as pa
import pytest

from market_data.quality import checks as Q
from market_data.quality import sql as S

GIORNO0 = dt.date(2000, 1, 3)


def serie_casuale(rng: random.Random, n: int) -> list[dict]:
    """Prezzi con salti da split finti, ritorni, penny stock, volumi zero ripetuti, buchi di volume."""
    prezzo, barre = rng.choice([0.02, 0.8, 25.0]), []
    for i in range(n):
        u = rng.random()
        if u < 0.02:
            prezzo *= rng.choice(Q.CANDIDATI) * rng.uniform(0.94, 1.06)
        elif u < 0.03:
            prezzo *= rng.choice([0.5, 2.0])
        else:
            prezzo *= rng.uniform(0.97, 1.03)
        prezzo = max(prezzo, 0.0001)
        volume = 0 if rng.random() < 0.15 else (None if rng.random() < 0.02 else rng.randint(1, 10_000))
        if barre and rng.random() < 0.3 and barre[-1]["volume"] == 0:
            prezzo, volume = barre[-1]["close"], 0                              # prezzo fermo a volume zero
        barre.append({"date": GIORNO0 + dt.timedelta(days=i), "close": round(prezzo, 6), "volume": volume})
    return barre


@pytest.fixture(scope="module")
def dati():
    rng = random.Random(20260917)
    tutte = {"C{:02d}".format(i): serie_casuale(rng, rng.randint(30, 400)) for i in range(40)}
    split = {("C03", tutte["C03"][10]["date"]), ("C07", tutte["C07"][50]["date"])}
    con = duckdb.connect()
    righe = [dict(b, code=c, exchange="US", open=b["close"], adjusted_close=b["close"]) for c, s in tutte.items() for b in s]
    con.register("prezzi_t", pa.Table.from_pylist(righe))
    con.execute("CREATE VIEW prezzi AS SELECT * FROM prezzi_t")
    con.register("split_t", pa.Table.from_pylist([{"code": c, "date": d, "factor": 2.0, "exchange": "US"} for c, d in split]))
    con.execute("CREATE VIEW split AS SELECT * FROM split_t")
    return con, tutte, split


def test_salti_sql_uguali_a_python(dati):
    con, tutte, split = dati
    da_sql = {(x["code"], x["data"], x["rapporto_tipico"], x["volume_coerente"]) for x in S.salti_split_mancanti(con, "US")}
    da_py = set()
    for c, s in tutte.items():
        date_split = {str(d) for cc, d in split if cc == c}
        barre = [dict(b, date=str(b["date"])) for b in s]
        for x in Q.esamina_salti(barre, date_split)["segnalati"]:
            da_py.add((c, dt.date.fromisoformat(x["data"]), x["rapporto_tipico"], x["volume_coerente"]))
    assert da_py and da_sql == da_py


def test_volume_zero_sql_uguale_a_python(dati):
    con, tutte, _ = dati
    da_sql = {(r[0], r[1], r[2], r[3]) for r in S.sequenze_volume_zero(con, "US", minimo=3)}
    da_py = set()
    for c, s in tutte.items():
        for x in Q.sequenze_volume_zero([dict(b, date=b["date"]) for b in s], minimo=3):
            da_py.add((c, x["da"], x["a"], x["sedute"]))
    assert da_py and da_sql == da_py


def test_buchi_duplicati_impossibili_coerenza():
    con = duckdb.connect()
    giorni = [dt.date(2020, 1, d) for d in (2, 3, 6, 7, 8, 9, 10)]
    con.register("cal_t", pa.Table.from_pylist([{"date": g, "exchange": "US"} for g in giorni]))
    con.execute("CREATE VIEW calendario AS SELECT * FROM cal_t")
    barre = [("A", dt.date(2020, 1, 2), 10.0, 10.0), ("A", dt.date(2020, 1, 3), 10.0, 10.0), ("A", dt.date(2020, 1, 4), 10.0, 10.0),
             ("A", dt.date(2020, 1, 10), 5.0, 10.0),                           # split 2:1 il 10: grezza /2, rettificata continua
             ("B", dt.date(2020, 1, 3), 1.0, 1.0), ("B", dt.date(2020, 1, 6), 0.05, 0.05), ("B", dt.date(2020, 1, 7), 0.0, 0.0),
             ("B", dt.date(2020, 1, 8), 0.05, -0.2)]                            # rettificata negativa: capita nei dati veri
    con.register("p_t", pa.Table.from_pylist([{"code": c, "date": d, "close": x, "adjusted_close": a, "open": x, "volume": 1,
                                               "exchange": "US"} for c, d, x, a in barre]))
    con.execute("CREATE VIEW prezzi AS SELECT * FROM p_t")
    con.register("s_t", pa.Table.from_pylist([{"code": "A", "date": dt.date(2020, 1, 10), "factor": 2.0, "exchange": "US"},
                                              {"code": "B", "date": dt.date(2020, 1, 6), "factor": 2.0, "exchange": "US"},
                                              {"code": "A", "date": dt.date(2020, 1, 3), "factor": 1.03, "exchange": "US"}]))
    con.execute("CREATE VIEW split AS SELECT * FROM s_t")
    con.register("d_t", pa.Table.from_pylist([{"code": "B", "duplicates": 2, "first_date": dt.date(2020, 1, 3), "exchange": "US"}]))
    con.execute("CREATE VIEW doppioni AS SELECT * FROM d_t")
    b = S.buchi(con, "US")
    per = {x["code"]: x for x in b["titoli_sopra_soglia"]}
    assert per["A"]["sedute"] == 7 and per["A"]["mancanti"] == 4 and b["barre_fuori_seduta"] == 1   # il 4 è sabato
    assert S.duplicati(con, "US")["righe"] == 2
    imp = S.prezzi_impossibili(con, "US")
    assert imp["rettificate_non_positive"] == 2 and imp["titoli_con_rettificate_non_positive"] == 1   # B: zero e negativa
    assert imp["chiusure_non_positive"] == 1 and imp["salti_oltre_90"] == 0       # B: -95% ma split registrato quel giorno
    coe = S.coerenza_split(con, "US")
    assert coe["split"] == 3 and coe["fattore_vicino_a_1_non_valutabili"] == 1 and coe["valutati"] == 2
    assert coe["incoerenti"] == 1 and coe["esempi"][0]["code"] == "B"


def test_a_blocchi_stesso_risultato(dati, monkeypatch):
    """I due controlli a finestra mobile girano a blocchi di codici per non tenere in memoria una borsa intera.
    Ogni serie sta tutta dentro un blocco, quindi le risposte devono essere identiche al giro unico."""
    con, _tutte, _split = dati
    salti_interi = S.salti_split_mancanti(con, "US")
    zero_interi = S.sequenze_volume_zero(con, "US")

    monkeypatch.setattr(S, "BARRE_PER_BLOCCO", 500)          # con queste serie vengono piu' blocchi
    blocchi = S.blocchi_per(con, "US")
    assert len(blocchi) > 1, "il test non prova niente se resta un blocco solo"

    salti_a_blocchi, zero_a_blocchi = [], []
    for b in blocchi:
        salti_a_blocchi += S.salti_split_mancanti(con, "US", blocco=b)
        zero_a_blocchi += S.sequenze_volume_zero(con, "US", blocco=b)

    chiave = lambda x: (x["code"], x["data"])                                          # noqa: E731
    assert sorted(salti_a_blocchi, key=chiave) == sorted(salti_interi, key=chiave)
    assert sorted(zero_a_blocchi) == sorted(zero_interi)


def test_ogni_codice_sta_in_un_blocco_solo(dati, monkeypatch):
    """Se un codice cadesse in due blocchi, le sue finestre mobili sarebbero spezzate e i conti cambierebbero."""
    con, tutte, _split = dati
    monkeypatch.setattr(S, "BARRE_PER_BLOCCO", 500)
    blocchi = S.blocchi_per(con, "US")
    visti = {}
    for b in blocchi:
        codici = {r[0] for r in con.execute(
            "SELECT DISTINCT code FROM prezzi WHERE exchange = 'US'" + S.filtro_blocco(b)).fetchall()}
        for c in codici:
            assert c not in visti, "{} in due blocchi".format(c)
            visti[c] = b
    assert set(visti) == set(tutte)
