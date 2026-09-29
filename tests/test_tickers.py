"""Prove sulla risoluzione del simbolo di borsa.

Il caso che conta piu' di tutti e' quello AMBIGUO. Un CIK con due classi --
GOOGL e GOOG, BRK-A e BRK-B -- non ha «il» ticker, e una correzione alla cieca
scambierebbe una classe per l'altra senza che niente lo dica. Su 7.998 CIK
quotati, 1.455 sono in questa condizione: e' un quinto, non un caso di bordo.

Il secondo caso che conta e' il SEPARATORE. EDGAR scrive `BRK-B`, i depositi
scrivono `BRK.B`. Confrontarli alla lettera classificherebbe Berkshire come
stantia e la manderebbe sulla classe A.

Per ogni esito c'e' la prova che scatta e quella che non scatta.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner import tickers as T


#  La mappa, coi casi veri incontrati sul corpus.
MAPPA = {
    "0001844971": frozenset({"GREEL", "VIP"}),      # ex Greenidge, ambiguo
    "0001839799": frozenset({"GRSD"}),              # ex GAMB, univoco
    "0001833141": frozenset({"HELP"}),              # ex CYBN, univoco
    "0000885275": frozenset({"WBHC"}),              # dichiarava NONE
    "0001067983": frozenset({"BRK-A", "BRK-B"}),    # separatore
    "0001652044": frozenset({"GOOG", "GOOGL"}),     # due classi
}


def test_normalize():
    check("il punto diventa trattino", T.normalize("BRK.B") == "BRK-B")
    check("maiuscolo", T.normalize("brk.b") == "BRK-B")
    check("spazi via", T.normalize("  VIP  ") == "VIP")
    check("None -> stringa vuota", T.normalize(None) == "")


def test_placeholder():
    for p in ("NONE", "none", "N/A", "", "-", "TBD", "NULL", "NONE."):
        check("{!r} e' un segnaposto".format(p), T.is_placeholder(p))
    for t in ("VIP", "HELP", "A", "BRK.B"):
        check("{!r} NON e' un segnaposto".format(t), not T.is_placeholder(t))


def test_valido():
    r = T.resolve("VIP", "0001844971", MAPPA)
    check("un simbolo attuale si tiene", r.ticker == "VIP", r.ticker)
    check("...con stato valido", r.status == T.VALIDO, r.status)
    check("...e non e' un cambio", not r.changed)
    check("...e non ha nulla da dire", r.note() == "", r.note())


def test_separatore_non_e_una_differenza():
    """PROVA POSITIVA sul caso che romperebbe Berkshire."""
    r = T.resolve("BRK.B", "0001067983", MAPPA)
    check("BRK.B e' valido contro BRK-B", r.status == T.VALIDO, r.status)
    check("...e il simbolo NON viene toccato", r.ticker == "BRK.B", r.ticker)
    check("...quindi non si scivola sulla classe A", r.ticker != "BRK-A")


def test_stantio_univoco():
    """PROVA POSITIVA: il caso che questo modulo esiste per correggere."""
    r = T.resolve("CYBN", "0001833141", MAPPA)
    check("CYBN diventa HELP", r.ticker == "HELP", r.ticker)
    check("...con stato corretto", r.status == T.CORRETTO, r.status)
    check("...ed e' un cambio", r.changed)
    check("...e conserva cio' che il deposito diceva",
          r.reported == "CYBN", r.reported)
    check("...e lo spiega", "CYBN" in r.note() and "HELP" in r.note(), r.note())

    r2 = T.resolve("GAMB", "0001839799", MAPPA)
    check("GAMB diventa GRSD", r2.ticker == "GRSD", r2.ticker)


def test_stantio_ambiguo_non_si_indovina():
    """Il caso piu' importante: due classi, nessuna correzione."""
    r = T.resolve("GREE", "0001844971", MAPPA)
    check("GREE NON viene corretto", r.ticker == "GREE", r.ticker)
    check("...lo stato dice ambiguo", r.status == T.AMBIGUO, r.status)
    check("...non e' un cambio", not r.changed)
    check("...i candidati sono dichiarati",
          r.candidates == ("GREEL", "VIP"), str(r.candidates))
    check("...e la nota li elenca",
          "GREEL" in r.note() and "VIP" in r.note(), r.note())

    #  Se domani il deposito scrivesse un simbolo sconosciuto su un CIK a due
    #  classi, il comportamento deve essere identico.
    r2 = T.resolve("GOOGX", "0001652044", MAPPA)
    check("simbolo ignoto su CIK a due classi -> ambiguo",
          r2.status == T.AMBIGUO and r2.ticker == "GOOGX", r2.status)


