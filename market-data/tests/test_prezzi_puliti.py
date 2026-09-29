"""Cosa entra e cosa non entra nei prezzi puliti, su un archivio finto.

Tre regole, tutte decise dall'utente alla fermata 3:
- un salto con la chiusura rettificata continua e' uno split che il fornitore ha applicato: si annota, non si toglie;
- una chiusura a zero o negativa non e' un prezzo: la barra sparisce, non diventa un rendimento del -100%;
- oltre il 20% di barre senza prezzo il titolo e' segnato come non abbastanza quotato per un backtest.
"""
import datetime as dt
import json

import pytest

from market_data import api
from market_data.quality import calendario as K
from market_data.quality import esegui as X
from market_data.store import catalog, identity
from market_data.store import normalize as N
from market_data.store.raw import Grezzo

TESTA = "Date,Open,High,Low,Close,Adjusted_close,Volume\n"


def csv_con_rettificata(barre, inizio=dt.date(2019, 1, 2)):
    """`barre`: (chiusura, rettificata, volume) per seduta."""
    righe, d = [], inizio
    for chiusura, rettificata, volume in barre:
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        righe.append("{},{c},{c},{c},{c},{a},{v}".format(d.isoformat(), c=chiusura, a=rettificata, v=volume))
        d += dt.timedelta(days=1)
    return (TESTA + "\n".join(righe) + "\n").encode()


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_DATA_DIR", str(tmp_path))
    g = Grezzo(tmp_path)
    attivi = [{"Code": c, "Name": c, "Exchange": "NASDAQ", "Currency": "USD", "Type": "Common Stock",
               "Isin": "US000000000{}".format(i)} for i, c in enumerate(("SPLIT", "ZERI", "SANO"), 1)]
    g.salva("exchange-symbol-list/US", {"fmt": "json"}, 200, json.dumps(attivi).encode())
    g.salva("exchange-symbol-list/US", {"delisted": "1", "fmt": "json"}, 200, b"[]")

    #  SPLIT: la grezza si dimezza, la rettificata prosegue liscia. Il fornitore conosce lo split ma non lo ha
    #  registrato nella tabella degli split, quindi il salto viene segnalato.
    barre = [(100.0, 50.0, 1000)] * 25 + [(50.0, 50.0, 1000)] * 25
    g.salva("eod/SPLIT.US", {"fmt": "csv"}, 200, csv_con_rettificata(barre))
    #  ZERI: dieci sedute su quaranta senza scambi, scritte come prezzo zero (25%, oltre la soglia del 20%).
    barre = [(10.0, 10.0, 500)] * 15 + [(0.0, 0.0, 0)] * 10 + [(10.0, 10.0, 500)] * 15
    g.salva("eod/ZERI.US", {"fmt": "csv"}, 200, csv_con_rettificata(barre))
    #  SANO: niente da segnalare.
    g.salva("eod/SANO.US", {"fmt": "csv"}, 200, csv_con_rettificata([(20.0, 20.0, 800)] * 40))
    for c in ("SPLIT", "ZERI", "SANO"):
        g.salva("splits/{}.US".format(c), {"fmt": "json"}, 200, b"[]")
    n = N.Normalizzatore(tmp_path, log=lambda *_: None)
    n.per_titolo({"prezzi", "split"}, None)
    identity.Anagrafica(tmp_path, log=lambda *_: None).costruisci(["US"])
    K.scrivi_calendario(tmp_path, ["US"], fine="2019-12-31")
    api.refresh()
    X.Controlli(tmp_path, log=lambda *_: None).esegui(["US"], esterni=False)
    api.refresh()
    yield tmp_path
    api.refresh()


def test_split_del_fornitore_e_una_nota_e_non_toglie_niente(archivio):
    """La rettificata attraversa il salto: il salto e' spiegato, la storia prima resta."""
    note = api.flags("SPLIT.US")
    assert list(note["controllo"]) == ["split_del_fornitore"]
    assert bool(note["esclude"].iloc[0]) is False
    riga = note.iloc[0]
    assert riga["from_date"] == riga["to_date"]                       # la nota copre il giorno del salto
    assert "split applicato dal fornitore" in riga["detail"]
    assert len(api.prices("SPLIT.US")) == len(api.prices("SPLIT.US", clean=False)) == 50


def test_chiusure_a_zero_spariscono_dai_prezzi_puliti(archivio):
    tutto = api.prices("ZERI.US", clean=False)
    puliti = api.prices("ZERI.US")
    assert len(tutto) == 40 and (tutto["close"] == 0).sum() == 10
    assert len(puliti) == 30
    assert (puliti["close"] > 0).all()                                # mai uno zero, quindi mai un -100%


def test_liquidita_segna_i_titoli_sotto_la_soglia(archivio):
    per_code = {r["code"]: r for _, r in api.liquidity().iterrows()}
    zeri = per_code["ZERI"]
    assert zeri["barre"] == 40 and zeri["barre_senza_prezzo"] == 10
    assert zeri["quota_senza_prezzo"] == pytest.approx(0.25)
    assert bool(zeri["liquidita_insufficiente"]) is True              # 25% > 20%
    assert bool(per_code["SANO"]["liquidita_insufficiente"]) is False
    assert per_code["SANO"]["barre_senza_prezzo"] == 0


def test_la_soglia_della_liquidita_e_dichiarata():
    """La soglia sta in un posto solo e vale 20%, come deciso."""
    assert catalog.QUOTA_LIQUIDITA_INSUFFICIENTE == 0.20


def test_la_vista_e_la_api_danno_gli_stessi_prezzi(archivio):
    """`api.prices(clean=True)` non legge `prezzi_puliti`: filtra prima sui simboli e si riscrive la query. Le due
    strade devono dire la stessa cosa, titolo per titolo, o la vista misura un archivio che nessuno legge."""
    con = api._con()
    for code in ("SPLIT", "ZERI", "SANO"):
        dalla_vista = con.execute(
            "SELECT date FROM prezzi_puliti WHERE exchange = 'US' AND code = ? ORDER BY date", [code]).fetchall()
        dalla_api = api.prices("{}.US".format(code))["date"]
        assert [d[0] for d in dalla_vista] == [d.date() for d in dalla_api], code


def test_segnalazioni_vecchie_senza_la_colonna_escludono_lo_stesso(archivio, monkeypatch):
    """Le partizioni scritte prima della fermata 3 non hanno `esclude`. Dove manca vale «esclude», che e' il
    comportamento di allora: un dato mancante non diventa un permesso."""
    import duckdb
    con = duckdb.connect()
    con.execute("CREATE VIEW segnalazioni_grezze AS SELECT 'X' AS code, 'salto_sospetto' AS controllo")
    catalog.normalizza_segnalazioni(con)
    assert con.execute("SELECT esclude FROM segnalazioni").fetchone()[0] is True

    con.execute("CREATE OR REPLACE VIEW segnalazioni_grezze AS "
                "SELECT 'X' AS code, CAST(NULL AS BOOLEAN) AS esclude")
    catalog.normalizza_segnalazioni(con)
    assert con.execute("SELECT esclude FROM segnalazioni").fetchone()[0] is True       # nulla = esclude
