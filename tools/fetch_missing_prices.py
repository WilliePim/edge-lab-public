"""Fetch prices for the live issuers the panel never asked for.

The price panel was built (by a backfill script since removed) from `form4_raw`, which is the corpus AFTER
the $25,000 floor. Everything below that floor -- 56% of all purchases -- was
never in the ticker list, so its issuers have no price series and every table in
this repo silently drops them.

A survivorship measurement (not included in this repository) separated those into two groups. The delisted ones
are gone and yfinance will not return them. The other group is **2,575 tickers
of companies that are still filing with the SEC**, carrying 73,075 purchases,
which the source was simply never asked about. That is what this fetches.

Same source, same window, same output format as backfill_prices.py -- START
2014-01-01, auto_adjust=False, the Adj Close column, one CSV per ticker with an
`adj_close` header. A series written any other way would not be comparable to
the ones already there, and the whole point is to extend the panel, not to
start a second one.

Failures are appended to state/backfill/missing_prices.jsonl with a reason, the
same file and the same discipline: a ticker with no prices is a fact about the
dataset, not something to drop in silence.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

#  STATE was `from backfill_fetch import STATE`. That module built the corpus
#  and the v3 prune removed it; the path is three tokens and inlining it is
#  cheaper than keeping a fetcher alive to hold a constant.
STATE = Path(__file__).resolve().parents[1] / "state" / "backfill"

PRICES = STATE / "prices"
MISSING = STATE / "missing_prices.jsonl"
TARGETS = STATE / "missing_live_tickers.json"
START = "2014-01-01"
BATCH = 40


def main() -> int:
    import yfinance as yf

    if not TARGETS.exists():
        raise SystemExit(
            "manca {}: generalo prima con la lista dei ticker vivi".format(TARGETS))
    todo = json.loads(TARGETS.read_text(encoding="utf-8"))
    todo = [t for t in todo
            if not (PRICES / "{}.csv".format(t.replace("/", "_"))).exists()]
    print("da scaricare: {:,}".format(len(todo)), flush=True)

    end = date.today().isoformat()
    fh = MISSING.open("a", encoding="utf-8")
    ok, fail, reasons = 0, 0, {}
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            df = yf.download(chunk, start=START, end=end, auto_adjust=False,
                             progress=False, threads=True, group_by="ticker")
        except Exception as e:                                 # noqa: BLE001
            for t in chunk:
                fh.write(json.dumps({"ticker": t,
                                     "reason": "download error"}) + "\n")
                reasons[t] = "download error"
                fail += 1
            fh.flush()
            continue

        for t in chunk:
            try:
                sub = df[t] if len(chunk) > 1 else df
                col = "Adj Close" if "Adj Close" in sub.columns else "Close"
                ser = sub[col].dropna()
            except (KeyError, TypeError):
                ser = None
            if ser is None or len(ser) < 20:
                why = "no data" if ser is None else "only {} bars".format(len(ser))
                fh.write(json.dumps({"ticker": t, "reason": why}) + "\n")
                reasons[t] = why
                fail += 1
                continue
            out = PRICES / "{}.csv".format(t.replace("/", "_"))
            tmp = out.with_suffix(".csv.tmp")
            ser.to_csv(tmp, header=["adj_close"])
            os.replace(tmp, out)
            ok += 1
        fh.flush()
        if (i // BATCH) % 10 == 0:
            print("  {:,}/{:,}  ok {:,} | falliti {:,}".format(
                i + len(chunk), len(todo), ok, fail), flush=True)
    fh.close()

    (STATE / "missing_live_failures.json").write_text(
        json.dumps(reasons, indent=1, sort_keys=True), encoding="utf-8")
    tot = ok + fail
    print("\nriusciti {:,} | falliti {:,} ({:.1f}%)".format(
        ok, fail, 100 * fail / tot if tot else 0))
    print("motivi salvati in {}".format(STATE / "missing_live_failures.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