def test_segnaposto_risolto_e_non():
    r = T.resolve("NONE", "0000885275", MAPPA)
    check("PROVA POSITIVA: NONE su un CIK con un simbolo -> si risolve",
          r.ticker == "WBHC" and r.status == T.CORRETTO, r.status)
    check("...e reported resta il segnaposto", r.reported == "NONE")

    r2 = T.resolve("NONE", "0001652044", MAPPA)
    check("NONE su un CIK a due classi -> ambiguo, non risolto",
          r2.status == T.AMBIGUO and r2.ticker == "NONE", r2.status)


def test_cik_non_quotato():
    """Sessanta emittenti su 506 stanno qui, e per loro NONE e' il FATTO."""
    r = T.resolve("NONE", "0001925309", MAPPA)
    check("CIK assente dalla mappa -> non quotato",
          r.status == T.NON_QUOTATO, r.status)
    check("...il segnaposto si tiene", r.ticker == "NONE", r.ticker)
    check("...e non c'e' niente da dire", r.note() == "")


def test_mappa_assente_non_cambia_nulla():
    """Senza mappa il giro deve comportarsi come prima di questo codice."""
    r = T.resolve("GREE", "0001844971", {})
    check("mappa vuota -> sconosciuto", r.status == T.SCONOSCIUTO, r.status)
    check("...e il simbolo resta quello del deposito", r.ticker == "GREE")


class FakeClient:
    def __init__(self, doc): self._doc = doc
    def get_json(self, url): return self._doc


def test_load_map():
    doc = {
        "0": {"cik_str": 1844971, "ticker": "VIP", "title": "Vulcan"},
        "1": {"cik_str": 1844971, "ticker": "GREEL", "title": "Vulcan"},
        "2": {"cik_str": 1833141, "ticker": "help", "title": "Cybin"},
        "3": {"cik_str": 999, "ticker": "", "title": "senza simbolo"},
        "4": {"rotta": True},
    }
    m = T.load_map(FakeClient(doc))
    check("due simboli sullo stesso CIK si accorpano",
          m["0001844971"] == frozenset({"VIP", "GREEL"}), str(m.get("0001844971")))
    check("il CIK e' a dieci cifre", "0001833141" in m, str(sorted(m)))
    check("il simbolo e' in maiuscolo", m["0001833141"] == frozenset({"HELP"}))
    check("una riga senza simbolo non entra", "0000000999" not in m)
    check("una riga rotta non fa esplodere", len(m) == 2, str(len(m)))

    class Rotto:
        def get_json(self, url): raise RuntimeError("rete giu'")
    check("se la rete cade la mappa e' vuota, non un'eccezione",
          T.load_map(Rotto()) == {})
    check("documento vuoto -> mappa vuota", T.load_map(FakeClient(None)) == {})


class FintoCluster:
    def __init__(self, cik, ticker):
        self.issuer_cik, self.ticker = cik, ticker


def test_apply_to_clusters():
    doc = {
        "0": {"cik_str": 1833141, "ticker": "HELP", "title": "Cybin"},
        "1": {"cik_str": 1844971, "ticker": "VIP", "title": "Vulcan"},
        "2": {"cik_str": 1844971, "ticker": "GREEL", "title": "Vulcan"},
    }
    cl = [
        FintoCluster("0001833141", "CYBN"),    # da correggere
        FintoCluster("0001844971", "GREE"),    # ambiguo
        FintoCluster("0001925309", "NONE"),    # non quotato
        FintoCluster("0001833141", "HELP"),    # gia' valido
    ]
    counts = T.apply_to_clusters(cl, FakeClient(doc))

    check("PROVA POSITIVA: il cluster stantio viene corretto sul posto",
          cl[0].ticker == "HELP", cl[0].ticker)
    check("l'ambiguo NON viene toccato", cl[1].ticker == "GREE", cl[1].ticker)
    check("il non quotato NON viene toccato", cl[2].ticker == "NONE")
    check("il valido NON viene toccato", cl[3].ticker == "HELP")
    check("i conteggi tornano",
          counts == {T.CORRETTO: 1, T.AMBIGUO: 1, T.NON_QUOTATO: 1, T.VALIDO: 1},
          str(counts))


test_normalize()
test_placeholder()
test_valido()
test_separatore_non_e_una_differenza()
test_stantio_univoco()
test_stantio_ambiguo_non_si_indovina()
test_segnaposto_risolto_e_non()
test_cik_non_quotato()
test_mappa_assente_non_cambia_nulla()
test_load_map()
test_apply_to_clusters()

if __name__ == "__main__":
    sys.exit(report("ALL TICKER TESTS PASSED"))
