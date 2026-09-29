"""Il confine con market-data (market-data/docs/adr/004): questo repo legge i prezzi EODHD solo tramite `market_data.api`.

market-data vive nella cartella `market-data/` di questo repo (market-data/docs/adr/007) e si usa come una libreria installata, come
yfinance. Il resto del codice non deve conoscere i moduli interni né i file dell'archivio: se l'archivio cambia forma,
cambia solo `market_data.api`. Queste asserzioni lo verificano sull'albero sintattico di ogni file Python del repo,
fuori da `market-data/` stessa:
- gli unici import ammessi sono `from market_data import api`, `import market_data.api` e `from market_data.api import …`;
- nessuna stringa punta ai file dell'archivio (`invest-data`, `eodhd/parquet`, `eodhd/raw`, `catalog.duckdb`).

Nessuna rete, nessun dato: solo lettura dei sorgenti.
"""
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

ROOT = Path(__file__).resolve().parents[1]
ESCLUSE = {".venv", "venv", "state", ".edgar_cache", "__pycache__", ".git", "out", "logs", "node_modules"}
PERCORSI_ARCHIVIO = ("invest-data", "eodhd/parquet", "eodhd\\parquet", "eodhd/raw", "eodhd\\raw", "catalog.duckdb")
#  Il package stesso, solo in cima all'albero (market-data/docs/adr/007): dentro market-data/ i moduli si importano fra loro e i
#  percorsi dell'archivio sono il loro mestiere. Il confine vale per chi lo usa, non per lui.
ESCLUSE_IN_CIMA = {"market-data"}
QUESTO_FILE = Path(__file__).resolve()


def sorgenti():
    for p in ROOT.rglob("*.py"):
        parti = p.relative_to(ROOT).parts
        if parti[0] in ESCLUSE_IN_CIMA:
            continue
        if not any(parte in ESCLUSE for parte in parti):
            yield p


def violazioni(albero: ast.AST) -> list[str]:
    out = []
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if (alias.name == "market_data" or alias.name.startswith("market_data.")) and alias.name != "market_data.api":
                    out.append("import {} (riga {})".format(alias.name, nodo.lineno))
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and (nodo.module == "market_data" or nodo.module.startswith("market_data.")):
            if nodo.module == "market_data":
                altri = [a.name for a in nodo.names if a.name != "api"]
                if altri:
                    out.append("from market_data import {} (riga {})".format(", ".join(altri), nodo.lineno))
            elif nodo.module != "market_data.api":
                out.append("from {} import … (riga {})".format(nodo.module, nodo.lineno))
        elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            if any(s in nodo.value for s in PERCORSI_ARCHIVIO):
                out.append("stringa con un percorso dell'archivio (riga {})".format(nodo.lineno))
    return out


#  il controllo stesso: esempi che devono essere presi e che devono passare
check("import di un modulo interno preso", violazioni(ast.parse("from market_data.store import normalize")))
check("import del package intero preso", violazioni(ast.parse("import market_data")))
check("config preso", violazioni(ast.parse("from market_data import config")))
check("percorso dell'archivio preso", violazioni(ast.parse("p = 'C:/x/invest-data/eodhd/parquet/prezzi'")))
check("api ammessa", not violazioni(ast.parse("from market_data import api\nimport market_data.api\nfrom market_data.api import prices")))

trovate = {}
for f in sorgenti():
    if f.resolve() == QUESTO_FILE:
        continue
    try:
        albero = ast.parse(f.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    v = violazioni(albero)
    if v:
        trovate[str(f.relative_to(ROOT))] = v
check("nessun modulo del repo passa il confine con market-data", not trovate, str(trovate))

if __name__ == "__main__":
    sys.exit(report("CONFINE CON MARKET-DATA RISPETTATO"))
