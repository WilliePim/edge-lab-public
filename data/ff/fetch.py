"""Scarica i fattori Fama-French mensili dalla Ken French Data Library.

Fonte: Kenneth R. French, Data Library, Tuck School of Business at Dartmouth
https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html

I file non sono ridistribuiti in questo repo: si scaricano al volo con questo script.
Scrive, accanto a questo file:
  ff3.zip  <- F-F_Research_Data_Factors_CSV.zip   (Mkt-RF, SMB, HML, RF)
  mom.zip  <- F-F_Momentum_Factor_CSV.zip         (Mom)
nel formato originale della Ken French Data Library.

Uso:  python data/ff/fetch.py            # scarica solo i file mancanti
      python data/ff/fetch.py --force    # riscarica
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = {
    "ff3.zip": BASE + "F-F_Research_Data_Factors_CSV.zip",
    "mom.zip": BASE + "F-F_Momentum_Factor_CSV.zip",
}
USER_AGENT = "edge-lab research (factor download)"


def fetch(name: str, url: str, force: bool = False) -> Path:
    out = HERE / name
    if out.exists() and not force:
        print("presente:", out.name)
        return out
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    tmp = out.with_suffix(".tmp")
    tmp.write_bytes(data)
    with zipfile.ZipFile(tmp) as z:          # controllo minimo: e' uno zip con un CSV dentro
        nomi = z.namelist()
        if not nomi or not nomi[0].lower().endswith(".csv"):
            tmp.unlink()
            raise SystemExit("contenuto inatteso in {}: {}".format(url, nomi))
    tmp.replace(out)
    print("scaricato:", out.name, "({} byte, {})".format(len(data), nomi[0]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true", help="riscarica anche se il file c'e'")
    a = ap.parse_args(argv)
    for name, url in FILES.items():
        fetch(name, url, a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
