"""Il confine del repo: edge-lab funziona da solo, senza un repo esterno e senza moduli che non ha.

Un repo che dipende da un altro, o da moduli rimasti fuori, si rompe su un clone pulito, e si rompe in silenzio fino
al primo import. Questo test lo dice prima, leggendo solo i sorgenti. Quattro controlli:
- **import**: ogni import assoluto di ogni file Python del repo risolve in una di tre cose: la libreria standard, un
  modulo o package che sta in questo repo, una dipendenza dichiarata (`requirements*.txt`, `pyproject.toml` di
  market-data). Un import che non risolve e' un modulo di un repo esterno, o un modulo rimasto fuori dal repo;
- **percorsi assoluti**: nessuna costante stringa (docstring escluse) contiene il percorso della cartella di un utente
  (`C:\\Users\\...`, `/home/...`, `/Users/...`). Un percorso cosi' funziona su una macchina sola;
- **script**: nessun `.sh`, `.cmd`, `.bat`, `.ps1` esce dalla radice del repo con `..` fuori dalle righe di commento;
- **market-data installato**: se l'interprete ha il pacchetto `market-data`, deve venire da una cartella `market-data`
  che contiene davvero il package (`market_data/api.py`), non da un'altra copia qualsiasi.

Le eccezioni stanno in NOTE (dipendenze usate ma non dichiarate) e AMMESSI (file che possono contenere un percorso
assoluto), ciascuna col motivo; un'eccezione che non serve piu' fa fallire il test.
Nessuna rete, nessun dato: solo lettura dei sorgenti e dei metadati del pacchetto installato.
"""
import ast
import importlib.metadata
import json
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

ROOT = Path(__file__).resolve().parents[1]
ESCLUSE = {".venv", "venv", "state", ".edgar_cache", ".llm_cache", "__pycache__", ".git", "out", "logs",
           "node_modules", ".pytest_cache"}

#  nome della distribuzione (minuscolo) -> nome del modulo importato, quando sono diversi
DISTRIBUZIONE_MODULO = {"pyyaml": "yaml", "beautifulsoup4": "bs4", "scikit-learn": "sklearn"}

#  modulo usato ma non dichiarato -> perche' e' ammesso lo stesso. Una nota che non serve piu' fa fallire il test.
#  Vuota: numpy e' in requirements.txt, exchange_calendars nell'extra `archivio` di market-data.
NOTE = {}

#  file relativo alla radice -> perche' puo' contenere un percorso assoluto di utente
AMMESSI = {
    "edgar_llm/tests/test_perimeter.py": "fixture positiva della regola `path-windows` del perimetro",
    "tests/test_confine_repo.py": "questo file: le usa negli autocontrolli",
}

PERCORSO_UTENTE = re.compile(r"(?:\b[a-z]:[\\/]+users[\\/]|(?:^|[\s'\"=(])/(?:home|users)/[a-z])")
#  suffisso -> riga di commento (gia' senza spazi ai lati e in minuscolo). `rem` solo come parola intera.
_COMMENTO_CMD = re.compile(r"^(::|@?rem(\s|$))")
SCRIPT = {".sh": re.compile(r"^#"), ".ps1": re.compile(r"^#"), ".cmd": _COMMENTO_CMD, ".bat": _COMMENTO_CMD}
FUORI_DAL_REPO = re.compile(r"(?:^|[\s'\"=(])\.\.[\\/]")


def file_del_repo(schema: str):
    for p in sorted(ROOT.rglob(schema)):
        if p.is_file() and not any(parte in ESCLUSE for parte in p.relative_to(ROOT).parts):
            yield p


def moduli_locali() -> set:
    """Ogni nome importabile che sta nel repo: file .py e cartelle che contengono file .py."""
    out = set()
    for p in file_del_repo("*.py"):
        out.add(p.stem)
        for parte in p.relative_to(ROOT).parts[:-1]:
            out.add(parte)
    return out


