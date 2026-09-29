"""Controllo pre-commit di edge-lab: nessun dato di mercato, nessun file grosso, nessuna chiave API nei commit.

edge-lab contiene codice, ricerca e il package market-data; i dati EODHD vivono fuori (licenza per uso personale, niente
ridistribuzione). Questo controllo guarda i file **nella staging area**, cioè quello che il commit conterrebbe davvero,
compresi i cambi di tipo (per esempio un collegamento che diventa un file):
- estensioni di dati: .parquet, .duckdb, .gz, .feather, .arrow;
- file `.env` (resta ammesso `.env.example`, che ha solo i nomi);
- file sopra 5 MB;
- stringhe che somigliano alla chiave EODHD: la chiave vera letta dall'ambiente o da `.env`, la forma
  «esadecimale.cifre» delle chiavi EODHD, `api_token=<valore>` ed `EODHD_API_KEY=<valore>`. I file UTF-16 (quelli che
  PowerShell 5.1 scrive con `>`) si controllano anche decodificati;
- sottomoduli e repo annidati (gitlink): bloccati, il loro contenuto non si può controllare da qui.

Il messaggio dice file e motivo, mai la stringa trovata. Attivazione: `git config core.hooksPath .githooks`.
Decisione: market-data/docs/adr/002-protezioni-git.md.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024
SUFFISSI_DATI = (".parquet", ".duckdb", ".duckdb.wal", ".gz", ".feather", ".arrow")
FORME_CHIAVE = (
    (re.compile(rb"(?<![0-9A-Za-z])[0-9a-fA-F]{12,16}\.[0-9]{6,10}(?![0-9A-Za-z])"),
     "stringa con la forma di una chiave EODHD"),
    (re.compile(rb"api_token=(?!demo\b)[A-Za-z0-9.]{8,}"), "api_token con un valore"),
    (re.compile(rb"EODHD_API_KEY\s*[=:]\s*['\"]?[A-Za-z0-9.]{8,}"), "EODHD_API_KEY con un valore"),
)


def chiavi_note(radice: Path) -> list[bytes]:
    """Valori reali di EODHD_API_KEY (ambiente e `.env` alla radice), per il confronto esatto. Legge `.env` in modo
    tollerante (BOM, spazi attorno a `=`, `export`), almeno quanto `market_data.config.leggi_env`."""
    valori = [os.environ.get("EODHD_API_KEY", "")]
    env = radice / ".env"
    if env.is_file():
        for riga in env.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            riga = riga.strip()
            if riga.startswith("export "):
                riga = riga[len("export "):].strip()
            if "=" in riga and riga.split("=", 1)[0].strip() == "EODHD_API_KEY":
                valori.append(riga.split("=", 1)[1].strip().strip("'\""))
    return [v.encode() for v in valori if len(v) >= 8]


def varianti(contenuto: bytes) -> list[bytes]:
    """Il contenuto così com'è e, se sembra UTF-16 (BOM o molti byte nulli), anche decodificato in UTF-8."""
    out = [contenuto]
    if contenuto[:2] in (b"\xff\xfe", b"\xfe\xff") or (contenuto and contenuto.count(0) > len(contenuto) // 4):
        for codifica in ("utf-16", "utf-16-le", "utf-16-be"):
            try:
                out.append(contenuto.decode(codifica).encode("utf-8"))
                break
            except UnicodeDecodeError:
                continue
    return out


def problemi(percorso: str, dimensione: int, contenuto: bytes | None, chiavi: list[bytes]) -> list[str]:
    """Motivi per cui il file non può entrare nel commit (lista vuota se può)."""
    out = []
    nome = percorso.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if nome.endswith(SUFFISSI_DATI):
        out.append("file di dati")
    if nome == ".env" or (nome.startswith(".env.") and nome != ".env.example"):
        out.append("file .env con segreti")
    if dimensione > MAX_BYTES:
        out.append("sopra 5 MB ({:.1f} MB)".format(dimensione / 1024 / 1024))
    if contenuto is not None:
        testi = varianti(contenuto)
        if any(k in x for k in chiavi for x in testi):
            out.append("contiene la chiave API")
        for regola, motivo in FORME_CHIAVE:
            if any(regola.search(x) for x in testi):
                out.append(motivo)
    return out


def _git(*args: str) -> bytes:
    return subprocess.run(("git",) + args, check=True, capture_output=True).stdout


def file_in_staging() -> list[tuple[str, int, bytes | None, bool]]:
    """(percorso, dimensione, contenuto o None sopra 5 MB, è un gitlink)."""
    nomi = [n for n in _git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMRT").decode("utf-8").split("\0") if n]
    out = []
    for n in nomi:
        modo = _git("ls-files", "-s", "-z", "--", n).decode("utf-8").split(" ", 1)[0]
        if modo == "160000":
            out.append((n, 0, None, True))
            continue
        dim = int(_git("cat-file", "-s", ":" + n).strip())
        out.append((n, dim, _git("show", ":" + n) if dim <= MAX_BYTES else None, False))
    return out


def main() -> int:
    radice = Path(_git("rev-parse", "--show-toplevel").decode().strip())
    chiavi = chiavi_note(radice)
    bloccati = []
    for n, dim, contenuto, gitlink in file_in_staging():
        motivi = ["sottomodulo o repo annidato (contenuto non controllabile)"] if gitlink else problemi(n, dim, contenuto, chiavi)
        if motivi:
            bloccati.append((n, motivi))
    if not bloccati:
        return 0
    print("pre-commit: commit bloccato.", file=sys.stderr)
    for n, motivi in bloccati:
        print("  {}: {}".format(n, "; ".join(motivi)), file=sys.stderr)
    print("Togli i file dalla staging area (git restore --staged <file>). Regole: market-data/docs/adr/002-protezioni-git.md",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
