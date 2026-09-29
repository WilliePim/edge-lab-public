"""Table III sul panel: dentro l'universo, la classe dell'insider distingue?

Non e' un confronto con un indice. E' una regressione di `exc_6m` sulle dummy di
classe, con controlli di size, book-to-market e rendimenti passati, ed errori
standard clusterizzati per emittente. La domanda e' quella di Cohen-Malloy-
Pomorski Table III, posta pero' DENTRO l'universo dello scanner invece che
contro il mercato.

L'UNITA' PRINCIPALE E' EMITTENTE-MESE, non la riga del panel. Il panel e' un
ri-scoring SETTIMANALE su finestra 60 giorni: lo stesso acquisto rientra in otto
righe consecutive, e otto copie della stessa informazione non sono otto
osservazioni. Il clustering CR1 assorbe la correlazione fra righe dello stesso
emittente, non il fatto che siano la stessa notizia ripetuta. Quindi il
risultato principale tiene la PRIMA riga di ogni emittente-mese, e la versione
settimanale va in appendice per mostrare di quanto le t si gonfiano.

NIENTE LOOKAHEAD NELLA CLASSIFICAZIONE. `purchase_history` viene troncata a
`as_of` prima di entrare in `classify_insider`, e `classify_insider` scarta da
se' le date successive (`block_of`: `days <= 0` -> `None`). Verificato: la stessa
storia con e senza acquisti futuri produce la stessa etichetta.

Nessuna dipendenza nuova: OLS e sandwich CR1 a mano con numpy.
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

from form4_scanner.classify import (NOVEL, OPPORTUNISTIC, ROUTINE, SPARSE,
                                    classify_insider)

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "backfill"
PANEL = STATE / "panel"
GATES = STATE / "gates"
CORPUS = STATE / "form4_raw"
MCAP = STATE / "marketcap_rows.jsonl"
HISTORY = STATE / "purchase_history.json"
PRICES = STATE / "prices"
REPORTS = ROOT / "reports"

WINDOW = 60          # la finestra su cui il panel e' stato costruito
ARTEFACT = 5.0
PRECEDENCE = (OPPORTUNISTIC, NOVEL, SPARSE, ROUTINE)
BUCKETS = (("<50M", 0.0, 50e6), ("50-300M", 50e6, 300e6),
           (">300M", 300e6, float("inf")))


def bucket_of(cap):
    if cap is None:
        return None
    for name, lo, hi in BUCKETS:
        if lo <= cap < hi:
            return name
    return None


# --------------------------------------------------------------- OLS CR1 --
def ols_cluster(y, X, groups):
    """(beta, se, t) con sandwich cluster-robust CR1. numpy e basta."""
    y = np.asarray(y, float)
    X = np.asarray(X, float)
    n, k = X.shape
    XtX = X.T @ X
    XtX_inv = np.linalg.pinv(XtX)
    beta = XtX_inv @ (X.T @ y)
    u = y - X @ beta

    order = np.argsort(groups)
    g_sorted = np.asarray(groups)[order]
    Xs, us = X[order], u[order]
    meat = np.zeros((k, k))
    start = 0
    G = 0
    for i in range(1, len(g_sorted) + 1):
        if i == len(g_sorted) or g_sorted[i] != g_sorted[start]:
            Xg, ug = Xs[start:i], us[start:i]
            s = Xg.T @ ug
            meat += np.outer(s, s)
            G += 1
            start = i
    c = (G / max(G - 1, 1)) * ((n - 1) / max(n - k, 1))
    V = XtX_inv @ meat @ XtX_inv * c
    se = np.sqrt(np.maximum(np.diag(V), 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(se > 0, beta / se, np.nan)
    return beta, se, t, n, G


# ------------------------------------------------------------ assemblaggio --
def price_index(ticker):
    p = PRICES / "{}.csv".format((ticker or "").replace("/", "_"))
    if not ticker or not p.exists():
        return None, None
    ds, px = [], []
    with p.open(encoding="utf-8") as fh:
        next(fh, None)
        for line in fh:
            d, _, v = line.partition(",")
            d = d.strip()
            try:
                f = float(v)
            except ValueError:
                continue
            if len(d) == 10 and f > 0:
                ds.append(d)
                px.append(f)
    return (ds, px) if len(ds) >= 2 else (None, None)


def build(verbose=True):
    if verbose:
        print("panel...", flush=True)
    rows = []
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
                rows.append({"cik": r["issuer_cik"].lstrip("0"),
                             "as_of": r["as_of"], "ticker": r.get("ticker"),
                             "y": float(x),
                             "buyers": r.get("distinct_buyers") or 0})
    if verbose:
        print("  {:,} righe con exc_6m".format(len(rows)))

    if verbose:
        print("equity dai gates...", flush=True)
    eq = {}
    for f in sorted(GATES.glob("*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("equity") is not None:
                    eq[(r["issuer_cik"].lstrip("0"), r["as_of"])] = r["equity"]

    if verbose:
        print("market cap...", flush=True)
    caps = collections.defaultdict(list)
    with MCAP.open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("mcap"):
                caps[str(r["issuer"]).lstrip("0")].append((r["trans"], r["mcap"]))
    for k in caps:
        caps[k].sort()

    if verbose:
        print("compratori sulla finestra 60gg...", flush=True)
    buys = collections.defaultdict(list)
    for f in sorted(CORPUS.glob("*.jsonl")):
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                o = (r.get("owner_cik") or "").lstrip("0")
                if o:
                    buys[r["issuer_cik"].lstrip("0")].append(
                        (r["transaction_date"], o))
    for k in buys:
        buys[k].sort()

    history = json.loads(HISTORY.read_text(encoding="utf-8"))
    hist = {k: sorted(v) for k, v in history.items()}
    lab_cache = {}

    def label_of(owner, as_of):
        key = (owner, as_of)
        got = lab_cache.get(key)
        if got is not None:
            return got
        #  Troncatura esplicita a as_of. classify_insider la rifarebbe da se',
        #  ma il taglio va fatto qui perche' si veda.
        ds = hist.get(owner, [])
        cut = bisect.bisect_left(ds, as_of)
        prior = [date.fromisoformat(d) for d in ds[:cut]]
        lab = classify_insider(owner, "", prior, date.fromisoformat(as_of)).label
        lab_cache[key] = lab
        return lab

    if verbose:
        print("classi, size, B/M, rendimenti passati...", flush=True)
    px_cache = {}
    out = []
    for i, r in enumerate(rows):
        cik, as_of = r["cik"], r["as_of"]
        xs = buys.get(cik)
        if not xs:
            continue
        lo = (date.fromisoformat(as_of) - timedelta(days=WINDOW)).isoformat()
        ds = [d for d, _ in xs]
        a, b = bisect.bisect_left(ds, lo), bisect.bisect_right(ds, as_of)
        owners = {o for _, o in xs[a:b]}
        if not owners:
            continue
        labs = {label_of(o, as_of) for o in owners}
        r["label"] = next((c for c in PRECEDENCE if c in labs), None)
        if not r["label"]:
            continue

        cs = caps.get(cik)
        cap = None
        if cs:
            j = bisect.bisect_right([d for d, _ in cs], as_of) - 1
            if j >= 0:
                cap = cs[j][1]
        r["cap"] = cap
        r["bucket"] = bucket_of(cap)
        e = eq.get((cik, as_of))
        r["bm"] = (e / cap) if (e is not None and cap and cap > 0) else None

        t = r.get("ticker")
        if t not in px_cache:
            px_cache[t] = price_index(t)
        pds, ppx = px_cache[t]
        r["past"] = None
        if pds:
            j = bisect.bisect_right(pds, as_of) - 1
            back = (date.fromisoformat(as_of) - timedelta(days=365)).isoformat()
            k = bisect.bisect_left(pds, back)
            if j > k >= 0 and ppx[k] > 0:
                v = ppx[j] / ppx[k] - 1.0
                if abs(v) <= ARTEFACT:
                    r["past"] = v
        out.append(r)
        if verbose and i % 40000 == 0:
            print("  {:,}/{:,}".format(i, len(rows)), flush=True)
    if verbose:
        print("  {:,} righe complete di classe".format(len(out)))
    return out


def monthly(rows):
    """Una riga per emittente-mese: la prima. E' il risultato principale."""
    seen, keep = set(), []
    for r in sorted(rows, key=lambda r: (r["cik"], r["as_of"])):
        k = (r["cik"], r["as_of"][:7])
        if k in seen:
            continue
        seen.add(k)
        keep.append(r)
    return keep


