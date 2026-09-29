"""E3 — i due file in blocco della SEC: companyfacts.zip e submissions.zip. Scaricati una volta, riusati sempre.

Decisione dell'utente del 22-09-2026 (ADR-046): il tetto di 3.000 chiamate non basta per i companyfacts dell'universo
dei peer e le submissions, uno per uno; i due zip costano una chiamata ciascuno. Quattro condizioni:

1. **point-in-time invariato**: nello zip ogni fatto porta la sua data di deposito (`filed`), e i filtri usano quella.
   Un fatto depositato dopo la data di ingresso non esiste per il backtest, anche se sta nello zip;
2. **manifest** con data di download e impronta sha256: gli zip sono fotografie rifatte ogni notte dalla SEC, e il
   referto dice di che giorno sono;
3. **si conservano** dopo il backtest, in `state/backfill/sec_bulk/` (ignorato da git): servono ai test successivi;
4. **soglia degli 8 GB liberi su C:** controllata prima e durante lo scaricamento; sotto soglia ci si ferma e il file
   parziale si cancella.

Si leggono **dentro lo zip**, senza estrarli: `companyfacts(cik)` e `submissions(cik)` (con i frammenti
`CIK##########-submissions-NNN.json` delle società con molti depositi, uniti come fa `survival.submissions`).

    python backtest/ipo_e3/bulk.py scarica
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
DIR = ROOT / "state" / "backfill" / "sec_bulk"
MANIFEST = DIR / "manifest.json"
CALLS = HERE / "edgar_calls.json"
FILE = {
    "companyfacts": "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip",
    "submissions": "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip",
}
#  I dati trimestrali dei Form 3/4/5 del 2012-2014, per lo spaccato insider (decisione dell'utente alla fermata 1):
#  quelli dal 2015 stanno già in `state/backfill/zips/`. Stesse quattro condizioni, una chiamata ciascuno.
FORM345 = ["form345_{}q{}".format(a, q) for a in (2012, 2013, 2014) for q in (1, 2, 3, 4)]
FILE.update({k: "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{}_form345.zip"
             .format(k.removeprefix("form345_")) for k in FORM345})
SOGLIA_LIBERI = 8 * 1024 ** 3
BLOCCO = 8 * 1024 ** 2


def liberi(percorso: Path = ROOT) -> int:
    return shutil.disk_usage(str(percorso)).free


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}


def _conta_chiamata() -> None:
    stato = json.loads(CALLS.read_text(encoding="utf-8")) if CALLS.exists() else {"network": 0}
    stato["network"] = stato.get("network", 0) + 1
    stato.setdefault("tetto", 3000)
    CALLS.write_text(json.dumps(stato), encoding="utf-8")


def scarica(nome: str) -> dict:
    """Scarica uno zip in streaming, con la soglia dei liberi controllata a ogni blocco. Una chiamata."""
    import requests
    from edgar_llm.config import get as env_get

    ua = env_get("EDGAR_USER_AGENT") or env_get("FORM4_USER_AGENT")
    if not ua or "@" not in ua:
        raise SystemExit("serve EDGAR_USER_AGENT con nome ed email")
    DIR.mkdir(parents=True, exist_ok=True)
    if liberi() < SOGLIA_LIBERI:
        raise SystemExit("meno di 8 GB liberi su C: prima di {}: fermo".format(nome))
    destinazione, parziale = DIR / (nome + ".zip"), DIR / (nome + ".zip.part")
    h, n = hashlib.sha256(), 0
    _conta_chiamata()
    with requests.get(FILE[nome], headers={"User-Agent": ua, "Accept-Encoding": "identity"}, stream=True,
                      timeout=120) as r:
        r.raise_for_status()
        testata = {k: r.headers.get(k) for k in ("Last-Modified", "Content-Length", "ETag")}
        with parziale.open("wb") as fh:
            for pezzo in r.iter_content(BLOCCO):
                fh.write(pezzo)
                h.update(pezzo)
                n += len(pezzo)
                if liberi() < SOGLIA_LIBERI:
                    fh.close()
                    parziale.unlink(missing_ok=True)
                    raise SystemExit("sotto 8 GB liberi durante {} ({} MB scaricati): fermo, parziale cancellato"
                                     .format(nome, n // 2 ** 20))
    parziale.replace(destinazione)
    voce = {"url": FILE[nome], "file": destinazione.name, "scaricato_utc": dt.datetime.now(dt.timezone.utc)
            .isoformat(timespec="seconds"), "sha256": h.hexdigest(), "byte": n, "testata": testata}
    m = manifest()
    m[nome] = voce
    MANIFEST.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
    return voce


# --------------------------------------------------------------------------------------------------- lettura ---
_zip: dict[str, zipfile.ZipFile] = {}


def _apri(nome: str) -> zipfile.ZipFile:
    if nome not in _zip:
        _zip[nome] = zipfile.ZipFile(DIR / (nome + ".zip"))
    return _zip[nome]


def _json(nome: str, membro: str) -> dict | None:
    try:
        with _apri(nome).open(membro) as fh:
            return json.load(fh)
    except KeyError:
        return None


def companyfacts(cik: str) -> dict | None:
    """Il companyfacts di un CIK come lo dà l'API della SEC, dallo zip. None se il CIK non c'è."""
    return _json("companyfacts", "CIK{}.json".format(str(cik).zfill(10)))


def submissions(cik: str) -> tuple[dict | None, list[tuple]]:
    """(testata, [(data, forma, voci, accession, documento principale)]) dallo zip, frammenti compresi."""
    cik = str(cik).zfill(10)
    d = _json("submissions", "CIK{}.json".format(cik))
    if not d:
        return None, []
    righe = []

    def assorbi(b):
        for i in range(len(b.get("accessionNumber", []))):
            righe.append((b["filingDate"][i], b["form"][i], b.get("items", [""] * (i + 1))[i] or "",
                          b["accessionNumber"][i], b.get("primaryDocument", [""] * (i + 1))[i] or ""))

    assorbi(d.get("filings", {}).get("recent", {}))
    for f in d.get("filings", {}).get("files", []):
        extra = _json("submissions", f.get("name", ""))
        if extra:
            assorbi(extra)
    righe.sort()
    return d, righe


if __name__ == "__main__":
    if sys.argv[1:2] == ["scarica"]:
        for k in sys.argv[2:] or list(FILE):
            v = scarica(k)
            print(k, v["byte"] // 2 ** 20, "MB", v["sha256"][:16], v["scaricato_utc"])
