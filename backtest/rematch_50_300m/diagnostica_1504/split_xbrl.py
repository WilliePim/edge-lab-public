"""Gli split si vedono nelle azioni XBRL as-reported? Zero rete.

Candidato split fra due depositi consecutivi (i-1, i) se il rapporto v_i / v_(i-1) e'
<= 0,55 (reverse) o >= 1,8 (in avanti) e il nuovo livello PERSISTE (v_(i+1)/v_i in
[0,8; 1,25]) e il vecchio non era gia' un'anomalia (v_(i-1)/v_(i-2) in [0,8; 1,25]).
Verifica con i prezzi insider: f = prezzo Form 4 / Adj Close. Transazione prima del
salto e dopo: f_prima / f_dopo deve valere circa il rapporto delle azioni.
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

import survival as SV  # noqa: E402
import step2_analysis as S  # noqa: E402

ciks = set()
with (HERE / "step2" / "eventi.csv").open(encoding="utf-8", newline="") as fh:
    for r in csv.DictReader(fh):
        ciks.add(r["cik"])
        for k in ("peer_size", "peer_mom"):
            if r[k]:
                ciks.add(r[k])


def serie_azioni(c):
    p = SV.S / "shares" / "{}.json".format(c)
    if not p.exists():
        return []
    by = {}
    for r in json.loads(p.read_text(encoding="utf-8")).get("primary") or []:
        if r.get("filed") and r.get("val"):
            by[r["filed"]] = float(r["val"])
    return sorted(by.items())


def candidati(xs):
    out = []
    for i in range(1, len(xs)):
        r = xs[i][1] / xs[i - 1][1]
        if not (r <= 0.55 or r >= 1.8):
            continue
        dopo_ok = i + 1 >= len(xs) or 0.8 <= xs[i + 1][1] / xs[i][1] <= 1.25
        prima_ok = i < 2 or 0.8 <= xs[i - 1][1] / xs[i - 2][1] <= 1.25
        if dopo_ok and prima_ok and i + 1 < len(xs):
            out.append((xs[i - 1][0], xs[i][0], r))
    return out


righe = SV.righe_insider()
tx = collections.defaultdict(list)
for (c, _f), vs in righe.items():
    if c in ciks:
        for td, _sh, px in vs:
            if len(td) == 10 and px > 0:
                tx[c].append((td, px))
serie_path = SV.indice_serie()
tick, _q, _r = S.leggi_corpus(set())

conte = collections.Counter()
verifiche = collections.Counter()
esempi = []
for c in sorted(ciks):
    xs = serie_azioni(c)
    if len(xs) < 3:
        conte["serie azioni < 3 depositi"] += 1
        continue
    cand = candidati(xs)
    conte["CIK con almeno un salto"] += bool(cand)
    for lo, hi, r in cand:
        conte["salti reverse (<= 0,55)" if r < 1 else "salti in avanti (>= 1,8)"] += 1
        # verifica col prezzo insider
        per = tick.get(c) or {}
        path = None
        for t, _d in sorted(per.items(), key=lambda kv: kv[1], reverse=True):
            if SV.chiave(t) in serie_path:
                path = serie_path[SV.chiave(t)]
                break
        ser = S.carica(path) if path else None
        ts = sorted(tx.get(c) or [])
        prima = [x for x in ts if x[0] <= lo][-3:]
        dopo = [x for x in ts if x[0] >= hi][:3]
        if ser is None or not prima or not dopo:
            verifiche["non verificabile (mancano transazioni ai due lati o serie)"] += 1
            continue

        def f(x):
            close = ser.a_sessione(S.sessione(x[0]))
            return x[1] / close if close else None

        fp = [v for v in map(f, prima) if v]
        fd = [v for v in map(f, dopo) if v]
        if not fp or not fd:
            verifiche["non verificabile (close mancante)"] += 1
            continue
        rap = (sorted(fp)[len(fp) // 2]) / (sorted(fd)[len(fd) // 2])
        ok = abs(math.log(rap) - math.log(r)) < math.log(1.5)
        piatto = abs(math.log(rap)) < math.log(1.25)
        verifiche["confermato dal prezzo insider" if ok else ("prezzo insider piatto: non uno split" if piatto else "discorde")] += 1
        if len(esempi) < 8 and not ok:
            esempi.append((c, lo, hi, round(r, 3), round(rap, 3)))

print("CIK esaminati (eventi e peer del passo 2):", len(ciks))
for k, v in sorted(conte.items()):
    print("  {}: {:,}".format(k, v))
print("verifica dei salti col prezzo insider:")
for k, v in sorted(verifiche.items()):
    print("  {}: {:,}".format(k, v))
print("esempi non confermati (cik, deposito prima, deposito dopo, rapporto azioni, rapporto f):", esempi)

cache = ROOT / ".edgar_cache"
campione = sorted(ciks)[:400]
con_cf, con_ratio = 0, 0
for c in campione:
    u = "https://data.sec.gov/api/xbrl/companyfacts/CIK{:010d}.json".format(int(c))
    p = cache / (hashlib.sha256(u.encode()).hexdigest()[:24] + ".cache")
    if p.exists():
        con_cf += 1
        t = p.read_text(encoding="utf-8", errors="replace")
        con_ratio += "StockholdersEquityNoteStockSplitConversionRatio" in t
print("companyfacts in cache sui primi 400 CIK: {}; con StockholdersEquityNoteStockSplitConversionRatio: {}".format(con_cf, con_ratio))
