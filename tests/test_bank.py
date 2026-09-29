"""Tests for the depository asset-quality gate.

A bank's insider buy looks identical to any other on a Form 4, and what kills a
bank is the loan book, which none of the twelve points can see. So a depository
either clears an NPA check or is capped below the level that would put it at the
top of the report.

The case that matters most is the one the live scan produced: roughly half of
small banks do not tag nonaccruals at all, and one of those was the highest
scoring name in the run. The gate must cap that name rather than guess at its
asset quality -- and must not cap a bank whose numbers are actually there.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner.bank import (ELEVATED, OK, UNVERIFIED, check_bank,
                                is_depository)


class FakeClient:
    """Serves a SIC code and scripted us-gaap concepts."""

    def __init__(self, sic="6022", concepts=None):
        self._sic = sic
        self._concepts = concepts or {}

    def submissions(self, cik):
        return {"sic": self._sic, "sicDescription": "test"}

    def company_concept(self, cik, taxonomy, tag):
        rows = self._concepts.get(tag)
        if rows is None:
            return None
        return {"units": {"USD": [{"end": d, "val": v} for d, v in rows]}}


NONACCRUAL = "FinancingReceivableRecordedInvestmentNonaccrualStatus"
GROSS = "FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLoss"
AS_OF = date(2026, 8, 22)


def bank(nonaccrual=None, gross=None, sic="6022"):
    c = {}
    if nonaccrual is not None:
        c[NONACCRUAL] = nonaccrual
    if gross is not None:
        c[GROSS] = gross
    return check_bank(FakeClient(sic, c), "123", as_of=AS_OF)


# --------------------------------------------------------------------------
print("[bank] who counts as a depository")
for sic, expected in (("6020", True), ("6021", True), ("6022", True),
                      ("6035", True), ("6036", True), ("6712", True)):
    ok, got = is_depository(FakeClient(sic), "1")
    check(f"SIC {sic} is a depository", ok is expected, f"{sic} -> {ok}")

for sic, why in (("6331", "insurance"), ("6798", "REIT"), ("2834", "pharma"),
                 ("6500", "real estate"), ("", "missing")):
    ok, _ = is_depository(FakeClient(sic), "1")
    check(f"SIC {sic or '(empty)'} is NOT a depository ({why})", ok is False,
          f"{sic} -> {ok}")

print("[bank] a non-depository passes through untouched")
r = check_bank(FakeClient("2834", {}), "123", as_of=AS_OF)
check("non-bank is not flagged as a depository", r.is_depository is False)
check("non-bank status is OK", r.status == OK, r.status)
check("non-bank is never capped", r.capped is False)
check("non-bank has no NPA ratio", r.npa_pct is None, str(r.npa_pct))

print("[bank] a bank with clean, current numbers clears")
r = bank(nonaccrual=[("2026-06-30", 6_200_000.0)],
         gross=[("2026-06-30", 1_000_000_000.0)])
check("status OK", r.status == OK, r.summary())
check("NPA ratio computed", r.npa_pct == 0.62, str(r.npa_pct))
check("a clearing bank is NOT capped", r.capped is False, r.summary())
check("the as-of date is recorded", r.as_of == date(2026, 6, 30), str(r.as_of))
check("the reason quotes the ratio", "0.62%" in r.summary(), r.summary())

print("[bank] elevated nonaccruals cap the score")
r = bank(nonaccrual=[("2026-06-30", 35_000_000.0)],
         gross=[("2026-06-30", 1_000_000_000.0)])
check("3.5% NPA is ELEVATED", r.status == ELEVATED, r.summary())
check("elevated caps", r.capped is True)
check("the reason says the loan book is the story",
      "loan book is the story" in r.summary(), r.summary())

r = bank(nonaccrual=[("2026-06-30", 20_000_000.0)],
         gross=[("2026-06-30", 1_000_000_000.0)])
check("exactly 2.00% is NOT elevated -- the band is above the line",
      r.status == OK, r.summary())
r = bank(nonaccrual=[("2026-06-30", 20_100_000.0)],
         gross=[("2026-06-30", 1_000_000_000.0)])
check("2.01% is elevated", r.status == ELEVATED, r.summary())

print("[bank] the real gap: a bank that does not tag nonaccruals")
r = bank(nonaccrual=None, gross=[("2026-06-30", 1_000_000_000.0)])
check("no nonaccrual tag -> UNVERIFIED", r.status == UNVERIFIED, r.summary())
check("unverified caps -- it does not guess", r.capped is True)
check("no ratio is invented", r.npa_pct is None, str(r.npa_pct))
check("the reason names what is missing", "nonaccruals" in r.summary(),
      r.summary())
check("...and says where to look by hand", "10-K" in r.summary(), r.summary())

r = bank(nonaccrual=[("2026-06-30", 6_200_000.0)], gross=None)
check("no loan balance -> UNVERIFIED", r.status == UNVERIFIED, r.summary())
check("the reason names the other side", "gross loans" in r.summary(),
      r.summary())

print("[bank] stale nonaccruals do not pair with a current loan book")
#  Coastal Financial in the live scan: the tag exists, but its last observation
#  is four years old. Dividing that by today's loan balance would produce a
#  confident, meaningless ratio.
r = bank(nonaccrual=[("2022-06-30", 6_200_000.0)],
         gross=[("2026-06-30", 1_000_000_000.0)])
check("a four-year gap refuses the pairing", r.status == UNVERIFIED, r.summary())
check("the reason states both dates and the distance",
      "2022-06-30" in r.summary() and "2026-06-30" in r.summary()
      and "d apart" in r.summary(), r.summary())
check("no ratio is produced from mismatched dates", r.npa_pct is None)

r = bank(nonaccrual=[("2026-05-31", 6_200_000.0)],
         gross=[("2026-06-30", 1_000_000_000.0)])
check("a 30-day gap is close enough to be the same balance sheet",
      r.status == OK, r.summary())

print("[bank] degenerate inputs are refused, not divided by")
r = bank(nonaccrual=[("2026-06-30", 6_200_000.0)],
         gross=[("2026-06-30", 0.0)])
check("a zero loan book refuses rather than dividing by zero",
      r.status == UNVERIFIED, r.summary())
check("the reason says so", "zero or negative" in r.summary(), r.summary())

r = bank(nonaccrual=[("2026-06-30", 6_200_000.0)],
         gross=[("2026-06-30", -5.0)])
check("a negative loan book is refused too", r.status == UNVERIFIED, r.summary())

print("[bank] only observations at or before as_of are used")
r = bank(nonaccrual=[("2026-06-30", 6_200_000.0), ("2027-06-30", 99_000_000.0)],
         gross=[("2026-06-30", 1_000_000_000.0),
                ("2027-06-30", 1_000_000_000.0)])
check("a future-dated fact is ignored", r.npa_pct == 0.62, str(r.npa_pct))
check("...and the as-of stays the in-range date", r.as_of == date(2026, 6, 30),
      str(r.as_of))

print("[bank] the newest in-range observation wins")
r = bank(nonaccrual=[("2025-06-30", 30_000_000.0),
                     ("2026-06-30", 6_200_000.0)],
         gross=[("2025-06-30", 1_000_000_000.0),
                ("2026-06-30", 1_000_000_000.0)])
check("last year's worse ratio does not win", r.npa_pct == 0.62, str(r.npa_pct))

#  Il tetto al punteggio (DEPOSITORY_SCORE_CAP) e la sua aritmetica vivevano qui,
#  su una Card finta con `.score`: erano il rispecchiamento di un blocco di score.py.
#  Con il rubric e' sparito il punteggio da limitare, e quel che resta e' il flag.
print("[bank] alternate spellings of the same disclosure")
alt = check_bank(FakeClient("6022", {
    "FinancingReceivableExcludingAccruedInterestNonaccrual":
        [("2026-06-30", 7_500_000.0)],
    GROSS: [("2026-06-30", 1_000_000_000.0)],
}), "123", as_of=AS_OF)
check("the post-CECL nonaccrual spelling resolves", alt.status == OK,
      alt.summary())
check("...to the right ratio", alt.npa_pct == 0.75, str(alt.npa_pct))

alt2 = check_bank(FakeClient("6022", {
    NONACCRUAL: [("2026-06-30", 6_200_000.0)],
    "LoansAndLeasesReceivableNetReportedAmount":
        [("2026-06-30", 1_000_000_000.0)],
}), "123", as_of=AS_OF)
check("the alternate loan-balance spelling resolves", alt2.status == OK,
      alt2.summary())

print("[bank] a client that returns nothing does not crash the gate")
r = check_bank(FakeClient("6022", {}), "123", as_of=AS_OF)
check("no concepts at all -> UNVERIFIED, capped", r.status == UNVERIFIED
      and r.capped, r.summary())


class DeadClient:
    def submissions(self, cik):
        return None

    def company_concept(self, cik, taxonomy, tag):
        return None


r = check_bank(DeadClient(), "123", as_of=AS_OF)
check("submissions returning None is survivable", r.is_depository is False,
      str(r.is_depository))
check("...and produces no cap, because it is not known to be a bank",
      r.capped is False, r.summary())

if __name__ == "__main__":
    sys.exit(report("ALL BANK TESTS PASSED"))
