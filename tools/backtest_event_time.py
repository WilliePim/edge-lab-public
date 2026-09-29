"""Backtest event-time: acquisti insider contro il Russell 2000, in euro.

Replica della Figura 3 di Cohen-Malloy-Pomorski sull'universo di questo repo:
ogni evento confrontato con l'indice sullo STESSO identico intervallo di
calendario, a 21, 63 e 126 giorni di borsa.

QUESTI NON SONO SEGNALI. Lo scanner non ha mai girato sullo storico: l'archivio
observations copre tre giorni di run e il piu' vecchio acquisto che contiene e'
di giugno 2026, quindi a 126 giorni di borsa non si chiuderebbe nemmeno un
orizzonte. La popolazione qui e' il CORPUS -- 237.833 acquisti open-market
2015Q1-2026Q1 -- che non ha passato il cancello diluizione e non ha uno
`score_v3`, perche' nessuno dei due esisteva quando quei Form 4 sono stati
depositati. E' l'universo giusto per misurare il drift; non e' la lista che lo
scanner emette oggi.

IL BENCHMARK. `IWM` (iShares Russell 2000, USD) convertito con `EURUSD=X`, di
default. `XRS2.DE` (Xtrackers Russell 2000 UCITS, euro nativo) e' selezionabile
ma parte dal 2015-03-06 e perde le prime nove settimane del corpus.
`IUS3.DE` NON e' un'alternativa: i metadati dicono "iShares S&P SmallCap 600
UCITS ETF", non Russell 2000, e l'S&P 600 ha un filtro di redditivita' che
esclude proprio le nano-cap non profittevoli in cui il corpus compra -- sarebbe
un benchmark piu' duro e non confrontabile con CMP.

Il cambio non e' un argomento contro l'ETF UCITS: entra una volta per serie e
nella differenza si elide quasi tutto. Il difetto vero di un UCITS e' TER piu'
tracking error, che gonfiano leggermente l'excess a favore della strategia.

EVENTI SOVRAPPOSTI. Con finestre di 126 giorni lo stesso emittente rientra
decine di volte nella stessa finestra e la t-stat si gonfia. Si riportano due
varianti: (a) tutti gli eventi, (b) un evento per emittente con cooldown di 126
giorni, il primo della sequenza. **La (b) e' quella confrontabile con la
Figura 3.**

Nessuna dipendenza nuova: numpy per t-stat e bootstrap, SVG scritto a mano.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from form4_scanner.classify import (NOVEL, OPPORTUNISTIC, ROUTINE, SPARSE,
                                    UNSEASONED, classify_insider)

ROOT = Path(__file__).resolve().parents[1]
#  EDGE_LAB_STATE_DIR sposta la cartella `state/` (default: `state/` nella radice del repo). Serve a importare questo
#  modulo, e i backtest che lo importano, contro un panel diverso da quello locale, per esempio serie sintetiche in
#  una cartella temporanea: `<EDGE_LAB_STATE_DIR>/backfill/prices/IWM.csv`.
STATE = Path(os.environ.get("EDGE_LAB_STATE_DIR") or ROOT / "state") / "backfill"
CORPUS = STATE / "form4_raw"
PRICES = STATE / "prices"
PANEL = STATE / "panel"
HISTORY = STATE / "purchase_history.json"
REPORTS = ROOT / "reports"

BENCHMARKS = {"iwm": ("IWM", True), "xrs2": ("XRS2.DE", False)}
FX = "EURUSD=X"
COOLDOWN = 126

#  Una barra oltre il +-500% non e' un rendimento: stessa costante e stessa
#  ragione di backfill_analyse.ARTEFACT.
ARTEFACT = 5.0

#  Precedenza dichiarata per etichettare un evento che ha piu' compratori:
#  `routine` solo quando TUTTI lo sono, che e' come flags.py gia' tratta il
#  caso. Non e' un giudizio, e' una regola di aggregazione scritta prima.
PRECEDENCE = (OPPORTUNISTIC, NOVEL, SPARSE, UNSEASONED, ROUTINE)
#  La mappatura a tre classi, per la tabella confrontabile con Table III.
THREE = {OPPORTUNISTIC: "OPPORTUNISTIC", ROUTINE: "ROUTINE",
         NOVEL: "UNCLASSIFIED", SPARSE: "UNCLASSIFIED",
         UNSEASONED: "UNCLASSIFIED"}


# ----------------------------------------------------------------- prezzi --
def load_series(ticker):
    """([date iso], [close]) dalla cache su disco, o (None, None)."""
    if not ticker:
        return None, None
    p = PRICES / "{}.csv".format(ticker.replace("/", "_"))
    if not p.exists():
        return None, None
    ds, px = [], []
    with p.open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            d, _, v = line.partition(",")
            d = d.strip()
            if len(d) != 10:
                continue
            try:
                f = float(v)
            except ValueError:
                continue
            if f > 0:
                ds.append(d)
                px.append(f)
    return (ds, px) if len(ds) >= 2 else (None, None)


def fetch(tickers, start="2013-01-01"):
    """Scarica cio' che manca nella cache. Stessa forma del panel esistente."""
    todo = [t for t in tickers
            if t and not (PRICES / "{}.csv".format(t.replace("/", "_"))).exists()]
    if not todo:
        return 0
    import yfinance as yf
    ok = 0
    for i in range(0, len(todo), 40):
        chunk = todo[i:i + 40]
        try:
            df = yf.download(chunk, start=start, auto_adjust=False,
                             progress=False, threads=True, group_by="ticker")
        except Exception:                                       # noqa: BLE001
            continue
        for t in chunk:
            try:
                sub = df[t] if len(chunk) > 1 else df
                col = "Adj Close" if "Adj Close" in sub.columns else "Close"
                ser = sub[col].dropna()
            except (KeyError, TypeError):
                continue
            if ser is None or len(ser) < 5:
                continue
            out = PRICES / "{}.csv".format(t.replace("/", "_"))
            tmp = out.with_suffix(".csv.tmp")
            ser.to_csv(tmp, header=["adj_close"])
            os.replace(tmp, out)
            ok += 1
        print("    prezzi {}/{}".format(i + len(chunk), len(todo)), flush=True)
    return ok


