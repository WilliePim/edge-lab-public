"""Tests for the dilution gate.

The case that matters most is ORDERING: the same 424B5 is a veto if it lands
after the insider buy and merely context if it landed before.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner.dilution import (BLOCKED, CAUTION, CLEAR, NOT_APPLICABLE,
                                    UNKNOWN, check_dilution,
                                    post_spin_share_growth, share_count_growth)


class FakeClient:
    """Serves a scripted filing history and share-count series."""

    def __init__(self, filings=(), shares=()):
        self._filings = list(filings)          # [(form, "YYYY-MM-DD")]
        self._shares = list(shares)            # [("YYYY-MM-DD", count)]

    def submissions(self, cik):
        return {
            "filings": {
                "recent": {
                    "form": [f for f, _ in self._filings],
                    "filingDate": [d for _, d in self._filings],
                },
                "files": [],
            }
        }

    def get_json(self, url):
        return None

    def company_concept(self, cik, taxonomy, tag):
        if not self._shares:
            return None
        return {
            "units": {
                "shares": [{"end": d, "val": v} for d, v in self._shares]
            }
        }


BUY = date(2026, 6, 15)
AS_OF = date(2026, 8, 10)
FLAT = [("2025-06-30", 40_000_000), ("2026-06-30", 40_400_000)]   # +1%

# --------------------------------------------------------------------------
print("\n[dilution] the trap: offering priced AFTER the insider buy")
c = FakeClient(
    filings=[("424B5", "2026-06-26"), ("S-3", "2025-11-01"), ("10-Q", "2026-05-05")],
    shares=FLAT,
)
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("424B5 11 days after the buy -> BLOCKED", r.verdict == BLOCKED, r.summary())
check("reason names the lag", "11d AFTER" in r.summary(), r.summary())
check("blocked property set", r.blocked)

print("\n[dilution] same filing, other side of the buy")
c = FakeClient(
    filings=[("424B5", "2026-05-02"), ("S-3", "2025-11-01")],
    shares=FLAT,
)
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("takedown before the buy is not a veto", r.verdict != BLOCKED, r.summary())
check("flagged as possible post-deal entry",
      any("BEFORE the buy" in x for x in r.reasons), r.summary())

print("\n[dilution] takedown after the buy but outside the trap window")
c = FakeClient(filings=[("424B5", "2026-11-01"), ("S-3", "2025-11-01")], shares=FLAT)
r = check_dilution(c, "123", BUY, as_of=date(2026, 12, 1))
check("139 days later -> CAUTION not BLOCKED", r.verdict == CAUTION, r.summary())

print("\n[dilution] live shelf, never drawn")
c = FakeClient(filings=[("S-3", "2025-11-01"), ("10-K", "2026-03-01")], shares=FLAT)
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("undrawn live shelf -> CAUTION", r.verdict == CAUTION, r.summary())
check("shelf recorded", r.live_shelf and r.live_shelf[0] == "S-3", str(r.live_shelf))

print("\n[dilution] stale shelf beyond Rule 415 three-year life")
c = FakeClient(filings=[("S-3", "2021-01-04"), ("10-K", "2026-03-01")], shares=FLAT)
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("expired shelf ignored", r.live_shelf is None, str(r.live_shelf))
check("clean issuer -> CLEAR", r.verdict == CLEAR, r.summary())

print("\n[dilution] realised share growth overrides everything")
c = FakeClient(
    filings=[("10-K", "2026-03-01")],
    shares=[("2025-06-30", 40_000_000), ("2026-06-30", 58_000_000)],   # +45%
)
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("+45% share count -> BLOCKED", r.verdict == BLOCKED, r.summary())
check("growth computed", r.shares_growth_pct == 45.0, str(r.shares_growth_pct))

c = FakeClient(
    filings=[("10-K", "2026-03-01")],
    shares=[("2025-06-30", 40_000_000), ("2026-06-30", 45_200_000)],   # +13%
)
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("+13% share count -> CAUTION", r.verdict == CAUTION, r.summary())

print("\n[dilution] conservative on missing data")
r = check_dilution(FakeClient(), "123", BUY, as_of=AS_OF)
check("no filing history -> UNKNOWN, never CLEAR", r.verdict == UNKNOWN, r.summary())

c = FakeClient(filings=[("10-K", "2026-03-01")], shares=[])
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("no share history -> UNKNOWN, never CLEAR", r.verdict == UNKNOWN, r.summary())

print("\n[dilution] share-count baseline hygiene")
c = FakeClient(filings=[], shares=[("2026-05-01", 40_000_000), ("2026-06-30", 44_000_000)])
g, n = share_count_growth(c, "123", AS_OF)
check("baseline only 60 days apart is rejected", g is None, str(g))
check("latest count still returned", n == 44_000_000, str(n))

c = FakeClient(filings=[], shares=[("2019-06-30", 10_000_000), ("2026-06-30", 40_000_000)])
g, _ = share_count_growth(c, "123", AS_OF)
check("7-year baseline rejected as stale", g is None, str(g))

print("\n[dilution] future-dated facts ignored")
c = FakeClient(filings=[], shares=[("2025-06-30", 40e6), ("2026-06-30", 41e6), ("2027-06-30", 90e6)])
g, n = share_count_growth(c, "123", AS_OF)
check("fact dated after as_of excluded", n == 41e6, str(n))
check("growth uses in-range facts only", g == 2.5, str(g))

# --------------------------------------------------------------------------
print("\n[dilution] spin-off younger than 12 months")

# A 2026 spin-off shape (synthetic counts): 10-12B in March, amended through May, two share counts
# after the distribution and nothing before it -- the entity did not exist.
SPIN = [("10-12B", "2026-03-20"), ("10-12B/A", "2026-05-06"), ("8-K", "2026-06-02")]
c = FakeClient(filings=SPIN,
               shares=[("2026-06-01", 28_000_000), ("2026-07-31", 28_084_000)])
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("young spin-off -> N/A, not UNKNOWN", r.verdict == NOT_APPLICABLE, r.summary())
check("N/A is not CLEAR", r.verdict != CLEAR, r.summary())
check("spin date anchored on the last 10-12B/A",
      r.spin_off_date == date(2026, 5, 6), str(r.spin_off_date))
check("baseline taken from first post-spin observation",
      r.shares_growth_pct == 0.3, str(r.shares_growth_pct))
check("window is the real span, not 365",
      r.growth_window_days == 60, str(r.growth_window_days))
check("reason refuses to call it a 12m figure",
      "not a 12m figure" in r.summary(), r.summary())
check("reason states the spin age", "spun off" in r.summary(), r.summary())

print("\n[dilution] the same issuer without the rule would have been UNKNOWN")
c = FakeClient(filings=[("8-K", "2026-06-02")],
               shares=[("2026-06-01", 28_000_000), ("2026-07-31", 28_084_000)])
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("no 10-12B -> still UNKNOWN", r.verdict == UNKNOWN, r.summary())

print("\n[dilution] spin-off older than 12 months uses the normal 12m test")
c = FakeClient(filings=[("10-12B", "2021-07-15"), ("10-12B/A", "2022-03-01")],
               shares=FLAT)
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("2022 spin is not 'recent'", r.spin_off_date is None, str(r.spin_off_date))
check("falls through to CLEAR on flat 12m count", r.verdict == CLEAR, r.summary())

print("\n[dilution] 10-12G is not a spin-off marker")
# HPS Real Assets Lending / Crestline shape: non-traded lending vehicles that
# register on 10-12G. Treating these as spin-offs would launder them to N/A.
c = FakeClient(filings=[("10-12G", "2025-11-10"), ("10-12G/A", "2026-01-05")],
               shares=[("2026-06-01", 10_000_000), ("2026-07-31", 10_100_000)])
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("10-12G stays UNKNOWN", r.verdict == UNKNOWN, r.summary())

print("\n[dilution] a spin-off that actually dilutes is still blocked")
c = FakeClient(filings=SPIN,
               shares=[("2026-06-01", 20_000_000), ("2026-07-31", 26_000_000)])
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("+30% post-spin -> BLOCKED", r.verdict == BLOCKED, r.summary())
check("block reason carries the real window",
      "since spin-off" in r.summary(), r.summary())

print("\n[dilution] spin-off with a live shelf keeps its CAUTION")
c = FakeClient(filings=SPIN + [("S-3", "2026-06-20")],
               shares=[("2026-06-01", 28_103_750), ("2026-07-31", 28_190_119)])
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("shelf detection applies to spin-offs -> CAUTION", r.verdict == CAUTION, r.summary())

print("\n[dilution] post-spin baseline hygiene")
c = FakeClient(filings=SPIN, shares=[("2026-07-20", 28_000_000), ("2026-07-31", 30_000_000)])
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("11-day post-spin window rejected", r.shares_growth_pct is None, str(r.shares_growth_pct))
check("unmeasurable spin-off still N/A", r.verdict == NOT_APPLICABLE, r.summary())

g, n, w = post_spin_share_growth(c, "123", AS_OF, date(2026, 5, 6))
check("helper returns None growth on a short window", g is None, str(g))
check("helper still returns the latest count", n == 30_000_000, str(n))
check("helper reports no window", w is None, str(w))

# Pre-spin observations belong to the parent and must not become the baseline.
c = FakeClient(filings=SPIN,
               shares=[("2026-01-31", 5_000_000), ("2026-06-01", 28_103_750),
                       ("2026-07-31", 28_190_119)])
g, n, w = post_spin_share_growth(c, "123", AS_OF, date(2026, 5, 6))
check("parent-era observation excluded from baseline", g == 0.3, str(g))
check("window measured from post-spin baseline", w == 60, str(w))


if __name__ == "__main__":
    sys.exit(report("ALL DILUTION TESTS PASSED"))
