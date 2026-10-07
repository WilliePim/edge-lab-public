"""Il controllo pre-commit (.githooks/guard.py) blocca dati, file grossi e chiavi; lascia passare il codice.

Portato insieme al controllo quando market-data e' entrato nel repo (market-data/docs/adr/002-protezioni-git.md), nello
stile di questo repo: script piatto su tests/harness.py, nessun pytest. Nessuna rete, nessun git: solo le funzioni pure del controllo.
"""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("guard", ROOT / ".githooks" / "guard.py")
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)

FINTA = "0123456789abcd" + "." + "12345678"   # spezzata: questo file deve poter entrare in un commit


#  estensioni di dati
for nome in ("a/prices.parquet", "x/cache.duckdb", "raw/eod.json.gz", "x.feather"):
    check("file di dati bloccato: {}".format(nome), "file di dati" in G.problemi(nome, 10, b"", []))

#  .env bloccato, .env.example (solo nomi) ammesso
check(".env bloccato", G.problemi(".env", 10, b"", []) == ["file .env con segreti"])
check(".env.example ammesso", G.problemi(".env.example", 10, b"EODHD_API_KEY=\nMARKET_DATA_DIR=\n", []) == [])
check("il .env.example della radice passa il controllo",
      G.problemi(".env.example", 0, (ROOT / ".env.example").read_bytes(), []) == [])

#  file sopra 5 MB
check("file sopra 5 MB bloccato",
      any(m.startswith("sopra 5 MB") for m in G.problemi("dump.csv", 6 * 1024 * 1024, None, [])))

#  chiave vera e forme di chiave
check("chiave vera presa", "contiene la chiave API" in G.problemi("x.py", 50, b"k = 'segreta-lunga'", [b"segreta-lunga"]))
check("forma esadecimale.cifre presa",
      "stringa con la forma di una chiave EODHD" in G.problemi("x.py", 50, FINTA.encode(), []))
check("api_token con valore preso", "api_token con un valore" in G.problemi(
    "x.md", 50, b"https://eodhd.com/api/eod/X?api_token=" + b"abcdefgh12", []))
check("EODHD_API_KEY con valore preso", "EODHD_API_KEY con un valore" in G.problemi(
    "x.sh", 50, b"export EODHD_API_KEY=" + b"abcdefgh12", []))

#  chiave FRED: 32 esadecimali, costruita qui perche' il test stesso non ne contenga una
FRED_FINTA = "0a1b2c3d" * 4
check("forma di chiave FRED presa",
      "stringa con la forma di una chiave FRED" in G.problemi("x.py", 50, ("k = '" + FRED_FINTA + "'").encode(), []))
check("FRED_API_KEY con valore preso", "FRED_API_KEY con un valore" in G.problemi(
    "x.sh", 50, b"FRED_API_KEY=" + FRED_FINTA.encode(), []))
check("api_key con valore preso (URL di ALFRED)", "api_key con un valore" in G.problemi(
    "log.txt", 80, b"https://api.stlouisfed.org/fred/series/observations?series_id=UNRATE&api_key=" + FRED_FINTA.encode(), []))
check("FRED_API_KEY vuota ammessa", G.problemi(".env.example", 20, b"FRED_API_KEY=\n", []) == [])
check("una forma di 31 o 33 esadecimali non e' una chiave FRED",
      G.problemi("x.py", 80, ("a = '" + FRED_FINTA[:31] + "'\nb = '" + FRED_FINTA + "f'").encode(), []) == [])
check("sha256 (64 esadecimali) non e' una chiave FRED",
      G.problemi("x.md", 80, ("impronta " + FRED_FINTA * 2).encode(), []) == [])

#  file UTF-16, come li scrive Out-File di PowerShell 5.1
testo = ("x = '" + FINTA + "'\n").encode("utf-16")
check("UTF-16: forma di chiave presa dopo la decodifica",
      "stringa con la forma di una chiave EODHD" in G.problemi("appunti.txt", len(testo), testo, []))
check("UTF-16: chiave vera presa dopo la decodifica",
      "contiene la chiave API" in G.problemi("appunti.txt", len(testo), testo, [FINTA.encode()]))

#  chiavi_note legge .env tollerante come la configurazione (BOM, export, spazi attorno a =)
_prima = {n: os.environ.pop(n, None) for n in ("EODHD_API_KEY", "FRED_API_KEY")}
try:
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / ".env").write_text("﻿MARKET_DATA_DIR=x\nexport EODHD_API_KEY = 'valore-lungo-1'\n"
                                      "FRED_API_KEY=valore-fred-2\n", encoding="utf-8")
        letto = G.chiavi_note(Path(d))
    check("chiavi_note legge .env come la configurazione, EODHD e FRED",
          letto == [b"valore-lungo-1", b"valore-fred-2"], str(letto))
finally:
    for n, v in _prima.items():
        if v is not None:
            os.environ[n] = v

#  il codice normale passa
testo = b"url = BASE + endpoint + '&' + urlencode({'api_token': self._chiave})\nversion = '1.2.3'\n"
check("codice normale passa",
      G.problemi("market-data/market_data/eodhd/client.py", len(testo), testo, [b"altra-chiave-vera"]) == [])
check("api_token=demo passa", G.problemi("docs/x.md", 20, b"api_token=demo", []) == [])

if __name__ == "__main__":
    sys.exit(report("CONTROLLO PRE-COMMIT CORRETTO"))
