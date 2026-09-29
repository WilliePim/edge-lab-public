"""Ogni ADR citato nel repo esiste in DECISIONS.md.

Il 22 settembre 2026 si è scoperto che la pre-registrazione del Russell citava ADR-040, 068, 069 e 070 (numeri della
copia pubblica, rinumerata) per filtri, peer, ingressi e placebo, e che quelle decisioni non erano mai state scritte:
il 040 in `DECISIONS.md` è un'altra cosa (i prezzi EODHD), e 068-070 non sono mai esistiti. Nessuno se n'era
accorto per sei giorni. Questo test lo avrebbe detto il giorno stesso.

**Cosa conta come citazione:** `ADR-NNN` in un file `.md` o `.py` del repo. Fuori: `edgar_llm/`, che ha la sua serie
di ADR in `edgar_llm/docs/adr/`, e le cartelle di dati e cache. Anche `market-data/` ha la sua serie
(`market-data/docs/adr/`), citata come «ADR 00N» con lo spazio: la regex non la prende. Non sono citazioni di questo
repo gli ADR del repo svedese, scritti «ADR-0NN di fi-insider-scanner».

**Le citazioni sbagliate note** sono elencate qui sotto, ciascuna col motivo: sono i rimandi della pre-registrazione,
che per regola non si riscrive e ha una riga di errata, e i punti di `DECISIONS.md` che raccontano l'errore. Una
citazione sbagliata nuova fa fallire il test.

Nessuna rete, nessun dato: solo lettura dei sorgenti.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

ROOT = Path(__file__).resolve().parents[1]
ESCLUSE = {".venv", "venv", "state", ".edgar_cache", ".llm_cache", "__pycache__", ".git", "out", "logs",
           "node_modules", "edgar_llm"}
CITAZIONE = re.compile(r"\bADR-(\d{3})\b(?! di fi-insider-scanner)")
INTESTAZIONE = re.compile(r"^## ADR-(\d{3})\b", re.M)

#  (file relativo alla radice, numero) -> perché la citazione può non esistere o puntare altrove
NOTE = {
    ("backtest/russell_exits/2026-09-16_preregistrazione.md", "068"): "errata del 22-09: peer è ADR-043",
    ("backtest/russell_exits/2026-09-16_preregistrazione.md", "069"): "errata del 22-09: ingressi è ADR-044",
    ("backtest/russell_exits/2026-09-16_preregistrazione.md", "070"): "errata del 22-09: placebo è ADR-045",
    #  DECISIONS.md della copia pubblica non cita i numeri sbagliati: ADR-041 e ADR-042..045 raccontano l'errore
    #  senza scriverli, quindi qui non servono eccezioni per DECISIONS.md.
}


def sorgenti():
    for p in sorted(ROOT.rglob("*")):
        if p.suffix not in (".md", ".py") or not p.is_file():
            continue
        if any(parte in ESCLUSE for parte in p.relative_to(ROOT).parts):
            continue
        yield p


def main() -> int:
    scritti = set(INTESTAZIONE.findall((ROOT / "DECISIONS.md").read_text(encoding="utf-8")))
    check("DECISIONS.md ha delle ADR", len(scritti) > 50, len(scritti))

    mancanti, citazioni, note_usate = [], 0, set()
    for p in sorgenti():
        if p.resolve() == Path(__file__).resolve():
            continue                                         # questo file cita i numeri sbagliati apposta
        rel = p.relative_to(ROOT).as_posix()
        testo = p.read_text(encoding="utf-8", errors="replace")
        for n in sorted(set(CITAZIONE.findall(testo))):
            citazioni += 1
            if n in scritti:
                continue
            if (rel, n) in NOTE:
                note_usate.add((rel, n))
                continue
            mancanti.append("{} cita ADR-{}".format(rel, n))
    check("ogni ADR citato esiste in DECISIONS.md ({} file-citazioni lette)".format(citazioni), not mancanti,
          "; ".join(mancanti[:10]))

    #  Una nota che non serve più (la citazione è sparita o l'ADR è stato scritto) va tolta: altrimenti la lista
    #  delle eccezioni cresce e nasconde.
    inutili = sorted(set(NOTE) - note_usate)
    check("nessuna eccezione inutile nella lista delle citazioni sbagliate note", not inutili,
          "; ".join("{} ADR-{}".format(*x) for x in inutili))

    #  I numeri giusti che l'errata promette devono esistere.
    for n, cosa in (("042", "filtri"), ("043", "peer"), ("044", "ingressi"), ("045", "placebo")):
        check("l'errata della pre-registrazione rimanda ad ADR-{} ({}), che esiste".format(n, cosa), n in scritti)
    return report("ADR CITATI ESISTENTI")


if __name__ == "__main__":
    sys.exit(main())
