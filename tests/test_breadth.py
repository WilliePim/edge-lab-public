"""Tests for the live breadth counts.

These do NOT re-verify the Phase 1 golden weeks. Those came from the SEC bulk
quarterly tables, and this module measures the live XML path, which counts
different things on purpose -- see the divergence note in breadth.py. Checking
one against the other would assert that two deliberately different measures
agree.

What is asserted instead is the behaviour that would silently corrupt the series:
which date field keys which count, that co-filers do not multiply the totals, and
that a re-observation appends rather than overwrites.
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner.breadth import BreadthTally, week_start, write_weeks


class T:
    """Duck-typed Transaction: only the fields the tally reads."""

    def __init__(self, issuer="1", txn_date=None, accession="acc1", idx=0,
                 value=100_000.0):
        self.issuer_cik = issuer
        self.txn_date = txn_date
        self.accession = accession
        self.txn_index = idx
        self.value = value


# --------------------------------------------------------------------------
print("[breadth] the Monday of the week, including on a Monday")
check("a Wednesday maps back to its Monday",
      week_start(date(2022, 5, 11)) == date(2022, 5, 9),
      str(week_start(date(2022, 5, 11))))
check("a Monday is its own week start",
      week_start(date(2022, 5, 9)) == date(2022, 5, 9))
check("a Sunday belongs to the week that started six days earlier",
      week_start(date(2022, 5, 15)) == date(2022, 5, 9),
      str(week_start(date(2022, 5, 15))))

print("[breadth] numerator and denominator key on DIFFERENT date fields")
#  The case that makes the distinction visible: a buy made in one week and filed
#  in the next. The issuer must count in the FILING week's denominator and in the
#  TRANSACTION week's numerator -- never the same week for both.
t = BreadthTally(min_value=25_000)
bought = date(2022, 5, 5)          # Thursday, week of 2022-05-02
filed = date(2022, 5, 10)          # Tuesday,  week of 2022-05-09
txn = T(issuer="AAA", txn_date=bought)
t.observe(filed, [txn], [txn])
weeks = {w.week_start: w for w in t.weeks()}
check("the filing lands in the denominator of the week it was FILED",
      weeks["2022-05-09"].issuers_filing == 1,
      str(weeks["2022-05-09"].issuers_filing))
check("...and not in the denominator of the week it was bought",
      weeks.get("2022-05-02") is None
      or weeks["2022-05-02"].issuers_filing == 0,
      str(weeks["2022-05-02"].issuers_filing))
check("the buy lands in the numerator of the week it was BOUGHT",
      weeks["2022-05-02"].issuers_buying == 1,
      str(weeks["2022-05-02"].issuers_buying))
check("...and not in the numerator of the week it was filed",
      weeks["2022-05-09"].issuers_buying == 0,
      str(weeks["2022-05-09"].issuers_buying))

print("[breadth] an issuer that filed but did not buy still counts below")
t = BreadthTally(min_value=25_000)
sold = T(issuer="BBB", txn_date=date(2022, 5, 10))
t.observe(date(2022, 5, 10), [sold], [])       # parsed, but not a qualifying buy
w = t.weeks()[0]
check("denominator counts it", w.issuers_filing == 1, str(w.issuers_filing))
check("numerator does not", w.issuers_buying == 0, str(w.issuers_buying))

print("[breadth] an issuer filing three times in a week is ONE issuer")
t = BreadthTally(min_value=25_000)
for i in range(3):
    x = T(issuer="CCC", txn_date=date(2022, 5, 10), accession=f"a{i}", idx=i)
    t.observe(date(2022, 5, 10), [x], [x])
w = t.weeks()[0]
check("the denominator is a set, not a counter", w.issuers_filing == 1,
      str(w.issuers_filing))
check("the numerator is a set too", w.issuers_buying == 1, str(w.issuers_buying))
check("filings are still counted individually", w.filings == 3, str(w.filings))

print("[breadth] co-filers do not multiply the totals")
#  The live failure this guards: four affiliated Forbion vehicles on ONE accession
#  turned $64.8M of buying into $259.2M. The XML path emits one Transaction per
#  (row x reporting owner); the bulk tables are normalised. Both counts are kept
#  so the splice between the two series can be measured.
t = BreadthTally(min_value=25_000)
joint = [T(issuer="DDD", txn_date=date(2022, 5, 10), accession="joint", idx=0,
           value=64_800_000.0) for _ in range(4)]
t.observe(date(2022, 5, 10), joint, joint)
w = t.weeks()[0]
check("the naive row count sees all four co-filers", w.txns_rows == 4,
      str(w.txns_rows))
check("the economic count collapses them to one trade", w.txns_economic == 1,
      str(w.txns_economic))
check("the total is the trade, not the trade times four",
      w.total_buy_usd == 64_800_000.0, f"{w.total_buy_usd:,.0f}")
check("the median is a median of trades, not of rows",
      w.median_buy_usd == 64_800_000.0, str(w.median_buy_usd))

print("[breadth] two distinct trades on one accession are two trades")
t = BreadthTally(min_value=25_000)
rows = [T(issuer="EEE", txn_date=date(2022, 5, 10), accession="same", idx=0,
          value=100_000.0),
        T(issuer="EEE", txn_date=date(2022, 5, 10), accession="same", idx=1,
          value=300_000.0)]
t.observe(date(2022, 5, 10), rows, rows)
w = t.weeks()[0]
check("txn_index keeps them apart", w.txns_economic == 2, str(w.txns_economic))
check("the median is of both values", w.median_buy_usd == 200_000.0,
      str(w.median_buy_usd))

print("[breadth] a buy with no transaction date is dropped, not guessed")
t = BreadthTally(min_value=25_000)
undated = T(issuer="FFF", txn_date=None)
t.observe(date(2022, 5, 10), [undated], [undated])
w = t.weeks()[0]
check("it still counts in the denominator", w.issuers_filing == 1)
check("it does not get assigned to a week it might not belong to",
      w.issuers_buying == 0, str(w.issuers_buying))

print("[breadth] the current week is flagged incomplete")
with tempfile.TemporaryDirectory() as tmp:
    run_on = date(2022, 5, 11)                 # Wednesday, week of 2022-05-09
    t = BreadthTally(min_value=25_000)
    for d in (date(2022, 5, 4), date(2022, 5, 11)):
        x = T(issuer="FFF", txn_date=d, accession=f"a{d}")
        t.observe(d, [x], [x])
    p = write_weeks(t, tmp, run_on, window_days=30, scanner_sha="deadbee")
    rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]
    by = {r["week_start"]: r for r in rows}
    check("the week the run happened in is marked incomplete",
          by["2022-05-09"]["week_complete"] is False,
          str(by["2022-05-09"]["week_complete"]))
    check("an earlier, closed week is marked complete",
          by["2022-05-02"]["week_complete"] is True,
          str(by["2022-05-02"]["week_complete"]))
    check("every row carries the git sha it was produced by",
          all(r["scanner_git_sha"] == "deadbee" for r in rows))
    check("every row carries the window that produced it",
          all(r["window_days"] == 30 for r in rows))

    print("[breadth] re-observing a week APPENDS, it never rewrites")
    #  A week keeps growing after it closes: Form 4 has a two-business-day
    #  deadline and late filings happen. Overwriting the earlier count would
    #  destroy the only evidence of how much arrived late.
    t2 = BreadthTally(min_value=25_000)
    for d in (date(2022, 5, 4), date(2022, 5, 11)):
        for i in range(2):
            x = T(issuer=f"H{i}", txn_date=d, accession=f"b{d}{i}", idx=i)
            t2.observe(d, [x], [x])
    write_weeks(t2, tmp, run_on, window_days=30, scanner_sha="deadbee")
    again = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines()]
    check("the file grew rather than being replaced", len(again) > len(rows),
          f"{len(rows)} -> {len(again)}")
    first = [r for r in again if r["week_start"] == "2022-05-02"]
    check("the same week now has two observations", len(first) == 2,
          str(len(first)))
    check("the earlier, lower count is still readable",
          sorted(r["issuers_buying"] for r in first) == [1, 2],
          str(sorted(r["issuers_buying"] for r in first)))
    check("no .tmp file is left behind",
          not list(Path(p).parent.glob("*.tmp")),
          str(list(Path(p).parent.glob("*.tmp"))))

print("[breadth] a week grazed by a late filing is NOT an observation of it")
#  Found by the first real run, not by reasoning: a buy dated 2025-12-01 arrived
#  in a scan covering three days of August 2026 -- a Form 4 nine months late. Its
#  week was written with a numerator of 1 and a denominator of 0, and anyone
#  computing a rate from that row divides by zero. The week was never observed;
#  one filing from it merely passed through the window.
with tempfile.TemporaryDirectory() as tmp:
    lo, hi = date(2026, 8, 24), date(2026, 8, 28)   # Mon-Fri, one partial week
    t = BreadthTally(min_value=25_000)
    inside = T(issuer="III", txn_date=date(2026, 8, 25), accession="in")
    stale = T(issuer="JJJ", txn_date=date(2025, 12, 3), accession="late")
    t.observe(date(2026, 8, 26), [inside, stale], [inside, stale])
    p2 = write_weeks(t, tmp, hi, window_days=3, scanner_sha="x",
                     start=lo, end=hi)
    by = {r["week_start"]: r
          for r in map(json.loads, p2.read_text(encoding="utf-8").splitlines())}
    check("the nine-month-late transaction still appears",
          "2025-12-01" in by, str(sorted(by)))
    check("...but its week is flagged as never observed",
          by["2025-12-01"]["week_in_window"] is False,
          str(by["2025-12-01"]["week_in_window"]))
    check("and it is exactly the row with a numerator and no denominator",
          by["2025-12-01"]["issuers_buying"] == 1
          and by["2025-12-01"]["issuers_filing"] == 0,
          str(by["2025-12-01"]))
    check("a week only PARTLY covered is not marked in-window either",
          by["2026-08-24"]["week_in_window"] is False,
          str(by["2026-08-24"]["week_in_window"]))
    check("the window bounds are on every row, so the flag can be rechecked",
          all(r["window_start"] == "2026-08-24" and r["window_end"] == "2026-08-28"
              for r in by.values()), str(by["2026-08-24"]))

with tempfile.TemporaryDirectory() as tmp:
    #  A week fully enclosed by the window IS an observation of it.
    lo, hi = date(2026, 8, 17), date(2026, 8, 31)
    t = BreadthTally(min_value=25_000)
    x = T(issuer="KKK", txn_date=date(2026, 8, 26), accession="k")
    t.observe(date(2026, 8, 26), [x], [x])
    p3 = write_weeks(t, tmp, hi, window_days=14, scanner_sha="x",
                     start=lo, end=hi)
    by = {r["week_start"]: r
          for r in map(json.loads, p3.read_text(encoding="utf-8").splitlines())}
    check("Mon-to-Sun entirely inside the window is in-window",
          by["2026-08-24"]["week_in_window"] is True,
          str(by["2026-08-24"]))

with tempfile.TemporaryDirectory() as tmp:
    #  Called without bounds -- as any caller that forgets them would -- the flag
    #  must say "not known to be in window", never assume it was.
    t = BreadthTally(min_value=25_000)
    x = T(issuer="LLL", txn_date=date(2026, 8, 26), accession="l")
    t.observe(date(2026, 8, 26), [x], [x])
    p4 = write_weeks(t, tmp, date(2026, 8, 31), window_days=14, scanner_sha="x")
    r = json.loads(p4.read_text(encoding="utf-8").splitlines()[0])
    check("with no bounds given the flag is False, not an assumption",
          r["week_in_window"] is False, str(r["week_in_window"]))
    check("...and the bounds are recorded as absent rather than invented",
          r["window_start"] is None and r["window_end"] is None,
          str([r["window_start"], r["window_end"]]))

print("[breadth] the module computes counts and nothing else")
import ast

src = (Path(__file__).resolve().parents[1] / "form4_scanner" / "breadth.py")
tree = ast.parse(src.read_text(encoding="utf-8"))
names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
banned = {n for n in names if any(k in n.lower() for k in
                                  ("zscore", "z_score", "deseason", "percent",
                                   "ratio", "normal"))}
check("no percentage, deseasonalising or z-score has crept into Phase 1",
      not banned, str(banned))

if __name__ == "__main__":
    sys.exit(report("ALL BREADTH TESTS PASSED"))
