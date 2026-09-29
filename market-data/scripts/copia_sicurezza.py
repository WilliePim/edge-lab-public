"""Copia di sicurezza dell'archivio su un disco esterno. La lancia l'utente, a download finito.

- Copia `MARKET_DATA_DIR` (livello grezzo, Parquet, manifest, catalogo) in `<destinazione>/invest-data/` come **specchio**:
  i file che nell'archivio non ci sono più (per esempio parti Parquet di una ricostruzione precedente) si tolgono anche dalla
  copia, altrimenti un archivio ripristinato conterebbe righe due volte.
- **Incrementale**: un file già presente con stessa dimensione e stessa data di modifica non si rilegge. Con
  `--verifica-completa` si confronta anche l'impronta sha256 di ogni file.
- **Verifica**: ogni file copiato si rilegge dalla destinazione e se ne confronta l'impronta con l'originale.
- **Non si ferma su un file**: un file illeggibile o sparito durante la copia si registra fra gli errori e si va avanti.
- Esclusi i file temporanei (`*.tmp`, partizioni in costruzione, `STOP`, chiavistello, `*.wal`, catalogo in scrittura).
- Si ferma prima di iniziare se un download o un aggiornamento è in corso (`manifest/download.lock` con un processo vivo),
  se c'è una ricostruzione a metà, o se la destinazione sta dentro un repo git o dentro l'archivio.
- Resoconto in `<destinazione>/invest-data/copia_sicurezza_<AAAA-MM-GG>.json`.

    .venv/Scripts/python.exe market-data/scripts/copia_sicurezza.py E:\\backup [--verifica-completa]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from market_data import config as C  # noqa: E402
from market_data.eodhd.download import processo_vivo  # noqa: E402

NOMI_ESCLUSI = {"STOP", "download.lock", "download.pid", "catalog.duckdb.nuovo"}
SUFFISSI_ESCLUSI = (".tmp", ".wal")
PREFISSI_CARTELLE_ESCLUSE = (".tmp_exchange=", ".old_exchange=")


def impronta(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for pezzo in iter(lambda: fh.read(1 << 20), b""):
            h.update(pezzo)
    return h.hexdigest()


def escluso(rel: Path) -> bool:
    if rel.name in NOMI_ESCLUSI or rel.name.endswith(SUFFISSI_ESCLUSI) or rel.name.startswith("copia_sicurezza_"):
        return True
    return any(parte.startswith(PREFISSI_CARTELLE_ESCLUSE) for parte in rel.parts)


def lavori_in_corso(archivio: Path) -> str | None:
    lock = archivio / "eodhd" / "manifest" / "download.lock"
    if lock.exists():
        pid = lock.read_text(encoding="utf-8").strip()
        if pid and processo_vivo(pid):
            return "download o aggiornamento in corso (PID {}): aspetta la fine (o crea manifest/STOP)".format(pid)
    parquet = archivio / "eodhd" / "parquet"
    if parquet.exists() and any(p.name.startswith(PREFISSI_CARTELLE_ESCLUSE) for p in parquet.glob("*/*")):
        return "ricostruzione del Parquet a metà (cartelle .tmp_ o .old_): rilanciare la ricostruzione prima della copia"
    return None


def copia(archivio: Path, destinazione: Path, verifica_completa: bool = False, log=print,
          in_corso=lavori_in_corso) -> dict:
    dest = destinazione / "invest-data"
    if C.repo_git_che_contiene(dest.resolve()) is not None:
        raise SystemExit("la destinazione sta dentro un repo git: scegli una cartella fuori")
    if dest.resolve() == archivio.resolve() or archivio.resolve() in dest.resolve().parents:
        raise SystemExit("la destinazione sta dentro l'archivio")
    motivo = in_corso(archivio)
    if motivo:
        raise SystemExit(motivo)
    conti = {"file": 0, "copiati": 0, "uguali": 0, "tolti_dalla_copia": 0, "byte_copiati": 0, "errori": []}
    presenti = set()
    for sorgente in sorted(archivio.rglob("*")):
        rel = sorgente.relative_to(archivio)
        if not sorgente.is_file() or escluso(rel):
            continue
        presenti.add(rel)
        conti["file"] += 1
        bersaglio = dest / rel
        try:
            st = sorgente.stat()
            if bersaglio.exists():
                sb = bersaglio.stat()
                if sb.st_size == st.st_size and int(sb.st_mtime) == int(st.st_mtime) and (
                        not verifica_completa or impronta(bersaglio) == impronta(sorgente)):
                    conti["uguali"] += 1
                    continue
            h = impronta(sorgente)
            bersaglio.parent.mkdir(parents=True, exist_ok=True)
            tmp = bersaglio.with_name(bersaglio.name + ".tmp")
            shutil.copy2(sorgente, tmp)
            if impronta(tmp) != h:
                tmp.unlink()
                conti["errori"].append({"file": rel.as_posix(), "errore": "impronta diversa dopo la copia"})
                continue
            os.replace(tmp, bersaglio)
            conti["copiati"] += 1
            conti["byte_copiati"] += st.st_size
            if conti["copiati"] % 5_000 == 0:
                log("copiati {} file".format(conti["copiati"]))
        except OSError as e:
            conti["errori"].append({"file": rel.as_posix(), "errore": "{}: {}".format(type(e).__name__, e)})
    if dest.exists():
        for vecchio in sorted(dest.rglob("*"), reverse=True):
            rel = vecchio.relative_to(dest)
            if vecchio.is_file() and not rel.name.startswith("copia_sicurezza_") and rel not in presenti:
                try:
                    vecchio.unlink()
                    conti["tolti_dalla_copia"] += 1
                except OSError as e:
                    conti["errori"].append({"file": rel.as_posix(), "errore": "non tolto: {}".format(e)})
            elif vecchio.is_dir() and not any(vecchio.iterdir()):
                vecchio.rmdir()
    conti["quando"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    conti["sorgente"], conti["destinazione"], conti["verifica_completa"] = str(archivio), str(dest), verifica_completa
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "copia_sicurezza_{}.json".format(dt.date.today())).write_text(json.dumps(conti, indent=1), encoding="utf-8")
    return conti


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Copia di sicurezza dell'archivio su un disco esterno")
    ap.add_argument("destinazione", help="cartella sul disco esterno, per esempio E:\\backup")
    ap.add_argument("--verifica-completa", action="store_true", help="confronta l'impronta anche dei file non cambiati")
    a = ap.parse_args(argv)
    conti = copia(C.archivio(), Path(a.destinazione), verifica_completa=a.verifica_completa)
    print(json.dumps({k: v for k, v in conti.items() if k != "errori"}, indent=1))
    if conti["errori"]:
        print("ERRORI: {} (dettaglio nel resoconto)".format(len(conti["errori"])))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
