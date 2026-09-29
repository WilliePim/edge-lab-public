"""Controllo appaiato per fascia, e terzili di rendimento passato.

DUE DOMANDE, una per sezione.

1. **Il controllo appaiato.** L'excess contro il Russell 2000 mette una nano-cap
   da 30 milioni contro un indice la cui mediana sta intorno al miliardo: parte
   di quello che si legge come excess e' la distanza fra i due, non l'acquisto
   insider. Il controllo toglie quella distanza: per ogni evento si prende un
   titolo della **stessa fascia di capitalizzazione**, alla **stessa data**,
   **senza acquisti insider nei 60 giorni precedenti**, e si guarda la
   differenza fra i due rendimenti. Il benchmark si elide: quello che resta e'
   "questo titolo contro un suo pari che nessun insider stava comprando".

   DA CHE POOL. I controlli escono dagli emittenti che hanno un market cap e una
   serie prezzi in cache -- cioe' **societa' i cui insider comprano in qualche
   momento**, solo non in quel momento. Non e' l'universo small cap generale:
   e' un universo gia' selezionato. Il che rende il confronto piu' stretto su
   una dimensione (stesso tipo di societa') e meno generale su un'altra. Un
   universo neutro richiederebbe prezzi e capitalizzazioni per migliaia di
   titoli senza attivita' Form 4, che non sono in cache.

   L'appaiamento e' sul **log-cap piu' vicino** dentro la fascia, deterministico:
   nessun campionamento casuale, nessun seme da ricordare.

2. **I terzili di rendimento passato**, dentro la fascia 50-300M. Se l'excess
   sta tutto nel terzile peggiore, il meccanismo e' il reversal e l'insider e'
   il marcatore, non la causa.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import backtest_event_time as B

STATE = B.STATE
PRICES = B.PRICES
REPORTS = B.REPORTS
QUIET_DAYS = 60


def load_caps():
    caps, tick = collections.defaultdict(list), {}
    with (STATE / "marketcap_rows.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("mcap"):
                c = str(r["issuer"]).lstrip("0")
                caps[c].append((r["trans"], float(r["mcap"])))
                if r.get("ticker"):
                    tick[c] = r["ticker"].upper()
    for k in caps:
        caps[k].sort()
    return caps, tick


def load_buydates():
    buys = collections.defaultdict(list)
    for f in sorted((STATE / "form4_raw").glob("*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                buys[r["issuer_cik"].lstrip("0")].append(r["transaction_date"])
    for k in buys:
        buys[k].sort()
    return buys


def cap_at(caps, cik, day):
    xs = caps.get(cik)
    if not xs:
        return None
    j = bisect.bisect_right([d for d, _ in xs], day) - 1
    return xs[j][1] if j >= 0 else None


def quiet(buys, cik, day):
    """True se l'emittente NON ha acquisti nei 60 giorni fino a `day`."""
    b = buys.get(cik)
    if not b:
        return True
    lo = (date.fromisoformat(day) - timedelta(days=QUIET_DAYS)).isoformat()
    return bisect.bisect_right(b, day) <= bisect.bisect_left(b, lo)


def eur_return(ticker, t0, horizon, fx):
    """Rendimento in euro dal primo giorno >= t0, su `horizon` barre."""
    ds, px = B.load_series(ticker)
    if ds is None:
        return None
    i = bisect.bisect_left(ds, t0)
    if i >= len(ds):
        return None
    j = i + horizon
    if j >= len(ds):
        return None
    f0 = B.value_on(fx[0], fx[1], ds[i])
    f1 = B.value_on(fx[0], fx[1], ds[j])
    if not f0 or not f1:
        return None
    r = (px[j] / f1) / (px[i] / f0) - 1.0
    return r if abs(r) <= B.ARTEFACT else None


def bucket_of(cap):
    return "<50M" if cap < 50e6 else "50-300M" if cap < 300e6 else ">300M"


