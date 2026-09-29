"""La colonna `emissione` non deve poter cambiare niente.

E' l'unico punto in cui un'estrazione LLM tocca la pipeline, e il vincolo di
CLAUDE.md sul confine fra scanner e giudizio dice cosa le e' permesso: comparire
accanto al verdetto, mai al posto suo. Queste asserzioni sono la forma
eseguibile di edgar_llm/docs/adr/004-mai-un-cancello.md.

Nessuna rete, nessuna chiave: si verifica il comportamento QUANDO l'estrazione
non e' disponibile, che e' il caso da difendere -- il giro delle 8:00 gira su
uno scheduler e non deve fermarsi perche' un'API non risponde.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report, section

from form4_scanner import report as report_mod
from form4_scanner.flags import Card


def card(cik="216228", ticker="ITT", score=2):
    c = Card(issuer_cik=cik, issuer_name="ITT Inc.", ticker=ticker)
    c.v3 = {"score": score, "cluster": True, "director": True}
    c.context = {"total_value": 250000, "first_buy_date": "2026-08-17",
                 "dilution": "BLOCKED"}
    c.inputs = {"cluster": {"buyers_in_window": 2}}
    return c


section("colonna assente = report di prima")

check("senza client non si interroga nessuno",
      report_mod.issuance_column([card()], None, date(2026, 9, 2)) == {})
check("senza emittenti nuovi non si interroga nessuno",
      report_mod.issuance_column([], object(), date(2026, 9, 2)) == {})

#  Il caso vero dello scheduler: package presente, chiave assente. Deve uscire
#  {} PRIMA di scaricare una dozzina di documenti per scriverci UNKNOWN sopra.
import os                                                        # noqa: E402

salvati = {k: os.environ.pop(k, None) for k in
           ("ANTHROPIC_API_KEY", "EDGAR_LLM_MODE", "EDGAR_LLM_DAILY")}
try:
    got = report_mod.issuance_column([card()], object(), date(2026, 9, 2))
    check("senza chiave API la colonna non parte affatto", got == {}, str(got))

    #  E anche CON la chiave: averla non e' il consenso a spendere ogni
    #  mattina per una colonna che nessuna eval ha ancora validato.
    os.environ["ANTHROPIC_API_KEY"] = "una-chiave-finta"
    got = report_mod.issuance_column([card()], object(), date(2026, 9, 2))
    check("con la chiave ma senza EDGAR_LLM_DAILY la colonna resta spenta",
          got == {}, str(got))

    #  L'interruttore acceso porta la funzione oltre il controllo: qui non
    #  serve che l'estrazione riesca, serve che NON si fermi prima.
    os.environ["EDGAR_LLM_DAILY"] = "1"
    os.environ["EDGAR_LLM_MODE"] = "replay"
    got = report_mod.issuance_column([card()], object(), date(2026, 9, 2))
    check("con l'interruttore acceso la funzione ci prova",
          isinstance(got, dict), str(got))
finally:
    for k, v in salvati.items():
        os.environ.pop(k, None)
        if v is not None:
            os.environ[k] = v


section("la riga rende un trattino quando non c'e' estrazione")

row = report_mod._row(card(), None, {})
check("dieci colonne, l'ultima e' il verdetto", row.count("|") == 11, row)
check("emissione a trattino", "| — | — |" in row, row)

row_pieno = report_mod._row(card(), None, {"216228": "M&A_issuance (high)"})
check("il tipo estratto compare in colonna",
      "M&A_issuance (high)" in row_pieno, row_pieno)
check("e non tocca il punteggio", row_pieno.startswith("| 2 |"), row_pieno)


section("l'estrazione non ha diritto di bloccare ne' di ordinare")

#  Il confine, verificato sull'AST invece che a occhio: nessun modulo dello
#  scanner puo' assegnare `blocked`, `v3` o riordinare a partire da un'estrazione.
import ast                                                       # noqa: E402

pkg = Path(__file__).resolve().parents[1] / "form4_scanner"
src = (pkg / "report.py").read_text(encoding="utf-8")
tree = ast.parse(src)

fn = next(n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "issuance_column")
assegnati = {t.attr for n in ast.walk(fn) for t in ast.walk(n)
             if isinstance(t, ast.Attribute) and isinstance(t.ctx, ast.Store)}
check("issuance_column non assegna nessun attributo di Card",
      not (assegnati & {"blocked", "v3", "flags", "dilution", "context"}),
      str(assegnati))

chiamate = {n.func.attr for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
check("non ordina niente", "sort" not in chiamate, str(chiamate))

#  E il modulo dell'estrazione non deve nemmeno conoscere `blocked`.
for f in (pkg.parent / "edgar_llm").glob("*.py"):
    txt = f.read_text(encoding="utf-8", errors="replace")
    check("edgar_llm/{} non nomina blocked".format(f.name),
          "blocked" not in txt.lower() or "adr" in txt.lower(),
          f.name)

if __name__ == "__main__":
    sys.exit(report("ALL ISSUANCE COLUMN TESTS PASSED"))
