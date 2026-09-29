"""Registri append-only (una riga JSON per evento): scrittura e lettura robuste a un'interruzione a metà riga.

- `appendi(percorso, voce)`: se il file non finisce con un a capo (ultima riga troncata da un'interruzione), prima va a
  capo, poi scrive la riga. Così la riga troncata resta isolata e la nuova non si incolla a lei. JSON in ASCII: nessun
  separatore di riga Unicode dentro una riga.
- `leggi(percorso)`: righe JSON valide; quelle illeggibili si saltano e si contano.
"""
from __future__ import annotations

import json
from pathlib import Path


def appendi(percorso: Path, voce: dict) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with percorso.open("ab") as fh:
        if fh.tell() > 0:
            with percorso.open("rb") as lettore:
                lettore.seek(-1, 2)
                if lettore.read(1) != b"\n":
                    fh.write(b"\n")
        fh.write(json.dumps(voce).encode("ascii") + b"\n")


def leggi(percorso: Path) -> tuple[list[dict], int]:
    """(righe valide, righe illeggibili)."""
    if not percorso.exists():
        return [], 0
    out, illeggibili = [], 0
    for riga in percorso.read_bytes().split(b"\n"):
        riga = riga.strip().strip(b"\x00")
        if not riga:
            continue
        try:
            out.append(json.loads(riga))
        except ValueError:
            illeggibili += 1
    return out, illeggibili
