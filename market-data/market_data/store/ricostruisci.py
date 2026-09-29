"""Ricostruisce tutto il livello normalizzato dal grezzo, in ordine: tabelle Parquet, anagrafica, calendario, catalogo.

Si può rilanciare quando si vuole: il grezzo non cambia, le partizioni si sostituiscono intere.

Prima di partire controlla lo spazio (ADR 006 punto 62): tutto il Parquet stimato per il fattore di sicurezza, meno il
Parquet già presente (si sostituisce una partizione alla volta), più la riserva. Se non basta si ferma e lo dice;
`--senza-controllo-spazio` lo salta.

    .venv/Scripts/python.exe -m market_data.store.ricostruisci [--borse US,LSE]
"""
from __future__ import annotations

import argparse
import json
import sys

import shutil
from pathlib import Path

from market_data import config as C
from market_data.eodhd import download as D
from market_data.quality import calendario as K
from market_data.store import catalog, identity
from market_data.store import normalize as N


def ricostruisci(archivio, borse=None, log=print) -> dict:
    n = N.Normalizzatore(archivio, log=log)
    esito = n.per_titolo({"prezzi", "dividendi", "split", "cambi"}, set(borse) if borse else None)
    esito["tesoro US"] = n.tesoro()
    esito.update({"identificativi " + b: v for b, v in n.identificativi().items()})
    esito.update({"anagrafica " + b: v for b, v in identity.Anagrafica(archivio, log=log).costruisci(borse).items()})
    presenti = sorted({k.split(" ", 1)[1] for k in esito if k.startswith("prezzi ")} - {"INDX", "FOREX"})
    esito.update({"calendario " + b: v for b, v in K.scrivi_calendario(archivio, [b for b in presenti if b in K.CALENDARI]).items()})
    for b in presenti:                                  # segnalazioni vuote dove i controlli non sono ancora passati
        if not (archivio / "eodhd" / "parquet" / "segnalazioni" / "exchange={}".format(b)).exists():
            N.Partizione(archivio / "eodhd" / "parquet", archivio / "eodhd" / "manifest", "segnalazioni", b).chiudi([])
    esito["catalogo"] = str(catalog.costruisci_catalogo(archivio, log=log))
    return esito


def spazio_per_ricostruire(archivio: Path, stima: dict | None = None, libero=None) -> tuple[float, float]:
    """(byte liberi, byte necessari) per ricostruire il Parquet."""
    stima = D.STIMA if stima is None else stima
    cartella = archivio / "eodhd" / "parquet"
    esistente = sum(f.stat().st_size for f in cartella.rglob("*.parquet")) if cartella.exists() else 0
    serve = max(0.0, D.FATTORE_SPAZIO * sum(v[1] for v in stima.values()) * 1024 ** 3 - esistente) + D.MARGINE_SPAZIO
    return (shutil.disk_usage(archivio).free if libero is None else libero), serve


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--borse", default="")
    ap.add_argument("--senza-controllo-spazio", action="store_true")
    a = ap.parse_args(argv)
    for flusso in (sys.stdout, sys.stderr):
        try:
            flusso.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    borse = [b.strip() for b in a.borse.split(",") if b.strip()] or None
    archivio = C.archivio()
    libero, serve = spazio_per_ricostruire(archivio)
    if libero < serve and not a.senza_controllo_spazio:
        print("spazio insufficiente per il Parquet: liberi {:.1f} GB, necessari {:.1f} GB".format(libero / 1024 ** 3, serve / 1024 ** 3))
        return 3
    print(json.dumps(ricostruisci(archivio, borse), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