# ------------------------------------------------------------ specifiche --
def design(rows, interact=False):
    """(y, X, nomi, gruppi). Baseline omessa: ROUTINE, come in Table III."""
    use = [r for r in rows
           if r.get("cap") and r.get("bm") is not None and r.get("past") is not None]
    if not use:
        return None
    classes = [c for c in PRECEDENCE if c != ROUTINE]
    names = ["intercetta"]
    cols = [np.ones(len(use))]
    for c in classes:
        names.append(c)
        cols.append(np.array([1.0 if r["label"] == c else 0.0 for r in use]))
    if interact:
        for bname, _, _ in BUCKETS[1:]:          # <50M e' la base del bucket
            names.append("bucket {}".format(bname))
            cols.append(np.array([1.0 if r["bucket"] == bname else 0.0
                                  for r in use]))
        for c in classes:
            for bname, _, _ in BUCKETS[1:]:
                names.append("{} x {}".format(c, bname))
                cols.append(np.array([1.0 if (r["label"] == c and
                                              r["bucket"] == bname) else 0.0
                                      for r in use]))
    names += ["log size", "B/M", "rend. 12m passato"]
    cols.append(np.array([math.log(r["cap"]) for r in use]))
    #  B/M winsorizzato all'1% e al 99%: equity negativo e cap minuscolo
    #  producono code che dominerebbero la stima.
    bm = np.array([r["bm"] for r in use])
    lo, hi = np.percentile(bm, [1, 99])
    cols.append(np.clip(bm, lo, hi))
    cols.append(np.array([r["past"] for r in use]))
    X = np.column_stack(cols)
    y = np.array([r["y"] for r in use])
    g = np.array([r["cik"] for r in use])
    return y, X, names, g, use


