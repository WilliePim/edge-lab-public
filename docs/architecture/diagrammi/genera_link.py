"""Rigenera i link all'editor di mermaid.live nelle pagine di `docs/architecture/`.

Ogni diagramma vive in un file `.mmd` di questa cartella. Nelle pagine, il link sta nella riga subito dopo il
segnaposto `<!-- diagramma: NOME.mmd -->`: questo script la riscrive con il diagramma attuale, compresso nel formato
che l'editor legge dall'indirizzo (`#pako:`, zlib + base64 URL-safe). Solo libreria standard, nessuna rete.

    python docs/architecture/diagrammi/genera_link.py
"""
from __future__ import annotations

import base64
import json
import re
import zlib
from pathlib import Path

QUI = Path(__file__).resolve().parent
PAGINE = QUI.parent
SEGNAPOSTO = re.compile(r"^<!-- diagramma: (?P<nome>[\w.-]+\.mmd) -->$")
TESTO = "**[▶  Apri il diagramma nell'editor Mermaid]({})**"


def link(codice: str) -> str:
    stato = {"code": codice, "mermaid": json.dumps({"theme": "base"}), "autoSync": True, "updateDiagram": True,
             "rough": False, "panZoom": True}
    compresso = zlib.compress(json.dumps(stato, ensure_ascii=False).encode("utf-8"), 9)
    return "https://mermaid.live/edit#pako:" + base64.urlsafe_b64encode(compresso).decode("ascii").rstrip("=")


def main() -> int:
    aggiornati = 0
    for pagina in sorted(PAGINE.glob("*.md")):
        righe = pagina.read_text(encoding="utf-8").split("\n")
        for i, riga in enumerate(righe[:-1]):
            m = SEGNAPOSTO.match(riga.strip())
            if m:
                codice = (QUI / m.group("nome")).read_text(encoding="utf-8")
                righe[i + 1] = TESTO.format(link(codice))
                aggiornati += 1
        pagina.write_text("\n".join(righe), encoding="utf-8", newline="\n")
    print("link aggiornati:", aggiornati)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
