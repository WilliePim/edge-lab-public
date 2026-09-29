"""Phase 2B: the two sign gates, replayed point-in-time.

Records what the gates WOULD have blocked without excluding anything, so Phase 4
can compare the returns of blocked and unblocked names. A gate that removes good
outcomes is worth knowing about before it removes them for real.

POINT-IN-TIME IS THE WHOLE DIFFICULTY. XBRL facts carry `end` (the period they
describe) and `filed` (when they became public). A fact about Q2 filed in August
did not exist in July, and using it to score a July observation is lookahead of
the most dangerous kind, because it looks like ordinary data. Every fact is
filtered on `filed <= as_of`, not on `end <= as_of`.

That is also why `companyfacts` is fetched instead of `companyconcept`: one
request per issuer instead of seven, and the response carries `filed` on every
fact. 7,408 issuers, ~18 minutes. The raw response is large, so only the concepts
the gates need are distilled to disk and the rest discarded.

The two predicates (predicates, not validated; neither runs in the scanner's
pipeline):
  NO_EBITDA_WITH_NET_DEBT   net debt > 0 and EBITDA <= 0            -- would block
  NEGATIVE_EQUITY_LEVERED   equity < 0 AND net_debt/EBITDA > 4.0    -- advisory
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

ANNUAL_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A"}

#  SELF-CONTAINED BY DESIGN. The v3 prune removes calibrate_leverage.py
#  and backfill_fetch.py; what this file needed from them is inlined below,
#  copied verbatim before their removal. A gate measurement that stops
#  working when the calibration scaffolding is cleared is not a measurement
#  you can run again.

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "state" / "backfill" / "checkpoint.json"

STATE = ROOT / "state" / "backfill"


def load_checkpoint() -> dict:
    if CHECKPOINT.exists():
        return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    return {"phase1_done": [], "phase2_done": [], "phase3_done": []}


def save_checkpoint(cp: dict) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    tmp = CHECKPOINT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cp, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, CHECKPOINT)


INSTANT = {
    "equity":  ["StockholdersEquity",
                "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "lt_debt": ["LongTermDebtNoncurrent", "LongTermDebt",
                "DebtLongtermAndShorttermCombinedAmount"],
    "st_debt": ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"],
    "cash":    ["CashAndCashEquivalentsAtCarryingValue",
                "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "assets":  ["Assets"],
}


DURATION = {
    "ebit": ["OperatingIncomeLoss"],
    "da":   ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"],
}


def _d(raw):
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _facts(client, cik, tag, as_of):
    data = client.company_concept(cik, "us-gaap", tag)
    if not data:
        return []
    out = []
    for rows in (data.get("units") or {}).values():
        for r in rows:
            if str(r.get("form") or "").strip().upper() not in ANNUAL_FORMS:
                continue
            end, val = _d(r.get("end")), r.get("val")
            if end is None or val is None or end > as_of:
                continue
            out.append((end, _d(r.get("start")), float(val), r.get("filed")))
    return sorted(out)


def latest_instant(client, cik, concept, as_of):
    """Most recent balance-sheet value for a concept, first chain hit wins."""
    for tag in INSTANT[concept]:
        rows = [r for r in _facts(client, cik, tag, as_of) if r[1] is None]
        if rows:
            return rows[-1][2], rows[-1][0], tag
    return None, None, None


def trailing_four_quarters(client, cik, concept, as_of):
    """Sum of the four most recent QUARTERLY facts -- EBITDA is not a GAAP tag."""
    for tag in DURATION[concept]:
        rows = [r for r in _facts(client, cik, tag, as_of)
                if r[1] is not None and 60 <= (r[0] - r[1]).days <= 100]
        if len(rows) >= 4:
            last4 = rows[-4:]
            return sum(r[2] for r in last4), last4[-1][0], tag
    return None, None, None

from form4_scanner.edgar import EdgarClient
from form4_scanner.xbrl import ebitda, leverage, net_debt

OBS = STATE / "observations"
XBRL = STATE / "xbrl"
GATES = STATE / "gates"
LEVERAGE_CEILING = 4.0
FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A"}
WANTED = {t for v in INSTANT.values() for t in v} | {t for v in DURATION.values() for t in v}


def distil(cik: str, client: EdgarClient):
    """Only the concepts the gates read, with `filed` kept on every fact."""
    XBRL.mkdir(parents=True, exist_ok=True)
    out = XBRL / f"{int(cik):010d}.json"
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    raw = client.get_json(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json")
    facts: dict = {}
    for tag, blob in ((raw or {}).get("facts", {}).get("us-gaap", {}) or {}).items():
        if tag not in WANTED:
            continue
        rows = []
        for unit_rows in (blob.get("units") or {}).values():
            for r in unit_rows:
                if str(r.get("form", "")).upper() not in FORMS:
                    continue
                if r.get("end") is None or r.get("val") is None or not r.get("filed"):
                    continue
                rows.append([r["end"], r.get("start"), float(r["val"]), r["filed"]])
        if rows:
            facts[tag] = sorted(rows)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(facts, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, out)
    return facts


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(a) - date.fromisoformat(b)).days


def instant(facts, concept, as_of: str):
    """Latest balance-sheet value KNOWN at as_of. `filed`, never `end`."""
    for tag in INSTANT[concept]:
        rows = [r for r in facts.get(tag, ())
                if r[1] is None and r[3] <= as_of and r[0] <= as_of]
        if rows:
            return rows[-1][2]
    return None


def four_quarters(facts, concept, as_of: str):
    """Sum of the four most recent quarterly facts known at as_of."""
    for tag in DURATION[concept]:
        rows = [r for r in facts.get(tag, ())
                if r[1] is not None and r[3] <= as_of and r[0] <= as_of
                and 60 <= _days(r[0], r[1]) <= 100]
        if len(rows) >= 4:
            return sum(r[2] for r in rows[-4:])
    return None


def evaluate(facts, as_of: str) -> dict:
    eq = instant(facts, "equity", as_of)
    lt = instant(facts, "lt_debt", as_of)
    st = instant(facts, "st_debt", as_of)
    cash = instant(facts, "cash", as_of)
    assets = instant(facts, "assets", as_of)
    ebit = four_quarters(facts, "ebit", as_of)
    da = four_quarters(facts, "da", as_of)

    nd = net_debt(lt, st, cash, balance_sheet_read=(eq is not None or assets is not None))
    eb = ebitda(ebit, da)
    lev = leverage(nd, eb)

    #  Two predicates, both computed and recorded, neither validated: this
    #  replay is descriptive (no pre-registration, no matched control), so it
    #  cannot validate either one. `gate_hits` and `advisory` are labels on the
    #  record; nothing here excludes a name.
    hits, advisory = [], []
    if nd.value is not None and nd.value > 0 and eb.value is not None and eb.value <= 0:
        hits.append("NO_EBITDA_WITH_NET_DEBT")
    if (eq is not None and eq < 0
            and lev.value is not None and lev.value > LEVERAGE_CEILING):
        advisory.append("NEGATIVE_EQUITY_LEVERED")
    return {"equity": eq, "net_debt": nd.value, "ebitda": eb.value,
            "leverage": lev.value, "gate_hits": hits, "advisory": advisory,
            "xbrl_available": bool(facts)}


def main() -> int:
    client = EdgarClient(sys.argv[1])
    GATES.mkdir(parents=True, exist_ok=True)
    cp = load_checkpoint()
    done = set(cp.get("gates_done", []))
    cache: dict = {}
    n = 0

    for src in sorted(OBS.glob("*.jsonl")):
        qkey = src.stem
        out = GATES / f"{qkey}.jsonl"
        if qkey in done and out.exists():
            continue
        if not src.exists():
            #  The glob is taken once and the run lasts hours; a quarter deleted
            #  in the meantime -- as 2026-Q2 was, once it turned out its 60-day
            #  window could not be filled -- must not take the whole pass down
            #  after it has already written 45 good files.
            print(f"[{qkey}] sparito durante la corsa, salto", flush=True)
            continue
        #  One evaluation per (issuer, as_of): a weekly cadence means the same
        #  issuer recurs, and the facts do not change between two Mondays in the
        #  same quarter -- but the filter is still on `filed <= as_of`, so a
        #  filing landing mid-quarter does move the answer.
        seen: dict = {}
        tmp = out.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as fh:
            for line in src.open(encoding="utf-8"):
                o = json.loads(line)
                cik, as_of = o["issuer_cik"], o["as_of"]
                if cik not in cache:
                    try:
                        cache[cik] = distil(cik, client)
                    except Exception as e:
                        print(f"  XBRL fallito {cik}: {e}", flush=True)
                        cache[cik] = {}
                key = (cik, as_of)
                if key not in seen:
                    seen[key] = evaluate(cache[cik], as_of)
                rec = {"as_of": as_of, "issuer_cik": cik, "ticker": o["ticker"]}
                rec.update(seen[key])
                fh.write(json.dumps(rec, sort_keys=True, allow_nan=False) + "\n")
                n += 1
        os.replace(tmp, out)
        done.add(qkey)
        cp["gates_done"] = sorted(done)
        save_checkpoint(cp)
        print(f"[{qkey}] {len(seen):,} coppie   emittenti in cache "
              f"{len(cache):,}   righe {n:,}", flush=True)

    print(f"\nFASE 2B COMPLETA: {n:,} righe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