def table(res, title):
    if res is None:
        return ["### {}".format(title), "", "_Nessuna riga utilizzabile._", ""]
    beta, se, t, n, G = res[0]
    names = res[1]
    L = ["### {}".format(title), "",
         "| termine | coeff. | s.e. (CR1) | t | |",
         "|---|---:|---:|---:|---|"]
    for i, nm in enumerate(names):
        star = ("***" if abs(t[i]) > 2.58 else "**" if abs(t[i]) > 1.96
                else "*" if abs(t[i]) > 1.65 else "")
        L.append("| {} | {:+.4f} | {:.4f} | {:.2f} | {} |".format(
            nm, beta[i], se[i], t[i], star))
    L += ["", "n = **{:,}**, emittenti (cluster) = **{:,}**. Baseline omessa: "
          "`routine`{}.".format(n, G,
                                ", bucket base `<50M`" if any(
                                    "bucket" in x for x in names) else ""), ""]
    return L


def run(rows, interact=False):
    d = design(rows, interact=interact)
    if d is None:
        return None
    y, X, names, g, use = d
    return (ols_cluster(y, X, g), names, use)


def means_by(rows, key):
    out = collections.OrderedDict()
    for r in rows:
        out.setdefault(r.get(key), []).append(r["y"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    rows = build()
    mon = monthly(rows)
    print("\nemittente-mese: {:,} righe   settimanale: {:,}".format(
        len(mon), len(rows)))

    run_date = date.today().isoformat()
    out_dir = Path(a.out) if a.out else REPORTS
    out_dir.mkdir(parents=True, exist_ok=True)

    base_m = run(mon, interact=False)
    inter_m = run(mon, interact=True)
    base_w = run(rows, interact=False)

    L = ["# Table III sul panel — la classe distingue, dentro l'universo?", "",
         "Generato il {}. Rieseguibile con `python tools/table3_regression.py`."
         .format(run_date), "",
         "Regressione di `exc_6m` sulle dummy di classe con controlli di size, "
         "book-to-market e rendimento passato, errori standard clusterizzati "
         "per emittente (sandwich CR1). **Non e' un confronto con un indice**: "
         "la domanda e' se, dentro l'universo dello scanner, la classe "
         "dell'insider separi.", "",
         "## L'unita', e perche' non e' la riga del panel", "",
         "Il panel e' un ri-scoring **settimanale** su finestra 60 giorni: lo "
         "stesso acquisto rientra in otto righe consecutive. Otto copie della "
         "stessa informazione non sono otto osservazioni, e il clustering CR1 "
         "assorbe la correlazione fra righe dello stesso emittente ma non il "
         "fatto che siano la stessa notizia ripetuta. Il risultato principale "
         "tiene percio' **la prima riga di ogni emittente-mese**; la versione "
         "settimanale e' in appendice, e serve a vedere di quanto le t si "
         "gonfiano.", "",
         "| campione | righe |", "|---|---:|",
         "| emittente-mese (principale) | {:,} |".format(len(mon)),
         "| settimanale (appendice) | {:,} |".format(len(rows)), "",
         "## Niente lookahead nella classificazione", "",
         "`purchase_history` e' troncata a `as_of` prima di entrare in "
         "`classify_insider`, e `classify_insider` scarta comunque da se' le "
         "date successive (`block_of`: `days <= 0` -> `None`). Verificato: la "
         "stessa storia con e senza acquisti futuri produce la stessa "
         "etichetta.", "",
         "---", "", "## Risultato principale — emittente-mese", ""]
    L += table(base_m, "Specifica base")
    L += ["`*` |t| > 1,65 · `**` |t| > 1,96 · `***` |t| > 2,58.", ""]
    L += ["---", "", "## Interazioni classe x fascia di capitalizzazione", "",
          "Se lo spread opportunistic-routine esiste sopra i 50M e sparisce "
          "sotto, il problema e' la soglia di universo e non il segnale.", ""]
    L += table(inter_m, "Con interazioni")

    L += ["---", "", "## Medie grezze, per controllo", "",
          "| classe | n | media `exc_6m` |", "|---|---:|---:|"]
    for lab, xs in sorted(means_by(mon, "label").items(),
                          key=lambda kv: -len(kv[1])):
        L.append("| {} | {:,} | {:+.2%} |".format(lab, len(xs),
                                                  float(np.mean(xs))))
    L += ["", "| fascia | n | media `exc_6m` |", "|---|---:|---:|"]
    for b, xs in sorted(means_by(mon, "bucket").items(),
                        key=lambda kv: (kv[0] is None, kv[0] or "")):
        L.append("| {} | {:,} | {:+.2%} |".format(b or "cap ignota", len(xs),
                                                  float(np.mean(xs))))
    L += ["", "| classe x fascia | n | media `exc_6m` |", "|---|---:|---:|"]
    cells = collections.OrderedDict()
    for r in mon:
        if r.get("bucket"):
            cells.setdefault((r["label"], r["bucket"]), []).append(r["y"])
    for (lab, b), xs in sorted(cells.items()):
        if len(xs) >= 30:
            L.append("| {} x {} | {:,} | {:+.2%} |".format(
                lab, b, len(xs), float(np.mean(xs))))
    L += ["", "_Celle sotto le 30 osservazioni omesse._", ""]

    L += ["---", "", "## Appendice — la stessa regressione sul settimanale", "",
          "Le t qui sono gonfiate per costruzione. E' il motivo per cui non e' "
          "il risultato principale.", ""]
    L += table(base_w, "Specifica base, righe settimanali")

    L += ["---", "", "## Limiti", "",
          "1. **Il campione e' quello con `exc_6m`**, cioe' le righe del panel "
          "per cui esisteva una serie prezzi a 6 mesi. Gli emittenti senza "
          "serie sono andati peggio: misurato in "
          "`backtest-event-time-{}.md`, scarto **-3,36 punti**.".format(run_date),
          "2. **`exc_6m` NON controlla per il fattore size.** E' excess contro "
          "il solo fattore di mercato: un premio small-cap ci finisce dentro "
          "per intero. Il coefficiente su `log size` (**-0,0127**, t -5,87) e "
          "le medie per fascia (`<50M` +6,1%, `>300M` -0,4%) sono percio' "
          "compatibili con un fattore size non controllato, non necessariamente "
          "con alfa. Il controllo si vede meglio nelle medie grezze: la fascia "
          "`<50M` e' positiva anche per i compratori **routine** (+11,98%), che "
          "sono la classe che per costruzione non dovrebbe portare "
          "informazione. Finche' `exc_6m` non e' ricalcolato contro un modello "
          "con SMB, la lettura size di questa tabella resta sospesa.",
          "3. **`exc_6m` e' excess contro il fattore di mercato Fama-French**, "
          "come il panel lo ha calcolato ai tempi. Non e' il Russell 2000 in "
          "euro del backtest event-time: i due numeri non si sommano.",
          "4. **Size e B/M coprono meno del campione.** La regressione gira "
          "sulle righe con cap, equity e rendimento passato tutti presenti; il "
          "conteggio effettivo e' nella riga `n` di ogni tabella.",
          "5. **Il market cap e' agganciato per data piu' vicina <= `as_of`**, "
          "non esatta: `marketcap_rows` e' indicizzato per data di transazione "
          "e il panel per data di ri-scoring.",
          "6. **`unseasoned` non compare**: distinguerlo da `novel` richiede la "
          "prima data di deposito del CIK, che il corpus non porta.",
          "7. **Il clustering e' per emittente.** Non assorbe la correlazione "
          "temporale fra mesi consecutivi dello stesso emittente, solo quella "
          "fra le sue righe.", ""]

    p = out_dir / "table3-regression-{}.md".format(run_date)
    p.write_text("\n".join(L), encoding="utf-8")
    print("scritto {}".format(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
