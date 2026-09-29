"""Split dalle riesposizioni XBRL delle companyfacts in cache. Zero rete.

Per ogni periodo contabile (start, end) di WeightedAverageNumberOfSharesOutstandingBasic, e per
ogni data (end) di CommonStockSharesOutstanding, i valori in ordine di deposito. Fra due depositi
consecutivi con valori diversi, rapporto = nuovo / vecchio. Candidato split se <= 0,55 o >= 1,8,
scartato come errore d'unita' se < 1/50 o > 50. Finestra dello split: (deposito vecchio, deposito
nuovo]. Candidati dello stesso CIK con rapporto concorde (entro il 10%) e finestre sovrapposte si
fondono nella finestra piu' stretta.

Verifica: f = prezzo Form 4 / Adj Close; transazioni prima e dopo la finestra; f_prima / f_dopo
deve valere il rapporto.
"""
import bisect
import collections
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]   # radice del repo
HERE = ROOT / "backtest" / "rematch_50_300m"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402
import step2_analysis as S  # noqa: E402
import survival as SV  # noqa: E402

CACHE = ROOT / ".edgar_cache"
CONCETTI = ("WeightedAverageNumberOfSharesOutstandingBasic", "CommonStockSharesOutstanding")


def companyfacts(c):
    u = "https://data.sec.gov/api/xbrl/companyfacts/CIK{:010d}.json".format(int(c))
    p = CACHE / (hashlib.sha256(u.encode()).hexdigest()[:24] + ".cache")
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except ValueError:
        return None


def split_da_riesposizioni(cf):
    cand = []
    gaap = ((cf or {}).get("facts") or {}).get("us-gaap") or {}
    for nome in CONCETTI:
        fatti = ((gaap.get(nome) or {}).get("units") or {}).get("shares") or []
        gruppi = collections.defaultdict(dict)
        for x in fatti:
            if not x.get("filed") or not x.get("val"):
                continue
            chiave = (x.get("start"), x.get("end"))
            gruppi[chiave].setdefault(x["filed"], float(x["val"]))
        for vals in gruppi.values():
            seq = sorted(vals.items())
            for (f0, v0), (f1, v1) in zip(seq, seq[1:]):
                if v0 <= 0 or f0 == f1:
                    continue
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
    return [g for g in fusi if g[0] < g[1]]


print("pool...", flush=True)
tick, quiet_righe, _ = S.leggi_corpus(set())
pool = S.Pool(tick, quiet_righe)
righe = SV.righe_insider()
tx = collections.defaultdict(list)
for (c, _f), vs in righe.items():
    for td, _sh, px in vs:
        if len(td) == 10 and px > 0:
            tx[c].append((td, px))
for c in tx:
    tx[c].sort()
serie_path = SV.indice_serie()

eventi = []
ciks = set()
with (HERE / "step2" / "eventi.csv").open(encoding="utf-8", newline="") as fh:
    for r in csv.DictReader(fh):
        eventi.append(r)
        ciks.add(r["cik"])
        if r["peer_size"]:
            ciks.add(r["peer_size"])

split = {}
conte = collections.Counter()
for c in ciks:
    cf = companyfacts(c)
    if cf is None:
        conte["companyfacts assenti"] += 1
        continue
    split[c] = split_da_riesposizioni(cf)
    conte["CIK con almeno uno split"] += bool(split[c])
    for g in split[c]:
        conte["split reverse" if g[2] < 1 else "split in avanti"] += 1


def serie_di(c):
    if c in pool.idx:
        return None, pool.idx[c]
    for t, _d in sorted((tick.get(c) or {}).items(), key=lambda kv: kv[1], reverse=True):
        if SV.chiave(t) in serie_path:
            return S.carica(serie_path[SV.chiave(t)]), None
    return None, None


def f_at(c, td, px):
    ser, i = serie_di(c)
    s = S.sessione(td)
    close = pool.prezzo(i, s) if i is not None else (ser.a_sessione(s) if ser else None)
    return px / close if close else None


ver = collections.Counter()
for c, gs in split.items():
    ts = tx.get(c) or []
    for lo, hi, r, n in gs:
        prima = [v for v in (f_at(c, *x) for x in [x for x in ts if x[0] <= lo][-3:]) if v]
        dopo = [v for v in (f_at(c, *x) for x in [x for x in ts if x[0] > hi][:3]) if v]
        if not prima or not dopo:
            ver["non verificabile"] += 1
            continue
        rap = float(np.median(prima)) / float(np.median(dopo))
        if abs(math.log(rap) - math.log(r)) < math.log(1.5):
            ver["confermato"] += 1
        elif abs(math.log(rap)) < math.log(1.25):
            ver["prezzo insider piatto"] += 1
        else:
            ver["discorde"] += 1

print("CIK (eventi e peer M_size del passo 2):", len(ciks))
for k, v in sorted(conte.items()):
    print("  {}: {:,}".format(k, v))
print("verifica col prezzo insider:")
for k, v in sorted(ver.items()):
    print("  {}: {:,}".format(k, v))

#  Richiamo sul bias: i peer M_size con f < 0,67 hanno uno split reverse dopo D?
tab = collections.Counter()
for r in eventi:
    if not r["peer_size"] or r["r_size"] == "":
        continue
    c, D = r["peer_size"], r["D"]
    ts = tx.get(c) or []
    tds = [t for t, _ in ts]
    j = bisect.bisect_left(tds, D)
    best = None
    for k in range(max(0, j - 3), min(len(ts), j + 3)):
        v = f_at(c, *ts[k])
        if v:
            gap = abs(S.giorno(ts[k][0]) - S.giorno(D))
            if best is None or gap < best[1]:
                best = (v, gap)
    fb = "f < 0,67" if best and best[0] < 0.67 else ("f > 1,5" if best and best[0] > 1.5 else ("0,67-1,5" if best else "senza f"))
    gs = split.get(c)
    if gs is None:
        stato = "companyfacts assenti"
    else:
        dopo = [g for g in gs if g[0] >= D]
        a_cavallo = [g for g in gs if g[0] < D < g[1]]
        stato = ("reverse dopo D" if any(g[2] < 1 for g in dopo) else
                 "in avanti dopo D" if dopo else
                 "finestra a cavallo di D" if a_cavallo else "nessuno split dopo D")
    tab[(r["banda"], fb, stato)] += 1
print("\npeer M_size: secchio di f × split rilevato dalle riesposizioni")
for k, v in sorted(tab.items()):
    print("  {:8s} {:10s} {:26s} {:,}".format(*k, v))