def build_pools(caps, tick, buys, dates, have_px):
    """{data: {fascia: [(log cap, cik, ticker)]}} -- una volta per data."""
    pools = {}
    ciks = [c for c in caps if tick.get(c) in have_px]
    for d in dates:
        per = collections.defaultdict(list)
        for c in ciks:
            cap = cap_at(caps, c, d)
            if not cap or cap <= 0:
                continue
            if not quiet(buys, c, d):
                continue
            per[bucket_of(cap)].append(
                (math.log(cap), c, tick[c]))
        for b in per:
            per[b].sort()
        pools[d] = per
    return pools


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--horizons", default="21,63,126")
    ap.add_argument("--gate", default="dilution", choices=("none", "dilution"))
    ap.add_argument("--start", default="2015-01-01")
    a = ap.parse_args()
    horizons = [int(x) for x in a.horizons.split(",")]

    print("eventi...", flush=True)
    events = B.load_events(a.start)
    if a.gate == "dilution":
        ver = {}
        with (STATE / "dilution.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                ver[(r["issuer_cik"], r["as_of"])] = r["verdict"]
        n0 = len(events)
        events = [e for e in events
                  if ver.get((e["cik"], e["filed"])) != "BLOCKED"]
        print("  veto: {:,} -> {:,}".format(n0, len(events)))
    events = B.cooldown_filter(events)
    print("  dopo cooldown 126gg: {:,}".format(len(events)))

    caps, tick = load_caps()
    buys = load_buydates()
    have_px = {p.stem.upper() for p in PRICES.glob("*.csv")}
    fx = B.load_series(B.FX)

    #  Fascia e rendimento passato per ogni evento.
    for e in events:
        cap = cap_at(caps, e["cik"], e["filed"])
        e["cap"] = cap
        e["bucket"] = bucket_of(cap) if cap else None
        e["past"] = None
        ds, px = B.load_series(e["ticker"])
        if ds:
            j = bisect.bisect_right(ds, e["filed"]) - 1
            back = (date.fromisoformat(e["filed"])
                    - timedelta(days=365)).isoformat()
            k = bisect.bisect_left(ds, back)
            if j > k >= 0 and px[k] > 0:
                v = px[j] / px[k] - 1.0
                if abs(v) <= B.ARTEFACT:
                    e["past"] = v

    usable = [e for e in events if e["bucket"] and e["ticker"] in have_px]
    print("  con fascia e prezzi: {:,}".format(len(usable)))

    dates = sorted({e["filed"] for e in usable})
    print("date distinte: {:,} -- costruzione pool...".format(len(dates)),
          flush=True)
    pools = build_pools(caps, tick, buys, dates, have_px)

    print("appaiamento e rendimenti...", flush=True)
    for n, e in enumerate(usable):
        pool = pools.get(e["filed"], {}).get(e["bucket"]) or []
        e["control"] = None
        if pool:
            target = math.log(e["cap"])
            i = bisect.bisect_left([x[0] for x in pool], target)
            best = None
            for j in (i - 1, i, i + 1):
                if 0 <= j < len(pool) and pool[j][1] != e["cik"]:
                    d = abs(pool[j][0] - target)
                    if best is None or d < best[0]:
                        best = (d, pool[j])
            if best:
                e["control"] = best[1]
        if not e["control"]:
            continue
        ds, _ = B.load_series(e["ticker"])
        i0 = bisect.bisect_left(ds, e["filed"]) if ds else None
        if i0 is None or i0 >= len(ds):
            continue
        if ds[i0] <= e["filed"]:
            i0 += 1
        if i0 >= len(ds):
            continue
        t0 = ds[i0]
        for h in horizons:
            re_ = eur_return(e["ticker"], t0, h, fx)
            rc = eur_return(e["control"][2], t0, h, fx)
            if re_ is not None and rc is not None:
                e["pair_{}".format(h)] = re_ - rc
        if n % 5000 == 0:
            print("  {:,}/{:,}".format(n, len(usable)), flush=True)

    write_report(usable, horizons, a)
    return 0


def block(rows, key, horizons, title, note=""):
    L = ["### {}".format(title), ""]
    if note:
        L += [note, ""]
    L += [B.HEAD]
    for h in horizons:
        xs = [r[key.format(h)] for r in rows if key.format(h) in r]
        d = B.describe(xs)
        L.append("| **{} giorni** {}".format(
            h, B.fmt(d) if d else "| — | — | — | — | — | — |"))
    L.append("")
    return L


def write_report(rows, horizons, a):
    run_date = date.today().isoformat()
    paired = [r for r in rows if any("pair_{}".format(h) in r for h in horizons)]
    L = ["# Controllo appaiato per fascia, e terzili di rendimento passato", "",
         "Generato il {}. `python tools/matched_control.py --gate {}`."
         .format(run_date, a.gate), "",
         "## Che cos'e' il controllo", "",
         "Per ogni evento si prende un titolo della **stessa fascia di "
         "capitalizzazione**, alla **stessa data**, **senza acquisti insider "
         "nei {} giorni precedenti**, appaiato sul log-cap piu' vicino. La "
         "misura e' la differenza fra i due rendimenti in euro sullo stesso "
         "intervallo. Il benchmark si elide: non c'e' piu' un indice di mezzo, "
         "e con esso sparisce la distanza di dimensione fra una nano-cap e il "
         "Russell 2000.".format(QUIET_DAYS), "",
         "> **Da che pool escono i controlli.** Dagli emittenti che hanno un "
         "market cap e una serie prezzi in cache, cioe' **societa' i cui "
         "insider comprano in qualche momento** -- solo non in quel momento. "
         "Non e' l'universo small cap generale: e' gia' selezionato. Il "
         "confronto e' percio' piu' stretto su una dimensione (stesso tipo di "
         "societa') e meno generale su un'altra. Un universo neutro "
         "richiederebbe prezzi e capitalizzazioni per migliaia di titoli senza "
         "attivita' Form 4, che non sono in cache.", "",
         "| | |", "|---|---:|",
         "| eventi con fascia e prezzi | {:,} |".format(len(rows)),
         "| di cui appaiati | {:,} |".format(len(paired)),
         "| veto diluizione | {} |".format(a.gate), "",
         "---", "", "## 1. Evento meno controllo", ""]
    L += block(paired, "pair_{}", horizons, "Tutte le fasce")
    for b in ("<50M", "50-300M", ">300M"):
        sel = [r for r in paired if r["bucket"] == b]
        L += block(sel, "pair_{}", horizons, "Fascia {}".format(b))

    L += ["---", "", "## 2. Terzili di rendimento a 12 mesi precedente, "
          "dentro 50-300M", "",
          "Se l'excess sta tutto nel terzile peggiore, il meccanismo e' il "
          "reversal e l'insider e' il marcatore, non la causa.", ""]
    mid = [r for r in paired if r["bucket"] == "50-300M" and r.get("past") is not None]
    if len(mid) >= 90:
        vals = sorted(r["past"] for r in mid)
        q1, q2 = vals[len(vals) // 3], vals[2 * len(vals) // 3]
        groups = [("peggiore (<= {:+.1%})".format(q1),
                   [r for r in mid if r["past"] <= q1]),
                  ("centrale", [r for r in mid if q1 < r["past"] <= q2]),
                  ("migliore (> {:+.1%})".format(q2),
                   [r for r in mid if r["past"] > q2])]
        for name, sel in groups:
            L += block(sel, "pair_{}", horizons, "Terzile {}".format(name))
        L += ["_Terzili sui {:,} eventi 50-300M con rendimento passato "
              "calcolabile. Tagli: {:+.1%} e {:+.1%}._".format(
                  len(mid), q1, q2), ""]
    else:
        L += ["_Meno di 90 eventi con rendimento passato: terzili non "
              "calcolati._", ""]

    L += ["---", "", "## Limiti", "",
          "1. **Il pool di controllo non e' un universo neutro** (vedi sopra).",
          "2. **L'appaiamento e' su fascia, data e log-cap.** Non su settore, "
          "non su book-to-market, non su liquidita'. Due titoli della stessa "
          "fascia possono avere spread denaro-lettera molto diversi, e su "
          "questo universo lo spread e' la voce di costo piu' grande.",
          "3. **Il controllo puo' essere lo stesso titolo per eventi diversi**: "
          "non c'e' vincolo di uso unico, quindi i controlli sono correlati "
          "fra loro quanto gli eventi.",
          "4. **Sopravvivenza**: un evento entra solo se ESSO e il suo "
          "controllo hanno prezzi a entrambi gli estremi. Chi e' fallito non "
          "e' qui, ne' da un lato ne' dall'altro.",
          "5. **Nessun costo applicato**: sono rendimenti lordi. La differenza "
          "fra due gambe pagherebbe due volte lo spread.", ""]

    p = REPORTS / "matched-control-{}.md".format(run_date)
    p.write_text("\n".join(L), encoding="utf-8")
    print("\nscritto {}".format(p))
    return p


if __name__ == "__main__":
    raise SystemExit(main())