def at_or_after(ds, px, day_iso):
    """(indice, prezzo) del primo giorno >= day_iso, o (None, None)."""
    i = bisect.bisect_left(ds, day_iso)
    return (i, px[i]) if i < len(ds) else (None, None)


def value_on(ds, px, day_iso):
    """Prezzo dell'ultimo giorno <= day_iso: per benchmark e cambio."""
    i = bisect.bisect_right(ds, day_iso) - 1
    return px[i] if i >= 0 else None


# ------------------------------------------------------------- classifica --
def build_labels(events, history):
    """{(owner, anno): etichetta}. CMP classifica al 1 gennaio di ogni anno."""
    need = {(e["owner"], int(e["filed"][:4])) for e in events}
    out = {}
    for owner, year in need:
        prior = [date.fromisoformat(d) for d in history.get(owner, [])]
        as_of = date(year, 1, 1)
        #  `unseasoned` richiede la prima data di deposito del CIK, che il
        #  corpus non porta: senza, la distinzione non si puo' fare e
        #  classify_insider ricade su NOVEL, come e' scritto nel suo docstring.
        p = classify_insider(owner, "", [d for d in prior if d < as_of], as_of)
        out[(owner, year)] = p.label
    return out


# ------------------------------------------------------------- statistica --
def tstat(xs):
    a = np.asarray(xs, dtype=float)
    if len(a) < 2:
        return None
    sd = a.std(ddof=1)
    return float(a.mean() / (sd / math.sqrt(len(a)))) if sd > 0 else None


