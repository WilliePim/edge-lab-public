"""Russell 2000, uscite verso il basso — fase 0: quali depositi SEC danno i titoli di IWM e IWB, e a che data.

1. `company_tickers_mf.json` della SEC: CIK, serie e classe di IWM e IWB.
2. Per ogni serie, elenco EDGAR dei depositi N-Q, N-CSR, N-CSRS, NPORT-P (feed Atom).
3. Per ogni deposito, l'intestazione (`-index-headers.html`): periodo di riferimento.

Output `risultati/fase0_depositi.json` e tabella a video: per ogni anno 2015-2025, il deposito del 31 marzo e del 30 giugno
per ciascun fondo, o «MANCA». Nessun documento grande scaricato qui.

    python backtest/russell_exits/fase0_depositi.py
"""
from __future__ import annotations

import collections
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import sec  # noqa: E402

OUT = HERE / "risultati" / "fase0_depositi.json"
FONDI = {"IWM": "iShares Russell 2000 ETF", "IWB": "iShares Russell 1000 ETF"}
TIPI = ("N-Q", "N-CSR", "N-CSRS", "NPORT-P")
ATOM = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={serie}&type={tipo}&dateb=&owner=include"
        "&count=100&output=atom")
NS = {"a": "http://www.w3.org/2005/Atom"}


def serie_fondi(b):
    raw = b.get("https://www.sec.gov/files/company_tickers_mf.json")
    if not raw:
        raise SystemExit("company_tickers_mf.json non raggiungibile")
    d = json.loads(raw)
    campi = d["fields"]
    out = {}
    for riga in d["data"]:
        x = dict(zip(campi, riga))
        if x["symbol"] in FONDI:
            out[x["symbol"]] = x
    return out


def depositi(b, serie, tipo):
    raw = b.get(ATOM.format(serie=serie, tipo=tipo))
    if not raw or "<feed" not in raw:
        return []
    root = ET.fromstring(raw)
    out = []
    for e in root.findall("a:entry", NS):
        c = e.find("a:content", NS)
        if c is None:
            continue
        g = {ch.tag.split("}")[-1]: (ch.text or "") for ch in c}
        if g.get("filing-type", "").upper() != tipo:
            continue
        out.append({"tipo": tipo, "accession": g.get("accession-number", ""), "depositato": g.get("filing-date", ""),
                    "href": g.get("filing-href", "")})
    return out


def periodo(b, cik, acc):
    url = "https://www.sec.gov/Archives/edgar/data/{}/{}/{}-index-headers.html".format(int(cik), acc.replace("-", ""), acc)
    raw = b.get(url)
    if not raw:
        return None
    m = re.search(r"CONFORMED PERIOD OF REPORT:\s*(\d{8})", raw)
    return "{}-{}-{}".format(m.group(1)[:4], m.group(1)[4:6], m.group(1)[6:]) if m else None


def main() -> int:
    b = sec.Budget()
    mf = serie_fondi(b)
    print("fondi:", {k: (v["cik"], v["seriesId"], v["classId"]) for k, v in mf.items()}, flush=True)
    res = {"fondi": mf, "depositi": {}}
    for sym, x in mf.items():
        righe = []
        for tipo in TIPI:
            for dep in depositi(b, x["seriesId"], tipo):
                dep["periodo"] = periodo(b, x["cik"], dep["accession"])
                righe.append(dep)
        res["depositi"][sym] = sorted(righe, key=lambda r: (r["periodo"] or "", r["depositato"]))
        print(sym, "depositi:", dict(collections.Counter(r["tipo"] for r in righe)), "chiamate:", b.usate, flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")

    print("\nanno | fondo | 31 marzo | 30 giugno")
    for anno in range(2015, 2026):
        for sym in FONDI:
            per = {}
            for r in res["depositi"].get(sym, []):
                per.setdefault(r["periodo"], []).append("{} {}".format(r["tipo"], r["accession"]))
            print(anno, sym, per.get("{}-03-31".format(anno), ["MANCA"]), per.get("{}-06-30".format(anno), ["MANCA"]))
    print("chiamate di rete usate:", b.usate, "negate dal tetto:", b.negate)
    return 0


if __name__ == "__main__":
    sys.exit(main())
