"""Il registro dei verdetti: quello che lo scanner NON ha il diritto di fare.

Le proprieta' asserite qui sono quasi tutte negative, ed e' voluto. Un verdetto
e' un giudizio, il confine di CLAUDE.md dice che i giudizi non nascono dallo
scanner, e un registro che si lasciasse scrivere per default o modificare in
place sarebbe il modo esatto in cui quel confine viene aggirato senza che
nessuno se ne accorga.
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, raises, report

from form4_scanner import verdicts as v

BASE = dict(cik="9999999", ticker="XMPL", verdict="HOLD",
            thesis="una tesi", invalidation=["close below 10"])


def ledger():
    return Path(tempfile.mkdtemp()) / "verdicts.jsonl"


print("[verdicts] i tre campi che non si possono dedurre")
p = ledger()
check("un verdetto fuori dalle quattro classi e' rifiutato",
      raises(lambda: v.add(**{**BASE, "verdict": "MAYBE"}, path=p), ValueError))
check("senza tesi e' rifiutato",
      raises(lambda: v.add(**{**BASE, "thesis": "  "}, path=p), ValueError))
check("senza invalidazione e' rifiutato",
      raises(lambda: v.add(**{**BASE, "invalidation": []}, path=p), ValueError))
check("...e dopo tre rifiuti il registro non esiste ancora", not p.exists())

print("[verdicts] append-only: un cambio e' una riga nuova, mai una modifica")
p = ledger()
first = v.add(**BASE, price_at_verdict=20.3, path=p, on=date(2026, 9, 1))
second = v.add(**{**BASE, "verdict": "SELL", "thesis": "cambiata"},
               path=p, on=date(2026, 11, 12))
rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]
check("due righe, non una riscritta", len(rows) == 2, str(len(rows)))
check("la prima e' intatta", rows[0]["verdict"] == "HOLD", rows[0]["verdict"])
check("la seconda supersede la prima",
      second["supersedes"] == first["id"], str(second["supersedes"]))
check("gli id sono diversi", first["id"] != second["id"])

cur = v.current(p)
check("in vigore ce n'e' uno solo", len(cur) == 1, str(len(cur)))
check("...ed e' il piu' recente", cur["9999999"]["verdict"] == "SELL",
      cur["9999999"]["verdict"])
check("il superato resta leggibile nel file",
      any(r["verdict"] == "HOLD" for r in rows))

print("[verdicts] il registro vive in data/, che git non ignora")
check("il percorso di default sta sotto data/",
      v.LEDGER.parent.name == "data", str(v.LEDGER))

print("[verdicts] le invalidazioni: solo prezzo contro numero")
ok, why = v.check_invalidation("close below 18.50", 17.0)
check("una soglia pura si verifica", ok is True, str((ok, why)))
ok, why = v.check_invalidation("close below 18.50", 20.0)
check("...e sa anche dire di no", ok is False, str((ok, why)))

#  La proprieta' che conta: una congiunzione NON si chiude sulla meta' che si
#  sa leggere. Dichiarare scattata "close below 18.50 without news" perche' il
#  prezzo e' sceso vorrebbe dire decidere che "senza notizie" vale, e quella e'
#  una decisione dell'operatore.
ok, why = v.check_invalidation("close below 18.50 without news", 17.0)
check("una congiunzione non si chiude sul solo prezzo", ok is None, str(ok))
check("...ma il fatto sul prezzo viene comunque riportato",
      "17.00" in why and "18.50" in why, why)
check("...e dice cosa resta da verificare a mano",
      "without news" in why, why)

ok, why = v.check_invalidation("Q3 segment growth < 7%", 17.0)
check("una condizione che non parla di prezzo non e' verificabile",
      ok is None, str((ok, why)))
ok, why = v.check_invalidation("close below 18.50", None)
check("senza prezzo non si verifica niente", ok is None, str((ok, why)))

print("[verdicts] lo scanner non scrive questo file da solo")
import ast

src = Path(__file__).resolve().parents[1] / "form4_scanner"
writers = []
for f in src.glob("*.py"):
    if f.name in ("verdicts.py", "cli.py"):
        continue                       # il modulo stesso, e la CLI che lo detta
    tree = ast.parse(f.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and n.attr == "add":
            if isinstance(n.value, ast.Name) and "verdict" in n.value.id.lower():
                writers.append(f.name)
check("nessun modulo dello scan chiama verdicts.add", not writers, str(writers))

if __name__ == "__main__":
    sys.exit(report("ALL VERDICT TESTS PASSED"))
