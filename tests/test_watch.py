"""Prove per la sorveglianza dei nomi singoli.

Il punto di questa suite: OGNI CONTROLLO DEVE DIMOSTRARE DI SCATTARE. Un alert
che non scatta mai e un alert che non ha niente da dire hanno lo stesso
aspetto, ed e' il guasto per cui questo repository ha gia' scritto un
postmortem. Quindi per ogni filtro c'e' una prova positiva -- un caso che DEVE
produrre un riscontro -- accanto a quella negativa.

Il caso che conta di piu' e' il filtro di ruolo su un emittente (segnaposto AAA)
i cui acquisti sono tutti di un 10% owner, quindi un filtro
rotto in un senso segnalerebbe il fondo, e rotto nell'altro non segnalerebbe
mai il management.
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner import watch as W


def owner_xml(owners, code="P", ad="A", shares=100.0, price=10.0,
              deriv=False, plan=False):
    """Un ownershipDocument minimo ma vero, con gli elementi che il parser cerca."""
    ro = "".join(
        """<reportingOwner>
             <reportingOwnerId>
               <rptOwnerCik>{cik}</rptOwnerCik>
               <rptOwnerName>{name}</rptOwnerName>
             </reportingOwnerId>
             <reportingOwnerRelationship>
               <isDirector>{d}</isDirector>
               <isOfficer>{o}</isOfficer>
               <isTenPercentOwner>{t}</isTenPercentOwner>
               <officerTitle>{title}</officerTitle>
             </reportingOwnerRelationship>
           </reportingOwner>""".format(
            cik=o["cik"], name=o["name"],
            d=1 if o.get("director") else 0,
            o=1 if o.get("officer") else 0,
            t=1 if o.get("ten") else 0,
            title=o.get("title", ""),
        )
        for o in owners
    )
    table = "derivativeTable" if deriv else "nonDerivativeTable"
    row = "derivativeTransaction" if deriv else "nonDerivativeTransaction"
    return """<?xml version="1.0"?>
<ownershipDocument>
  <aff10b5One>{plan}</aff10b5One>
  <issuer>
    <issuerCik>0000000001</issuerCik>
    <issuerName>TEST ISSUER</issuerName>
    <issuerTradingSymbol>TEST</issuerTradingSymbol>
  </issuer>
  {ro}
  <{table}>
    <{row}>
      <securityTitle><value>Common</value></securityTitle>
      <transactionDate><value>2026-08-10</value></transactionDate>
      <transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>{shares}</value></transactionShares>
        <transactionPricePerShare><value>{price}</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>{ad}</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>1000</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
      <ownershipNature>
        <directOrIndirectOwnership><value>D</value></directOrIndirectOwnership>
      </ownershipNature>
    </{row}>
  </{table}>
