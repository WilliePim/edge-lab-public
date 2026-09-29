"""Il veto sulla diluizione e' implementato ma SPENTO per default, finche' il predicato non e' validato.

Spento: il predicato si calcola e si mostra (flag, contesto), ma nessuna scheda e' `blocked`, quindi nessun nome e'
fermato ne' nascosto. Acceso esplicitamente (EDGE_LAB_DILUTION_VETO=1): il comportamento storico, cioe' la scheda e'
`blocked` e il flag dice DILUTION VETO. Il percorso completo (scan, report, confronto) sta in test_e2e.py,
test_report.py e test_compare.py, che accendono il veto dove provano il comportamento storico.

Nessuna rete, nessun dato.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner.dilution import BLOCKED, VETO_ENV, DilutionReport, veto_attivo
from form4_scanner.flags import Card, dilution_flags


def scheda_con_predicato_bloccante():
    rep = DilutionReport(issuer_cik="1", verdict=BLOCKED, reasons=["424B5 priced 3d after the last buy"])
    c = Card(ticker="AAA", issuer_name="AAA CORP", issuer_cik="1", dilution=rep)
    dilution_flags(c, rep)
    return rep, c


os.environ.pop(VETO_ENV, None)
print("[veto] default: spento")
check("senza variabile d'ambiente il veto e' spento", veto_attivo() is False)
rep, c = scheda_con_predicato_bloccante()
check("il predicato resta BLOCKED (e' informazione)", rep.blocked is True)
check("...ma la scheda non e' fermata", c.blocked is False)
check("...e il flag dice che il veto e' spento", any("veto off" in f for f in c.flags), str(c.flags))
check("...senza la parola VETO del comportamento acceso", not any("DILUTION VETO" in f for f in c.flags),
      str(c.flags))
for v in ("", "0", "no", "off", "false"):
    os.environ[VETO_ENV] = v
    check("valore {!r}: spento".format(v), veto_attivo() is False)

print("[veto] acceso esplicitamente: comportamento storico")
for v in ("1", "true", "si", "yes", "on", " ON "):
    os.environ[VETO_ENV] = v
    check("valore {!r}: acceso".format(v), veto_attivo() is True)
os.environ[VETO_ENV] = "1"
rep, c = scheda_con_predicato_bloccante()
check("acceso: la scheda e' fermata", c.blocked is True)
check("acceso: il flag e' DILUTION VETO", any(f.startswith("DILUTION VETO") for f in c.flags), str(c.flags))
os.environ.pop(VETO_ENV, None)

sys.exit(report("ALL DILUTION VETO TESTS PASSED"))
