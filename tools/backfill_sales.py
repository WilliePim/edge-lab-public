"""Extract insider SALES from the quarterly ZIPs into state/backfill/sales.jsonl.

For research only. Nothing in the live pipeline is touched: parse.py still
filters to open-market buys, and the scanner never reads this file. It exists so
that net-consensus and the sell side of Cohen-Malloy-Pomorski become answerable
without another download.

The schema mirrors form4_raw exactly, field for field, so anything already
written against the purchases corpus reads this one unchanged. The only
difference is the sign of what happened.

WHY THIS COSTS NOTHING. backfill_fetch.py:191 kept only TRANS_CODE == "P" and
dropped everything else, but the ZIPs it downloaded were never thrown away:
481 MB, 45 quarters, sitting in state/backfill/zips. The sales have been on
disk the whole time, unread.

Co-filers are expanded, one record per (transaction row x reporting owner),
exactly as the purchases corpus does -- (accession, txn_index) stays the
identity of the underlying economic trade, so anything summing value must
dedupe on it just as cluster.economic_txns does for buys.
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

#  STATE was `from backfill_fetch import STATE`. That module built the corpus
#  and the v3 prune removed it; the path is three tokens and inlining it is
#  cheaper than keeping a fetcher alive to hold a constant.
STATE = Path(__file__).resolve().parents[1] / "state" / "backfill"
import re as _re

#  Both copied from cmp_calendar_time before the prune removed it.
PLAN = _re.compile(r"10\s*b5[\s\-]*1", _re.I)
MONTHS_ABBR = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
     "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}


def _bulk_date(s):
    try:
        d, m, y = s.strip().split("-")
        return date(int(y), MONTHS_ABBR[m.upper()], int(d))
    except (ValueError, KeyError, AttributeError):
        return None

ZIPS = STATE / "zips"
OUT = STATE / "sales.jsonl"
PRICES = STATE / "prices"


def rows(z, name):
    with z.open(name) as fh:
        yield from csv.DictReader(
            io.TextIOWrapper(fh, encoding="utf-8", errors="replace"),
            delimiter="\t")


def main() -> int:
    n = 0
    issuers = set()
    with OUT.open("w", encoding="utf-8") as out:
        for zp in sorted(ZIPS.glob("*.zip")):
            with zipfile.ZipFile(zp) as z:
                names = set(z.namelist())
                if not {"SUBMISSION.tsv", "REPORTINGOWNER.tsv",
                        "NONDERIV_TRANS.tsv"} <= names:
                    continue
                sub, plan = {}, set()
                for r in rows(z, "SUBMISSION.tsv"):
                    a = r["ACCESSION_NUMBER"]
                    fd = _bulk_date(r.get("FILING_DATE") or "")
                    sub[a] = {
                        "issuer_cik": (r.get("ISSUERCIK") or "").strip(),
                        "issuer_name": (r.get("ISSUERNAME") or "").strip(),
                        "ticker": (r.get("ISSUERTRADINGSYMBOL") or "").strip().upper(),
                        "filed_date": fd.isoformat() if fd else None,
                    }
                    if (r.get("AFF10B5ONE") or "").strip().upper() in ("1", "Y", "TRUE"):
                        plan.add(a)
                if "FOOTNOTES.tsv" in names:
                    for r in rows(z, "FOOTNOTES.tsv"):
                        if PLAN.search(r.get("FOOTNOTE_TXT") or ""):
                            plan.add(r["ACCESSION_NUMBER"])

                owners = {}
                for r in rows(z, "REPORTINGOWNER.tsv"):
                    rel = r.get("RPTOWNER_RELATIONSHIP") or ""
                    owners.setdefault(r["ACCESSION_NUMBER"], []).append({
                        "owner_cik": (r.get("RPTOWNERCIK") or "").strip(),
                        "owner_name": (r.get("RPTOWNERNAME") or "").strip(),
                        "officer_title": (r.get("RPTOWNER_TITLE") or "").strip(),
                        "is_director": "Director" in rel,
                        "is_officer": "Officer" in rel,
                        "is_ten_pct": "TenPercent" in rel,
                    })

                for r in rows(z, "NONDERIV_TRANS.tsv"):
                    a = r["ACCESSION_NUMBER"]
                    if a not in sub or a not in owners:
                        continue
                    if (r.get("TRANS_CODE") or "").strip().upper() != "S":
                        continue
                    if (r.get("TRANS_ACQUIRED_DISP_CD") or "").strip().upper() != "D":
                        continue
                    td = _bulk_date(r.get("TRANS_DATE") or "")
                    if td is None:
                        continue
                    try:
                        sh = float(r.get("TRANS_SHARES") or 0)
                        px = float(r.get("TRANS_PRICEPERSHARE") or 0)
                        aft = float(r.get("SHRS_OWND_FOLWNG_TRANS") or 0)
                    except ValueError:
                        continue
                    s = sub[a]
                    if s["issuer_cik"]:
                        issuers.add(s["issuer_cik"].lstrip("0"))
                    for o in owners[a]:
                        rec = {
                            "accession": a,
                            "filed_date": s["filed_date"],
                            "is_10b5_1": a in plan,
                            "issuer_cik": s["issuer_cik"],
                            "issuer_name": s["issuer_name"],
                            "ticker": s["ticker"],
                            "price": px,
                            "shares": sh,
                            "shares_owned_after": aft,
                            "transaction_date": td.isoformat(),
                            "txn_index": int(r.get("NONDERIV_TRANS_SK") or 0),
                            "value": sh * px,
                        }
                        rec.update(o)
                        out.write(json.dumps(rec, sort_keys=True) + "\n")
                        n += 1

    size = OUT.stat().st_size
    print("scritto {}".format(OUT))
    print("  {:,} record di vendita, {:.1f} MB".format(n, size / 1e6))

    #  The point of the count: a net-consensus study needs prices for every
    #  issuer on BOTH sides, and the price panel was only ever built for
    #  issuers that had a purchase over $25,000.
    have = {p.stem.upper() for p in PRICES.glob("*.csv")}
    tick_with_sales = set()
    tick_missing = set()
    with OUT.open(encoding="utf-8") as fh:
        for line in fh:
            t = json.loads(line).get("ticker") or ""
            if not t or t in ("NONE", "N/A", "[NONE]"):
                continue
            tick_with_sales.add(t)
            if t not in have:
                tick_missing.add(t)
    print("  emittenti (ticker) con vendite: {:,}".format(len(tick_with_sales)))
    print("  di cui SENZA serie prezzi nel panel: {:,} ({:.1f}%)".format(
        len(tick_missing),
        100 * len(tick_missing) / len(tick_with_sales) if tick_with_sales else 0))
    print("  ticker con serie prezzi sul disco: {:,}".format(len(have)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
