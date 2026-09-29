"""Misura descrittiva dell'ipotesi §15.4, zero rete.

f = prezzo insider (grezzo, dal Form 4) / close del panel (Adj Close) alla stessa sessione.
Senza split ne' dividendi dopo quella data f ~ 1. Reverse split futuro 1:k -> f ~ 1/k (cap
del panel gonfiata); split in avanti k:1 -> f ~ k (cap sgonfiata).
"""
import bisect
import collections
import csv
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

tick, quiet_righe, _ = S.leggi_corpus(set())
pool = S.Pool(tick, quiet_righe)
righe = SV.righe_insider()
per_cik = collections.defaultdict(list)
for (c, _f), xs in righe.items():
    for td, sh, px in xs:
        if len(td) == 10 and px > 0:
            per_cik[c].append((td, px))
for c in per_cik:
    per_cik[c].sort()


def f_peer(cik, D):
    """f alla transazione piu' vicina a D con un close valido, e distanza in giorni."""
    i = pool.idx.get(cik)
    xs = per_cik.get(cik) or []
    if i is None or not xs:
        return None, None
    tds = [t for t, _ in xs]
    j = bisect.bisect_left(tds, D)
    best = None
    for k in (j - 3, j - 2, j - 1, j, j + 1, j + 2):
        if 0 <= k < len(xs):
            s = S.sessione(xs[k][0])
            close = pool.prezzo(i, s)
            if close:
                gap = abs(S.giorno(xs[k][0]) - S.giorno(D))
                if best is None or gap < best[1]:
                    best = (xs[k][1] / close, gap)
    return best if best else (None, None)


def secchio(f):
    if f is None:
        return "senza f"
    return "f < 0,67 (reverse split dopo?)" if f < 0.67 else ("f > 1,5 (split dopo?)" if f > 1.5 else "0,67-1,5")


pop = {(r["cik"], r["filed"]): r for r in map(json.loads, (HERE / "step2_prep" / "popolazione.jsonl").read_text(encoding="utf-8").splitlines())}
peer = collections.defaultdict(list)
evento = collections.defaultdict(list)
gaps = collections.defaultdict(list)
with (HERE / "step2" / "eventi.csv").open(encoding="utf-8", newline="") as fh:
    for r in csv.DictReader(fh):
        if r["r_e"] == "" or r["r_iwm"] == "":
            continue
        b = r["banda"]
        r_e, r_i = float(r["r_e"]), float(r["r_iwm"])
        if r["peer_size"] and r["r_size"] != "":
            f, gap = f_peer(r["peer_size"], r["D"])
            peer[(b, secchio(f))].append(float(r["r_size"]) - r_i)
            if gap is not None:
                gaps[b].append(gap)
        p = pop.get((r["cik"], r["filed"]))
        fe = None
        if p and p.get("prezzo_insider") and p.get("serie") and p.get("data_insider"):
            ser = S.carica(ROOT / p["serie"])
            close = ser.a_sessione(S.sessione(p["data_insider"])) if ser else None
            fe = p["prezzo_insider"] / close if close else None
        evento[(b, secchio(fe))].append(r_e - r_i)

print("\nPEER M_size: f alla transazione piu' vicina a D; media (r_peer - r_IWM)")
for b in ("<50M", "50-300M", ">300M"):
    tot = sum(len(v) for (bb, _s), v in peer.items() if bb == b)
    print(" ", b, "distanza mediana dalla transazione: {:.0f} giorni".format(np.median(gaps[b])))
    for (bb, s), v in sorted(peer.items()):
        if bb == b:
            print("    {:32s} n {:5d} ({:5.1%})  media {:+.2%}".format(s, len(v), len(v) / tot, np.mean(v)))
print("\nEVENTI: f alla data insider; media (r_e - r_IWM)")
for b in ("<50M", "50-300M", ">300M"):
    tot = sum(len(v) for (bb, _s), v in evento.items() if bb == b)
    for (bb, s), v in sorted(evento.items()):
        if bb == b:
            print("    {:8s} {:32s} n {:5d} ({:5.1%})  media {:+.2%}".format(b, s, len(v), len(v) / tot, np.mean(v)))
