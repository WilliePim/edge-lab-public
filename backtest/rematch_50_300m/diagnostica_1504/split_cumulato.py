"""Verifica cumulata degli split dalle riesposizioni XBRL. Zero rete.

Per ogni split rilevato: ultima transazione insider <= inizio finestra ed entro 365 giorni, prima
transazione > fine finestra ed entro 365 giorni. Atteso = prodotto dei rapporti di TUTTI gli
split rilevati (non scartati) le cui finestre cadono fra le due transazioni. Confermato se
f_prima / f_dopo sta entro un fattore 1,5 dall'atteso.
"""
import collections
import csv
import hashlib
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]   # radice del repo
HERE = ROOT / "backtest" / "rematch_50_300m"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import step2_analysis as S  # noqa: E402
import survival as SV  # noqa: E402

CACHE = ROOT / ".edgar_cache"
CONCETTI = ("WeightedAverageNumberOfSharesOutstandingBasic", "CommonStockSharesOutstanding")
PULITI = (1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 10, 12, 15, 20, 25, 30, 35, 40, 50)


def pulito(r):
    x = r if r >= 1 else 1 / r
    return any(abs(x / p - 1) <= 0.03 for p in PULITI)


def companyfacts(c):
    u = "https://data.sec.gov/api/xbrl/companyfacts/CIK{:010d}.json".format(int(c))
    p = CACHE / (hashlib.sha256(u.encode()).hexdigest()[:24] + ".cache")
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace")) if p.exists() else None
    except ValueError:
        return None


def splits(cf):
    cand = []
    gaap = ((cf or {}).get("facts") or {}).get("us-gaap") or {}
    for nome in CONCETTI:
        gruppi = collections.defaultdict(dict)
        for x in ((gaap.get(nome) or {}).get("units") or {}).get("shares") or []:
            if x.get("filed") and x.get("val"):
                gruppi[(x.get("start"), x.get("end"))].setdefault(x["filed"], float(x["val"]))
        for vals in gruppi.values():
            seq = sorted(vals.items())
            for (f0, v0), (f1, v1) in zip(seq, seq[1:]):
                if v0 > 0 and f0 != f1:
                    r = v1 / v0
                    if (r <= 0.55 or r >= 1.8) and 1 / 50 <= r <= 50:
                        cand.append([f0, f1, r])
    fusi = []
    for lo, hi, r in sorted(cand, key=lambda z: (z[2], z[0])):
        for g in fusi:
            if abs(math.log(r) - math.log(g[2])) < math.log(1.1) and lo < g[1] and g[0] < hi:
                g[0], g[1] = max(g[0], lo), min(g[1], hi)
                g[3] += 1
                break
        else:
            fusi.append([lo, hi, r, 1])
    #  Scartati: in avanti con rapporto non pulito (1 confermato su 58 verificabili).
    return sorted([g for g in fusi if g[0] < g[1] and not (g[2] > 1 and not pulito(g[2]))])


def piu(d, n):
    return (date.fromisoformat(d) + timedelta(days=n)).isoformat()


tick, quiet_righe, _ = S.leggi_corpus(set())
pool = S.Pool(tick, quiet_righe)
serie_path = SV.indice_serie()
tx = collections.defaultdict(list)
for (c, _f), vs in SV.righe_insider().items():
    for td, _sh, px in vs:
        if len(td) == 10 and px > 0:
            tx[c].append((td, px))
for c in tx:
    tx[c].sort()
ciks = set()
with (HERE / "step2" / "eventi.csv").open(encoding="utf-8", newline="") as fh:
    for r in csv.DictReader(fh):
        ciks.add(r["cik"])
        if r["peer_size"]:
            ciks.add(r["peer_size"])

_serie = {}


def f_at(c, td, px):
    s = S.sessione(td)
    if c in pool.idx:
        close = pool.prezzo(pool.idx[c], s)
    else:
        if c not in _serie:
            path = next((serie_path[SV.chiave(t)] for t, _d in sorted((tick.get(c) or {}).items(), key=lambda kv: kv[1], reverse=True)
                         if SV.chiave(t) in serie_path), None)
            _serie[c] = S.carica(path) if path else None
        close = _serie[c].a_sessione(s) if _serie[c] else None
    return px / close if close else None


tab = collections.Counter()
for c in ciks:
    ts = tx.get(c) or []
    gs = splits(companyfacts(c))
    for lo, hi, r, n in gs:
        cat = ("pulito" if pulito(r) else "non pulito") + (" / reverse" if r < 1 else " / in avanti")
        prima = [x for x in ts if piu(lo, -365) <= x[0] <= lo]
        dopo = [x for x in ts if hi < x[0] <= piu(hi, 365)]
        fb = f_at(c, *prima[-1]) if prima else None
        fa = f_at(c, *dopo[0]) if dopo else None
        if not fb or not fa:
            tab[(cat, "non verificabile")] += 1
            continue
        tb, ta = prima[-1][0], dopo[0][0]
        atteso = 1.0
        for lo2, hi2, r2, _n2 in gs:
            if tb <= lo2 and hi2 < ta:
                atteso *= r2
        rap = fb / fa
        esito = ("confermato" if abs(math.log(rap) - math.log(atteso)) < math.log(1.5)
                 else "piatto" if abs(math.log(rap)) < math.log(1.25) else "discorde")
        tab[(cat, esito)] += 1
print("verifica cumulata, transazioni entro 365 giorni dalla finestra")
for k, v in sorted(tab.items()):
    print("  {:26s} {:18s} {:,}".format(*k, v))