def bootstrap_ci(xs, n=1000, seed=12345):
    a = np.asarray(xs, dtype=float)
    if len(a) < 2:
        return (None, None)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(n, len(a)))
    means = a[idx].mean(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def describe(xs):
    a = np.asarray(xs, dtype=float)
    if len(a) == 0:
        return None
    lo, hi = bootstrap_ci(a)
    return {"n": int(len(a)), "mean": float(a.mean()),
            "median": float(np.median(a)), "sd": float(a.std(ddof=1))
            if len(a) > 1 else None,
            "hit": float((a > 0).mean()), "t": tstat(a),
            "ci_lo": lo, "ci_hi": hi}


# ----------------------------------------------------------------- eventi --
def load_events(start_iso):
    """Un evento per (emittente, data di deposito). Il corpus non ha segnali."""
    by = {}
    for f in sorted(CORPUS.glob("*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                filed, cik = r.get("filed_date"), (r.get("issuer_cik") or "")
                if not filed or filed < start_iso or not cik:
                    continue
                key = (cik.lstrip("0"), filed)
                e = by.get(key)
                if e is None:
                    e = by[key] = {"cik": key[0], "filed": filed,
                                   "ticker": (r.get("ticker") or "").upper(),
                                   "owners": set(), "usd": 0.0, "name":
                                   r.get("issuer_name") or ""}
                if r.get("owner_cik"):
                    e["owners"].add(r["owner_cik"].lstrip("0"))
                e["usd"] += float(r.get("value") or 0.0)
                if not e["ticker"]:
                    e["ticker"] = (r.get("ticker") or "").upper()
    out = []
    for e in by.values():
        t = e["ticker"]
        if t in ("", "NONE", "N/A", "[NONE]"):
            e["ticker"] = None
        e["owners"] = sorted(e["owners"])
        e["buyers"] = len(e["owners"])
        e["owner"] = e["owners"][0] if e["owners"] else ""
        out.append(e)
    out.sort(key=lambda e: (e["cik"], e["filed"]))
    return out


def cooldown_filter(events, days=COOLDOWN):
    """Un evento per emittente ogni `days` giorni, il primo della sequenza."""
    keep, last = [], {}
    for e in sorted(events, key=lambda e: (e["cik"], e["filed"])):
        d = date.fromisoformat(e["filed"])
        prev = last.get(e["cik"])
        if prev is None or (d - prev).days > days:
            keep.append(e)
            last[e["cik"]] = d
    return keep


# ------------------------------------------------------------ rendimenti --
def measure(events, bench, fx, horizons, cost_bps):
    """Aggiunge a ogni evento i rendimenti, l'excess e il flag."""
    bds, bpx, bench_usd = bench
    fds, fpx = fx
    by_ticker = defaultdict(list)
    for e in events:
        by_ticker[e["ticker"]].append(e)

    for tick, group in by_ticker.items():
        ds, px = load_series(tick)
        if ds is None:
            for e in group:
                e["flag"] = "DELISTED_NO_DATA"
            continue
        for e in group:
            i0, p0 = at_or_after(ds, px, e["filed"])
            #  t0 = primo giorno di borsa SUCCESSIVO al deposito. bisect_left su
            #  filed puo' cadere sul deposito stesso: si avanza di uno.
            if i0 is not None and ds[i0] <= e["filed"]:
                i0 += 1
                p0 = px[i0] if i0 < len(px) else None
            if i0 is None or p0 is None or i0 >= len(ds):
                e["flag"] = "NO_ENTRY_BAR"
                continue
            f0 = value_on(fds, fpx, ds[i0])
            b0 = value_on(bds, bpx, ds[i0])
            if not f0 or not b0:
                e["flag"] = "NO_BENCH_BAR"
                continue
            e["t0"] = ds[i0]
            e["flag"] = "OK"
            for h in horizons:
                j = i0 + h
                if j >= len(ds):
                    e["flag"] = "PARTIAL"
                    continue
                f1 = value_on(fds, fpx, ds[j])
                b1 = value_on(bds, bpx, ds[j])
                if not f1 or not b1:
                    continue
                #  Il titolo e' in dollari: si porta in euro dividendo per
                #  EURUSD (dollari per euro) a ciascun estremo.
                s0, s1 = p0 / f0, px[j] / f1
                r = s1 / s0 - 1.0
                #  Il benchmark: IWM in dollari va convertito, XRS2 e' gia' in
                #  euro e `bench_usd` lo dice.
                if bench_usd:
                    br = (b1 / f1) / (b0 / f0) - 1.0
                else:
                    br = b1 / b0 - 1.0
                if abs(r) > ARTEFACT or abs(br) > ARTEFACT:
                    continue
                net = r - cost_bps / 10000.0
                e["ret_{}".format(h)] = r
                e["net_{}".format(h)] = net
                e["exc_{}".format(h)] = r - br
                e["excnet_{}".format(h)] = net - br
    return events


def event_curve(events, bench, fx, upto=126):
    """{etichetta: [excess medio cumulato giorno 0..upto]} -- 127 punti."""
    bds, bpx, bench_usd = bench
    fds, fpx = fx
    acc = defaultdict(lambda: np.zeros(upto + 1))
    cnt = defaultdict(lambda: np.zeros(upto + 1))
    by_ticker = defaultdict(list)
    for e in events:
        if e.get("flag") in ("DELISTED_NO_DATA", "NO_ENTRY_BAR", "NO_BENCH_BAR"):
            continue
        by_ticker[e["ticker"]].append(e)

    for tick, group in by_ticker.items():
        ds, px = load_series(tick)
        if ds is None:
            continue
        for e in group:
            lab = e.get("label")
            if not lab or not e.get("t0"):
                continue
            i0 = bisect.bisect_left(ds, e["t0"])
            if i0 >= len(ds):
                continue
            f0 = value_on(fds, fpx, ds[i0])
            b0 = value_on(bds, bpx, ds[i0])
            if not f0 or not b0:
                continue
            s0 = px[i0] / f0
            for k in range(0, upto + 1):
                j = i0 + k
                if j >= len(ds):
                    break
                f1 = value_on(fds, fpx, ds[j])
                b1 = value_on(bds, bpx, ds[j])
                if not f1 or not b1:
                    continue
                r = (px[j] / f1) / s0 - 1.0
                br = ((b1 / f1) / (b0 / f0) - 1.0) if bench_usd else b1 / b0 - 1.0
                if abs(r) > ARTEFACT or abs(br) > ARTEFACT:
                    continue
                acc[lab][k] += r - br
                cnt[lab][k] += 1
    return {lab: np.where(cnt[lab] > 0, acc[lab] / np.maximum(cnt[lab], 1), np.nan)
            for lab in acc}, {lab: cnt[lab] for lab in acc}


# ------------------------------------------------- il 57% senza prezzi -----
def panel_shadow(events):
    """Media di exc_6m nel panel per gli eventi che NON hanno serie prezzi.

    Il 57% dei candidati non ha una serie: sono i falliti e i delistati, e la
    loro assenza alza ogni numero. Il panel pero' un excess a 6 mesi ce l'ha,
    calcolato ai tempi contro il fattore di mercato Fama-French. Non e' lo
    stesso benchmark di questo backtest e non e' confrontabile al centesimo,
    ma dice in che DIREZIONE e di quanto il campione con prezzi e' selezionato.
    """
    missing = {e["cik"] for e in events if e.get("flag") == "DELISTED_NO_DATA"}
    have = {e["cik"] for e in events if e.get("flag") in ("OK", "PARTIAL")}
    miss_x, have_x = [], []
    for f in sorted(PANEL.glob("*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                x = r.get("exc_6m")
                if x is None or abs(x) > ARTEFACT:
                    continue
                cik = (r.get("issuer_cik") or "").lstrip("0")
                if cik in missing:
                    miss_x.append(x)
                elif cik in have:
                    have_x.append(x)
    return describe(miss_x), describe(have_x)


# --------------------------------------------------------------- output ---
def svg_curve(curves, counts, path, upto=126):
    """Grafico scritto a mano: nessuna dipendenza, e resta un file vero."""
    W, H, PAD = 900, 420, 56
    labs = [l for l in (OPPORTUNISTIC, ROUTINE, NOVEL) if l in curves]
    vals = [v for l in labs for v in curves[l] if v == v]
    if not vals:
        path.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        return path
    lo, hi = min(vals + [0.0]), max(vals + [0.0])
    span = (hi - lo) or 1.0
    lo, hi = lo - span * 0.1, hi + span * 0.1
    colours = {OPPORTUNISTIC: "#1f6feb", ROUTINE: "#d1242f", NOVEL: "#8250df"}

    def X(k):
        return PAD + (W - 2 * PAD) * k / upto

    def Y(v):
        return H - PAD - (H - 2 * PAD) * (v - lo) / (hi - lo)

    p = ['<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" '
         'viewBox="0 0 {} {}" font-family="system-ui,sans-serif">'.format(W, H, W, H),
         '<rect width="{}" height="{}" fill="#ffffff"/>'.format(W, H)]
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = lo + (hi - lo) * frac
        y = Y(v)
        p.append('<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="#e6e6e6"/>'
                 .format(PAD, y, W - PAD, y))
        p.append('<text x="{}" y="{:.1f}" font-size="11" fill="#666" '
                 'text-anchor="end">{:+.1%}</text>'.format(PAD - 8, y + 4, v))
    p.append('<line x1="{}" y1="{:.1f}" x2="{}" y2="{:.1f}" stroke="#999" '
             'stroke-dasharray="3 3"/>'.format(PAD, Y(0.0), W - PAD, Y(0.0)))
    for k in (0, 21, 63, 126):
        p.append('<text x="{:.1f}" y="{}" font-size="11" fill="#666" '
                 'text-anchor="middle">{}</text>'.format(X(k), H - PAD + 18, k))
    p.append('<text x="{}" y="{}" font-size="12" fill="#333">giorni di borsa '
             'dall\'ingresso</text>'.format(W // 2 - 90, H - 12))
    for lab in labs:
        pts = []
        for k, v in enumerate(curves[lab]):
            if v == v:
                pts.append("{:.1f},{:.1f}".format(X(k), Y(v)))
        if pts:
            p.append('<polyline fill="none" stroke="{}" stroke-width="2" '
                     'points="{}"/>'.format(colours.get(lab, "#555"), " ".join(pts)))
    for i, lab in enumerate(labs):
        y = PAD + 6 + i * 18
        p.append('<rect x="{}" y="{}" width="10" height="10" fill="{}"/>'
                 .format(W - PAD - 190, y - 9, colours.get(lab, "#555")))
        p.append('<text x="{}" y="{}" font-size="12" fill="#333">{} (n={:,.0f})'
                 '</text>'.format(W - PAD - 174, y, lab, counts[lab][0]))
    p.append('</svg>')
    path.write_text("\n".join(p), encoding="utf-8")
    return path


def fmt(d, pct=True):
    if not d:
        return "| — | — | — | — | — | — |"
    def q(v):
        if v is None:
            return "—"
        return "{:+.2%}".format(v) if pct else "{:.2f}".format(v)
    return "| {:,} | {} | {} | {} | {:.0%} | {} | {} – {} |".format(
        d["n"], q(d["mean"]), q(d["median"]), q(d["sd"]) if d["sd"] else "—",
        d["hit"], "{:.2f}".format(d["t"]) if d["t"] is not None else "—",
        q(d["ci_lo"]), q(d["ci_hi"]))



def build_report(events, variants, horizons, sym, a, run_date, svg,
                 shadow_missing, shadow_have, curves, counts):
    from collections import Counter
    L = ["# Backtest event-time — acquisti insider vs Russell 2000 (EUR)", "",
         "Generato il {}. Rieseguibile con:".format(run_date), "",
         "```",
         "python tools/backtest_event_time.py --horizons {} --benchmark {} "
         "--cost-bps {:.0f} --start {} --gate {} --cap-bucket {}".format(
             ",".join(str(h) for h in horizons), a.benchmark, a.cost_bps,
             a.start, a.gate, a.cap_bucket),
         "```", ""]

    complete = [e for e in variants[1][1] if "exc_126" in e]
    if len(complete) < 30:
        L += ["> **Meno di 30 eventi completi a 126 giorni ({}). Sotto quella "
              "soglia le statistiche sono indicative e non altro.**".format(
                  len(complete)), ""]

    flags = Counter(e.get("flag", "?") for e in events)
    L += ["## Popolazione", "",
          "**Questi non sono segnali.** Lo scanner non ha mai girato sullo "
          "storico: l'archivio observations copre tre giorni di run e il suo "
          "acquisto piu' vecchio e' di giugno 2026. La popolazione qui e' il "
          "corpus — acquisti open-market codice P, non derivati, non 10b5-1 — "
          "che non ha passato il cancello diluizione e non ha uno `score_v3`, "
          "perche' nessuno dei due esisteva quando quei Form 4 sono stati "
          "depositati.", "",
          "| | |", "|---|---:|",
          "| eventi (emittente x data di deposito) | {:,} |".format(len(events)),
          "| di cui misurabili (`OK` o `PARTIAL`) | {:,} |".format(
              flags.get("OK", 0) + flags.get("PARTIAL", 0)),
          "| `DELISTED_NO_DATA` | {:,} |".format(flags.get("DELISTED_NO_DATA", 0)),
          "| `NO_ENTRY_BAR` | {:,} |".format(flags.get("NO_ENTRY_BAR", 0)),
          "| `NO_BENCH_BAR` | {:,} |".format(flags.get("NO_BENCH_BAR", 0)),
          "| benchmark | `{}` |".format(sym),
          "| costo round trip | {:.2f}% |".format(a.cost_bps / 100.0), ""]

    L += ["## Aggregato, excess lordo", ""]
    for vname, evs in variants:
        L += ["### {}".format(vname), "", HEAD]
        for h in horizons:
            xs = [e["exc_{}".format(h)] for e in evs if "exc_{}".format(h) in e]
            d = describe(xs)
            L.append("| **{} giorni** {}".format(
                h, fmt(d) if d else "| — | — | — | — | — | — |"))
        L.append("")

    L += ["## Aggregato, excess netto del costo", "", HEAD]
    for h in horizons:
        xs = [e["excnet_{}".format(h)] for e in variants[1][1]
              if "excnet_{}".format(h) in e]
        d = describe(xs)
        L.append("| **{} giorni** {}".format(
            h, fmt(d) if d else "| — | — | — | — | — | — |"))
    L += ["", "_Variante (b). Il costo e' un haircut sulla gamba titolo._", ""]

    base = variants[1][1]
    for h in horizons:
        L += ["---", "", "## Spaccature a {} giorni — variante (b)".format(h), ""]
        g3 = [(k, [e for e in base if e.get("label3") == k])
              for k in ("OPPORTUNISTIC", "UNCLASSIFIED", "ROUTINE")]
        L += section("Tre classi (mappatura dichiarata, confrontabile con "
                     "Table III di CMP)", g3, h)
        L += ["`UNCLASSIFIED` = `novel` + `sparse` + `unseasoned`. "
              "Un evento e' `ROUTINE` solo se **tutti** i compratori lo sono.", ""]
        g5 = [(k, [e for e in base if e.get("label") == k])
              for k in PRECEDENCE if any(e.get("label") == k for e in base)]
        L += section("Cinque classi native", g5, h)
        gb = [("1 compratore", [e for e in base if e["buyers"] == 1]),
              ("2 compratori", [e for e in base if e["buyers"] == 2]),
              ("3 o piu'", [e for e in base if e["buyers"] >= 3])]
        L += section("Numero di compratori distinti", gb, h)
        years = sorted({e["filed"][:4] for e in base})
        gy = [(y, [e for e in base if e["filed"][:4] == y]) for y in years]
        L += section("Anno di deposito", gy, h)

    L += ["---", "", "## Curva event-time", "",
          "Excess medio cumulato giorno per giorno da 0 a 126, variante (b). "
          "E' il confronto diretto con la Figura 3 di CMP.", "",
          "![curva]({})".format(svg.name), "",
          "Dati: `backtest-event-time-curve-{}.csv`, 127 punti.".format(run_date), ""]
    if curves:
        L += ["| classe | giorno 21 | giorno 63 | giorno 126 | n al giorno 0 |",
              "|---|---:|---:|---:|---:|"]
        for lab in sorted(curves):
            c = curves[lab]
            L.append("| {} | {} | {} | {} | {:,.0f} |".format(
                lab,
                "{:+.2%}".format(c[21]) if c[21] == c[21] else "—",
                "{:+.2%}".format(c[63]) if c[63] == c[63] else "—",
                "{:+.2%}".format(c[126]) if c[126] == c[126] else "—",
                counts[lab][0]))
        L.append("")

    L += ["---", "", "## Quanto vale il {:.1%} senza prezzi".format(flags.get("DELISTED_NO_DATA", 0) / max(len(events), 1)), "",
          "Gli eventi senza serie prezzi non sono un campione neutro: sono i "
          "falliti e i delistati. Il panel storico pero' un excess a 6 mesi ce "
          "l'ha, calcolato ai tempi **contro il fattore di mercato "
          "Fama-French** — un altro benchmark, quindi il confronto dice la "
          "direzione e l'ordine di grandezza, non il centesimo.", "",
          HEAD]
    L.append("| **senza serie prezzi** {}".format(
        fmt(shadow_missing) if shadow_missing else "| — | — | — | — | — | — |"))
    L.append("| **con serie prezzi** {}".format(
        fmt(shadow_have) if shadow_have else "| — | — | — | — | — | — |"))
    L.append("")
    if shadow_missing and shadow_have:
        gap = shadow_missing["mean"] - shadow_have["mean"]
        tail = ("Gli esclusi sono andati **peggio**: ogni numero di questo "
                "documento e' sovrastimato di un ordine simile." if gap < 0 else
                "Gli esclusi sono andati **meglio**: il verso della distorsione "
                "non e' quello atteso, e va guardato.")
        L += ["Scarto fra le due medie: **{:+.2%}**. ".format(gap) + tail, ""]

    miss = flags.get("DELISTED_NO_DATA", 0)
    L += ["---", "", "## Limiti", "",
          "1. **Survivorship.** {:,} eventi su {:,} non hanno serie prezzi "
          "({:.1%}). Non e' rumore: e' la parte del campione che e' fallita. "
          "La sezione qui sopra la quantifica.".format(
              miss, len(events), miss / max(len(events), 1)),
          "2. **Periodo coperto:** depositi dal {} in poi; il corpus arriva al "
          "2026Q1. Gli eventi troppo recenti per chiudere un orizzonte sono "
          "`PARTIAL` e non entrano negli aggregati.".format(a.start),
          "3. **Costo assunto:** {:.2f}% round trip, come haircut sulla gamba "
          "titolo. Non include lo spread denaro-lettera delle nano-cap, che su "
          "questo universo e' la voce piu' grande.".format(a.cost_bps / 100.0),
          "4. **Eventi sovrapposti.** La variante (a) conta lo stesso emittente "
          "decine di volte dentro la stessa finestra di 126 giorni e la sua "
          "t-stat e' gonfiata. La (b) e' quella da leggere.",
          "5. **`unseasoned` non compare**: distinguerlo da `novel` richiede la "
          "prima data di deposito del CIK, che il corpus non porta.",
          "6. **Barre oltre il ±500% scartate** (`ARTEFACT = 5.0`), stessa "
          "regola del resto del repo.",
          "7. **Benchmark UCITS:** con `--benchmark xrs2` mancano le prime nove "
          "settimane del 2015, e TER piu' tracking error gonfiano leggermente "
          "l'excess a favore della strategia.", "",
          "### Incoerenze trovate nei dati, non corrette", "",
          "- `total_buy_usd = 305.496.908.725` su una riga del panel: 305 "
          "miliardi su un singolo cluster, quasi certamente azioni x prezzo su "
          "un campo sbagliato.",
          "- Una `transaction_date` del **2006-08-28** dentro le observations "
          "di agosto 2026: deposito tardivo o amendment.", "",
          "Nessuna delle due e' stata corretta: non e' il compito di questo "
          "backtest.", ""]
    return "\n".join(L)


HEAD = ("| | n | media | mediana | dev.std | hit rate | t | IC 95% |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|")


def section(title, groups, h, key="exc_{}"):
    L = ["### {}".format(title), "", HEAD]
    for name, evs in groups:
        xs = [e[key.format(h)] for e in evs if key.format(h) in e]
        d = describe(xs)
        L.append("| **{}** {}".format(name, fmt(d) if d else
                                      "| — | — | — | — | — | — |"))
    L.append("")
    return L


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--horizons", default="21,63,126")
    ap.add_argument("--benchmark", default="iwm", choices=sorted(BENCHMARKS))
    ap.add_argument("--cost-bps", type=float, default=100.0)
    ap.add_argument("--start", default="2015-01-01")
    ap.add_argument("--out", default=None)
    ap.add_argument("--gate", default="none", choices=("none", "dilution"),
                    help="dilution = applica il veto point-in-time da "
                         "state/backfill/dilution.jsonl")
    ap.add_argument("--cap-bucket", default="all",
                    help="all | <50M | 50-300M | >300M")
    ap.add_argument("--dry-run", action="store_true",
                    help="conta gli eventi e i prezzi mancanti, non misura")
    a = ap.parse_args()
    horizons = [int(x) for x in a.horizons.split(",") if x.strip()]

    print("eventi dal corpus...", flush=True)
    events = load_events(a.start)
    tickers = {e["ticker"] for e in events if e["ticker"]}
    print("  {:,} eventi (emittente x data di deposito), {:,} ticker".format(
        len(events), len(tickers)))
    have = sum(1 for t in tickers
               if (PRICES / "{}.csv".format(t.replace("/", "_"))).exists())
    print("  ticker con serie in cache: {:,} / {:,}".format(have, len(tickers)))
    if a.dry_run:
        print("  dry-run: nessuna misura")
        return 0

    sym, usd = BENCHMARKS[a.benchmark]
    fetch([sym, FX])
    bds, bpx = load_series(sym)
    fds, fpx = load_series(FX)
    if bds is None or fds is None:
        print("benchmark o cambio non disponibili: {} / {}".format(sym, FX))
        return 2
    bench = (bds, bpx, usd)
    fx = (fds, fpx)
    print("benchmark {} ({} barre), cambio {} ({} barre)".format(
        sym, len(bds), FX, len(fds)))

    #  Il veto, e la fascia di capitalizzazione. Entrambi sono join su dati
    #  gia' calcolati: nessuna chiamata in piu'.
    if a.gate == "dilution":
        ver = {}
        with (STATE / "dilution.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                ver[(r["issuer_cik"], r["as_of"])] = r
        before = len(events)
        for e in events:
            d = ver.get((e["cik"], e["filed"]))
            e["dilution"] = (d or {}).get("verdict", "N/A")
        events = [e for e in events if e.get("dilution") != "BLOCKED"]
        print("  veto diluizione: {:,} -> {:,} ({:,} bloccati)".format(
            before, len(events), before - len(events)))

    if a.cap_bucket != "all":
        import bisect as _b
        caps = defaultdict(list)
        with (STATE / "marketcap_rows.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("mcap"):
                    caps[str(r["issuer"]).lstrip("0")].append(
                        (r["trans"], r["mcap"]))
        for k in caps:
            caps[k].sort()
        lo_hi = {"<50M": (0.0, 50e6), "50-300M": (50e6, 300e6),
                 ">300M": (300e6, float("inf"))}[a.cap_bucket]
        keep = []
        for e in events:
            xs = caps.get(e["cik"])
            if not xs:
                continue
            j = _b.bisect_right([d for d, _ in xs], e["filed"]) - 1
            if j >= 0 and lo_hi[0] <= xs[j][1] < lo_hi[1]:
                keep.append(e)
        print("  fascia {}: {:,} eventi".format(a.cap_bucket, len(keep)))
        events = keep

    print("classificazione CMP...", flush=True)
    history = json.loads(HISTORY.read_text(encoding="utf-8"))
    labels = build_labels(events, history)
    for e in events:
        per = [labels.get((o, int(e["filed"][:4]))) for o in e["owners"]]
        per = [p for p in per if p]
        e["labels"] = per
        e["label"] = next((c for c in PRECEDENCE if c in per), None)
        e["label3"] = THREE.get(e["label"]) if e["label"] else None

    print("rendimenti...", flush=True)
    measure(events, bench, fx, horizons, a.cost_bps)
    variants = [("(a) tutti gli eventi", events),
                ("(b) un evento per emittente, cooldown 126gg",
                 cooldown_filter(events))]

    run_date = date.today().isoformat()
    tag = ""
    if a.gate != "none":
        tag += "-" + a.gate
    if a.cap_bucket != "all":
        tag += "-" + a.cap_bucket.replace("<", "lt").replace(">", "gt")
    run_date = run_date + tag
    out_dir = Path(a.out) if a.out else REPORTS
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "backtest-event-time-{}.csv".format(run_date)).open(
            "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        cols = (["cik", "ticker", "issuer", "filed", "t0", "buyers", "usd",
                 "label", "label3", "flag"]
                + ["ret_{}".format(h) for h in horizons]
                + ["exc_{}".format(h) for h in horizons]
                + ["excnet_{}".format(h) for h in horizons])
        w.writerow(cols)
        for e in sorted(events, key=lambda e: e["filed"]):
            w.writerow([e["cik"], e["ticker"] or "", e["name"][:60], e["filed"],
                        e.get("t0", ""), e["buyers"], "{:.0f}".format(e["usd"]),
                        e.get("label") or "", e.get("label3") or "",
                        e.get("flag", "")]
                       + ["{:.6f}".format(e[k]) if k in e else ""
                          for k in (["ret_{}".format(h) for h in horizons]
                                    + ["exc_{}".format(h) for h in horizons]
                                    + ["excnet_{}".format(h) for h in horizons])])

    print("curva event-time...", flush=True)
    curves, counts = event_curve(variants[1][1], bench, fx)
    svg = svg_curve(curves, counts, out_dir / "backtest-event-time-{}.svg".format(run_date))
    with (out_dir / "backtest-event-time-curve-{}.csv".format(run_date)).open(
            "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        labs = sorted(curves)
        w.writerow(["day"] + labs + ["n_" + l for l in labs])
        for k in range(127):
            w.writerow([k] + ["{:.6f}".format(curves[l][k])
                              if curves[l][k] == curves[l][k] else "" for l in labs]
                       + ["{:.0f}".format(counts[l][k]) for l in labs])

    shadow_missing, shadow_have = panel_shadow(events)
    rep = build_report(events, variants, horizons, sym, a, run_date, svg,
                       shadow_missing, shadow_have, curves, counts)
    p = out_dir / "backtest-event-time-{}.md".format(run_date)
    p.write_text(rep, encoding="utf-8")
    print("\nscritto {}".format(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