def _nome(requisito: str) -> str:
    return re.split(r"[\s<>=!~;\[]", requisito.strip(), maxsplit=1)[0].lower()


def dipendenze_dichiarate() -> set:
    nomi = set()
    for p in file_del_repo("requirements*.txt"):
        for riga in p.read_text(encoding="utf-8").splitlines():
            riga = riga.strip()
            if riga and not riga.startswith(("#", "-")):
                nomi.add(_nome(riga))
    for p in file_del_repo("pyproject.toml"):
        progetto = tomllib.loads(p.read_text(encoding="utf-8")).get("project", {})
        for r in progetto.get("dependencies", []):
            nomi.add(_nome(r))
        for gruppo in progetto.get("optional-dependencies", {}).values():
            for r in gruppo:
                nomi.add(_nome(r))
    return {DISTRIBUZIONE_MODULO.get(n, n.replace("-", "_")) for n in nomi}


def docstring(albero: ast.AST) -> set:
    """Gli id dei nodi che sono docstring: prima istruzione stringa di modulo, classe o funzione."""
    out = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and nodo.body:
            primo = nodo.body[0]
            if isinstance(primo, ast.Expr) and isinstance(primo.value, ast.Constant) and isinstance(primo.value.value, str):
                out.add(id(primo.value))
    return out


def radici_importate(albero: ast.AST) -> dict:
    """{radice: prima riga} degli import assoluti. Gli import relativi sono moduli di questo repo per costruzione."""
    out = {}
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                out.setdefault(alias.name.split(".")[0], nodo.lineno)
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            out.setdefault(nodo.module.split(".")[0], nodo.lineno)
    return out


def import_non_risolti(sorgente: str, conosciuti: set) -> dict:
    return {r: n for r, n in radici_importate(ast.parse(sorgente)).items() if r not in conosciuti}


def percorsi_utente(sorgente: str) -> list:
    albero = ast.parse(sorgente)
    esclusi = docstring(albero)
    return ["riga {}".format(nodo.lineno) for nodo in ast.walk(albero)
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in esclusi
            and PERCORSO_UTENTE.search(nodo.value.lower())]


def uscite_script(testo: str, suffisso: str) -> list:
    commento = SCRIPT[suffisso]
    return ["riga {}".format(n) for n, riga in enumerate(testo.splitlines(), 1)
            if not commento.match(riga.strip().lower()) and FUORI_DAL_REPO.search(riga)]


#  ---- il controllo stesso: esempi che devono essere presi e che devono passare
CONOSCIUTI_PROVA = set(sys.stdlib_module_names) | {"form4_scanner", "requests"}
check("import di un modulo che non c'e' preso", import_non_risolti("import modulo_privato", CONOSCIUTI_PROVA))
check("from x.y import z di un package assente preso",
      import_non_risolti("from package_esterno.sotto import f", CONOSCIUTI_PROVA))
check("libreria standard ammessa", not import_non_risolti("import json, re\nfrom pathlib import Path", CONOSCIUTI_PROVA))
check("modulo del repo e dipendenza dichiarata ammessi",
      not import_non_risolti("from form4_scanner.scan import x\nimport requests", CONOSCIUTI_PROVA))
check("import relativo ammesso", not import_non_risolti("from .qualcosa import x", CONOSCIUTI_PROVA))
check("percorso Windows di utente preso", percorsi_utente("P = r'C:\\\\Users\\\\qualcuno\\\\dati'"))
check("percorso Windows con le barre dritte preso", percorsi_utente("P = 'c:/users/qualcuno/dati'"))
check("percorso POSIX di utente preso", percorsi_utente("P = '/home/qualcuno/dati'"))
check("docstring con un percorso ammessa", not percorsi_utente('"""Prima stava in /home/qualcuno."""\n'))
check("percorso relativo ammesso", not percorsi_utente("P = 'state/backfill/prices'"))
check("sh: uscita dalla radice presa, commento ammesso",
      uscite_script("cd ../altro-repo", ".sh") and not uscite_script("# cd ../altro-repo", ".sh"))
