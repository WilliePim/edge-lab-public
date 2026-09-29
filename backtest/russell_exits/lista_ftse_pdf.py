"""Russell 2000, uscite verso il basso — lettura delle liste FTSE Russell delle cancellazioni (PDF).

Solo libreria standard (zlib, re): testo dei flussi compressi, pezzi raggruppati per altezza, colonne per posizione
orizzontale (società < 230, simbolo 230-360, settore ≥ 360). Nessun parser PDF installato: nessuna dipendenza nuova.

**Due modi di posizionare il testo.** I PDF del 2025 usano la matrice di testo (`1 0 0 1 x y Tm`), quelli del 2024
e prima l'offset di riga (`x y Td`) dentro un blocco `BT`/`ET` appena aperto, che lì vale come posizione assoluta.
Si accettano tutti e due: le colonne restano le stesse, cambia solo come è scritta la posizione.

**Il titolo non sta nel testo delle pagine** ma nei metadati del documento (`titolo_e_data`), e lì si legge anche la
data di creazione: è quella che distingue la lista finale della ricostituzione dalle preliminari di maggio.
"""
from __future__ import annotations

import collections
import re
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PDF = ROOT / "state" / "backfill" / "russell" / "ru3000-deletions-20250627.pdf"
COL_SIMBOLO, COL_SETTORE = 230, 360
#  `1 0 0 1 x y Tm` (2025) oppure `x y Td` (2024 e prima): in questi file il secondo segue sempre un `BT` appena
#  aperto, quindi l'offset vale come posizione assoluta.
POSIZIONE = re.compile(rb"(?:1 0 0 1 )?([\d.]+) ([\d.]+) T[md]\b")


def _stringhe(b):
    out, i, n = [], 0, len(b)
    while i < n:
        if b[i:i + 1] == b"(":
            prof, j, s = 1, i + 1, bytearray()
            while j < n and prof:
                c = b[j:j + 1]
                if c == b"\\" and j + 1 < n:
                    s += b[j + 1:j + 2]
                    j += 2
                    continue
                if c == b"(":
                    prof += 1
                elif c == b")":
                    prof -= 1
                    if prof == 0:
                        break
                s += c
                j += 1
            out.append(bytes(s))
            i = j + 1
        else:
            i += 1
    return out


def righe(pdf=PDF):
    raw = Path(pdf).read_bytes()
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        try:
            d = zlib.decompress(m.group(1))
        except zlib.error:
            continue
        if b"TJ" not in d and b"Tj" not in d:
            continue
        per_y = collections.defaultdict(list)
        for blk in re.finditer(rb"BT(.*?)ET", d, re.S):
            tm = POSIZIONE.search(blk.group(1))
            if tm:
                per_y[round(float(tm.group(2)))].append((float(tm.group(1)), b"".join(_stringhe(blk.group(1))).decode("latin-1")))
        for y in sorted(per_y, reverse=True):
            pezzi = sorted(per_y[y])
            soc = "".join(t for x, t in pezzi if x < COL_SIMBOLO).strip()
            sim = "".join(t for x, t in pezzi if COL_SIMBOLO <= x < COL_SETTORE).strip()
            sett = "".join(t for x, t in pezzi if x >= COL_SETTORE).strip()
            if soc and sim and soc != "Company" and re.fullmatch(r"[A-Z0-9.\-]{1,8}", sim):
                out.append({"societa": soc, "simbolo": sim, "settore": sett})
    return out


#  I metadati del documento: lì stanno il titolo e la data di creazione, che il testo delle pagine non porta.
_TITOLO = re.compile(rb"/Title\s*\(([^)]{0,200})\)")
_DATA = re.compile(rb"/CreationDate\s*\(D:(\d{8})")


def titolo_e_data(pdf=PDF) -> tuple[list[str], str | None]:
    """(titoli dichiarati nel documento, data di creazione AAAAMMGG).

    Serve a distinguere la lista **finale** della ricostituzione dalle preliminari di maggio: il titolo lo dice
    quando c'è («Final Russell 3000 Deletions - Reconstitution 2025», «USADeletionsFinal»), la data sempre."""
    grezzo = Path(pdf).read_bytes()
    titoli = [m.group(1).decode("latin-1", "replace").strip() for m in _TITOLO.finditer(grezzo)]
    data = _DATA.search(grezzo)
    return [t for t in titoli if t], (data.group(1).decode() if data else None)


if __name__ == "__main__":
    import sys
    percorso = sys.argv[1] if len(sys.argv) > 1 else PDF
    titoli, data = titolo_e_data(percorso)
    r = righe(percorso)
    print("titoli:", titoli)
    print("creato il:", data)
    print(len(r), "righe;", r[:2], r[-1:])
