"""I documenti citano il codice riga per riga: qui si controlla che le righe esistano.

RULES.md dichiara di sé: «se il codice cambia e questo file no, questo file è
sbagliato». Era vero nel senso peggiore -- cinque citazioni su dieci puntavano a
una riga diversa da quella promessa, e una a un file cancellato. Le citazioni non
si consumano perché qualcuno è distratto: si consumano perché il codice si sposta,
e niente le rilegge.

Questo lo rilegge. Per ogni collegamento `(percorso#Lnn)` nei documenti:
  - il file deve esistere e avere almeno quella riga;
  - se la riga del documento nomina un simbolo fra apici inversi, e quel simbolo
    esiste nel file citato, deve comparire entro ±3 righe dal bersaglio.

La tolleranza di tre righe esiste perché una citazione può puntare alla firma o
al corpo di una funzione; più in là si tratta di un'altra cosa. Il simbolo si
controlla solo se esiste nel file: così una riga che nomina due cose diverse non
fa fallire la citazione di quella giusta.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

RADICE = Path(__file__).resolve().parents[1]
DOCUMENTI = ("README.md", "RULES.md", "CLAUDE.md", "docs/OVERVIEW.md")
TOLLERANZA = 3
#  [testo](percorso#Lnn) -- il percorso è relativo alla radice del repo
LEGAME = re.compile(r"\[([^\]]+)\]\(([^)\s]+?\.py)#L(\d+)\)")
#  Un simbolo nel testo del collegamento: `nome_funzione` oppure file.py:nn
SIMBOLO = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")


controllati = verificati_col_simbolo = 0
for nome in DOCUMENTI:
    doc = RADICE / nome
    if not doc.exists():
        continue
    for riga_doc in doc.read_text(encoding="utf-8").splitlines():
        simboli = SIMBOLO.findall(riga_doc)
        for etichetta, percorso, riga in LEGAME.findall(riga_doc):
            controllati += 1
            #  L'etichetta quasi sempre ripete il numero di riga («parse.py:217»).
            #  Se lo ripete, deve dire la stessa cosa del collegamento: e' la
            #  coppia che si scolla per prima quando si aggiorna a mano solo una
            #  delle due.
            scritta = re.search(r":(\d+)\s*$", etichetta.strip("`* "))
            if scritta:
                check(f"{nome}: l'etichetta «{etichetta}» e il collegamento dicono la stessa riga",
                      scritta.group(1) == riga, f"etichetta {scritta.group(1)}, link {riga}")
            f = RADICE / percorso
            if not check(f"{nome}: {percorso} esiste", f.exists(), percorso):
                continue
            righe = f.read_text(encoding="utf-8").splitlines()
            n = int(riga)
            if not check(f"{nome}: {percorso}#L{n} è dentro il file", n <= len(righe),
                         f"{len(righe)} righe"):
                continue
            corpo = "\n".join(righe)
            vicino = "\n".join(righe[max(0, n - 1 - TOLLERANZA):n + TOLLERANZA])
            for atteso in simboli:
                if atteso not in corpo:          # la riga nomina altro: non è questa citazione
                    continue
                verificati_col_simbolo += 1
                check(f"{nome}: {percorso}#L{n} contiene davvero `{atteso}`",
                      atteso in vicino, repr(righe[n - 1][:70]))

check("i documenti citano il codice (se questo scende a zero, la regex è rotta)",
      controllati >= 10, str(controllati))
check("...e su alcune si verifica anche il simbolo nominato",
      verificati_col_simbolo >= 3, f"{verificati_col_simbolo} su {controllati}")
print(f"\n{controllati} citazioni controllate, {verificati_col_simbolo} col simbolo")

sys.exit(report("ALL CITATION TESTS PASSED"))