check("sh: un percorso dentro il repo ammesso", not uscite_script('. ./venv.sh\n"$PY" tools/notify.ps1', ".sh"))
check("cmd: REM e :: ammessi", not uscite_script("REM cd ..\\altro\n:: cd ..\\altro", ".cmd"))

#  ---- il repo
locali = moduli_locali()
dichiarate = dipendenze_dichiarate()
conosciuti = set(sys.stdlib_module_names) | locali | dichiarate
check("lette le dipendenze dichiarate (se scende a zero, il parser e' rotto)", len(dichiarate) >= 5,
      sorted(dichiarate))

non_risolti, note_usate, n_py = {}, set(), 0
percorsi, ammessi_usati = {}, set()
for p in file_del_repo("*.py"):
    rel = p.relative_to(ROOT).as_posix()
    testo = p.read_text(encoding="utf-8", errors="replace")
    try:
        mancanti = import_non_risolti(testo, conosciuti)
        assoluti = percorsi_utente(testo)
    except SyntaxError:
        continue
    n_py += 1
    for radice, riga in mancanti.items():
        if radice in NOTE:
            note_usate.add(radice)
        else:
            non_risolti.setdefault(radice, []).append("{}:{}".format(rel, riga))
    if assoluti:
        if rel in AMMESSI:
            ammessi_usati.add(rel)
        else:
            percorsi[rel] = assoluti

uscite, n_script = {}, 0
for suffisso in SCRIPT:
    for p in file_del_repo("*" + suffisso):
        n_script += 1
        v = uscite_script(p.read_text(encoding="utf-8", errors="replace"), suffisso)
        if v:
            uscite[p.relative_to(ROOT).as_posix()] = v

check("letti file Python e script ({} / {})".format(n_py, n_script), n_py > 100 and n_script > 3)
check("ogni import risolve in libreria standard, modulo del repo o dipendenza dichiarata", not non_risolti,
      "; ".join("{} ({})".format(r, ", ".join(v[:3])) for r, v in sorted(non_risolti.items())))
check("nessun percorso assoluto di utente nel codice", not percorsi, str(percorsi))
check("nessuno script esce dalla radice del repo", not uscite, str(uscite))
check("nessuna nota inutile fra le dipendenze non dichiarate", not sorted(set(NOTE) - note_usate),
      str(sorted(set(NOTE) - note_usate)))
check("nessuna eccezione inutile in AMMESSI", not sorted(set(AMMESSI) - ammessi_usati),
      str(sorted(set(AMMESSI) - ammessi_usati)))

#  ---- il market-data installato nell'interprete che fa girare la suite
try:
    distribuzione = importlib.metadata.distribution("market-data")
except importlib.metadata.PackageNotFoundError:
    distribuzione = None
if distribuzione is None:
    print("  (market-data non installato in questo interprete: niente da controllare)")
else:
    grezzo = distribuzione.read_text("direct_url.json") or ""
    try:
        url = json.loads(grezzo).get("url", "") if grezzo else ""
    except ValueError:
        url = ""
    cartella = Path(unquote(urlparse(url).path).lstrip("/")) if url.startswith("file:") else None
    if cartella is not None and not cartella.is_absolute():
        cartella = Path("/" + str(cartella))
    check("market-data installato viene da una cartella `market-data` con il package dentro "
          "(reinstalla con: pip install -e ./market-data[archivio])",
          cartella is not None and cartella.name == "market-data" and (cartella / "market_data" / "api.py").exists(),
          url)
    if cartella is not None and cartella.resolve() != (ROOT / "market-data").resolve():
        print("  nota: market-data installato da un'altra copia di edge-lab: {}".format(cartella))

if __name__ == "__main__":
    sys.exit(report("CONFINE DEL REPO RISPETTATO"))