</ownershipDocument>""".format(ro=ro, table=table, row=row, code=code,
                               shares=shares, price=price, ad=ad,
                               plan=1 if plan else 0)


class FakeClient:
    """Una storia di depositi scritta a mano, piu' l'XML di ciascuno."""

    def __init__(self, filings=(), xml_by_acc=None):
        self._filings = list(filings)      # [(form, "YYYY-MM-DD", accession)]
        self._xml = dict(xml_by_acc or {})

    def submissions(self, cik):
        return {
            "filings": {
                "recent": {
                    "form": [f for f, _, _ in self._filings],
                    "filingDate": [d for _, d, _ in self._filings],
                    "accessionNumber": [a for _, _, a in self._filings],
                },
                "files": [],
            }
        }

    def get_json(self, url):
        return None

    def ownership_xml(self, cik, accession):
        return self._xml.get(accession)


DIRECTOR = {"cik": "0000000001", "name": "Rossi Mario", "director": True}
OFFICER = {"cik": "0000000002", "name": "Bianchi Anna", "officer": True,
           "title": "CFO"}
TENPCT = {"cik": "0001166152", "name": "FONDO ACCUMULATORE LLC", "ten": True}
DIR_AND_TEN = {"cik": "0000000003", "name": "Verdi Luca", "director": True,
               "ten": True}


# ---------------------------------------------------------------- caricamento

def test_load():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "watch.json"

        check("file assente non e' un errore", W.load_watches(p) == [])

        p.write_text(json.dumps({
            "lookback_days": 45,
            "watches": [
                {"id": "a", "cik": "0000000001", "kind": "form4_buys",
                 "roles": "management"},
                {"id": "b", "cik": "0000000002", "kind": "filings",
                 "forms": ["s-3", "424B5"], "lookback_days": 90},
                {"id": "c", "cik": "0000000009", "kind": "inventato"},
                {"id": "d", "kind": "filings"},
            ],
        }), encoding="utf-8")
        ws = W.load_watches(p)

        check("le sorveglianze valide entrano, le altre no", len(ws) == 2,
              str([w.id for w in ws]))
        check("genere sconosciuto scartato", "c" not in {w.id for w in ws})
        check("senza cik scartata", "d" not in {w.id for w in ws})

        a = {w.id: w for w in ws}
        check("il default di file si applica", a["a"].lookback_days == 45,
              str(a["a"].lookback_days))
        check("la singola sorveglianza lo sovrascrive",
              a["b"].lookback_days == 90, str(a["b"].lookback_days))
        check("le forme si normalizzano in maiuscolo",
              a["b"].forms == ("S-3", "424B5"), str(a["b"].forms))

        p.write_text("{ non json", encoding="utf-8")
        check("file illeggibile non alza", W.load_watches(p) == [])


# --------------------------------------------------------------------- forme

FILINGS = [
    ("S-3", "2026-08-20", "0000000000-26-000001"),
    ("S-8 POS", "2026-08-21", "0000000000-26-000002"),
    ("424B5", "2026-06-01", "0000000000-26-000003"),
]


def test_filings():
    c = FakeClient(FILINGS)
    w = W.Watch(id="w", cik="0000000002", ticker="BBB", name="n",
                kind="filings", forms=("S-3", "424B5", "POS AM"))

    hits = W.check_filings(c, w, "2026-08-01")
    forms = sorted(h.form for h in hits)

    check("PROVA POSITIVA: la forma cercata scatta", "S-3" in forms, str(forms))
    check("la forma non cercata non scatta", "S-8 POS" not in forms, str(forms))
    check("fuori finestra non scatta", "424B5" not in forms, str(forms))
    check("il link punta al deposito",
          hits[0].url.endswith("0000000000-26-000001-index.htm"), hits[0].url)


# --------------------------------------------------------------------- ruolo

def test_roles():
    accs = {
        "A": owner_xml([TENPCT]),
        "B": owner_xml([DIRECTOR]),
        "C": owner_xml([OFFICER]),
        "D": owner_xml([DIR_AND_TEN]),
        "E": owner_xml([DIRECTOR], code="A"),          # attribuzione, non acquisto
        "F": owner_xml([DIRECTOR], plan=True),         # piano 10b5-1
        "G": owner_xml([DIRECTOR], deriv=True),        # derivato
        "H": owner_xml([DIRECTOR], ad="D"),            # cessione
    }
    filings = [("4", "2026-08-10", k) for k in accs]
    c = FakeClient(filings, accs)

    w_any = W.Watch(id="w", cik="0000000001", ticker="AAA", name="n",
                    kind="form4_buys", roles="any")
    w_mgmt = W.Watch(id="w", cik="0000000001", ticker="AAA", name="n",
                     kind="form4_buys", roles="management")

    got_any = {h.accession for h in W.check_form4_buys(c, w_any, "2026-01-01")}
    got_mgmt = {h.accession for h in W.check_form4_buys(c, w_mgmt, "2026-01-01")}

    check("PROVA POSITIVA: il director scatta", "B" in got_mgmt, str(got_mgmt))
    check("PROVA POSITIVA: l'officer scatta", "C" in got_mgmt, str(got_mgmt))
    check("il 10% owner NON scatta come management", "A" not in got_mgmt,
          str(got_mgmt))
    check("director CHE E' ANCHE 10% owner non scatta", "D" not in got_mgmt,
          str(got_mgmt))
    check("ma senza filtro il 10% owner scatta", "A" in got_any, str(got_any))

    for acc, why in (("E", "codice A, non P"), ("F", "piano 10b5-1"),
                     ("G", "derivato"), ("H", "cessione")):
        check("escluso: {}".format(why), acc not in got_any, str(got_any))


def test_is_management():
    class T:
        def __init__(self, d, o, t):
            self.is_director, self.is_officer, self.is_ten_pct = d, o, t

    check("director puro", W._is_management(T(True, False, False)))
    check("officer puro", W._is_management(T(False, True, False)))
    check("10% puro escluso", not W._is_management(T(False, False, True)))
    check("director + 10% escluso", not W._is_management(T(True, False, True)))
    check("officer + 10% escluso", not W._is_management(T(False, True, True)))
    check("nessun ruolo escluso", not W._is_management(T(False, False, False)))


# --------------------------------------------------------------------- dedup

def test_dedup_and_render():
    c = FakeClient(FILINGS)
    ws = [W.Watch(id="w", cik="0000000002", ticker="BBB", name="n",
                  kind="filings", forms=("S-3",), note="rivendita")]
    with tempfile.TemporaryDirectory() as td:
        first = W.run(c, ws, date(2026, 8, 25), td, lookback_days=30)
        check("PROVA POSITIVA: il primo giro segnala", len(first) == 1,
              str(len(first)))

        lines = W.render(first, ws)
        check("la resa ha l'intestazione", lines and lines[0] == "## Sorveglianza")
        check("la resa dice che la forma non decide la rivendita",
              any("non dice" in l for l in lines))
        check("la nota compare in tabella", any("rivendita" in l for l in lines))

        W.record_seen(td, first, date(2026, 8, 25))
        second = W.run(c, ws, date(2026, 8, 25), td, lookback_days=30)
        check("il secondo giro non ripete", second == [], str(second))
        check("nessun riscontro, nessuna sezione", W.render([], ws) == [])


def test_lookback_is_not_frozen():
    """Il default della firma non deve congelare la finestra.

    `def run(..., lookback_days=DEFAULT)` fisserebbe il valore alla definizione
    della funzione: cambiare l'attributo del modulo dopo l'import non avrebbe
    effetto, e una prova che lo alza continuerebbe a girare sulla finestra
    vecchia senza dirlo. Qui la finestra arriva dalla sorveglianza o
    dall'argomento, mai da un default catturato.
    """
    c = FakeClient(FILINGS)
    ws = [W.Watch(id="w", cik="0000000002", ticker="BBB", name="n",
                  kind="filings", forms=("424B5",), lookback_days=5)]
    with tempfile.TemporaryDirectory() as td:
        stretta = W.run(c, ws, date(2026, 8, 25), td)
        larga = W.run(c, ws, date(2026, 8, 25), td, lookback_days=120)
    check("finestra stretta: niente", stretta == [], str(stretta))
    check("PROVA POSITIVA: finestra larga: il 424B5 di giugno compare",
          len(larga) == 1, str(larga))


test_load()
test_filings()
test_roles()
test_is_management()
test_dedup_and_render()
test_lookback_is_not_frozen()

if __name__ == "__main__":
    sys.exit(report("ALL WATCH TESTS PASSED"))
