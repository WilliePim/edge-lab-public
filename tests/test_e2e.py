"""End-to-end pipeline test against a fake EDGAR, verifying scan.py wiring."""
import os
import sys
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import form4_scanner.scan as scan
from form4_scanner.market import MarketSnapshot
from test_scanner import CFO_BUY, BARE_DIRECTOR_BUY, MASTER_IDX

DILUTION_FILINGS = []      # mutated per-scenario below

class FakeClient:
    def __init__(self, *a, **k): pass
    def company_concept(self, cik, taxonomy, tag):
        return {"units": {"shares": [{"end": "2025-06-30", "val": 40e6},
                                     {"end": "2026-06-30", "val": 40.4e6}]}}
    def daily_master_index(self, day):
        return MASTER_IDX if day in (date(2026, 8, 7), date(2026, 8, 19)) else None
    def ownership_xml(self, cik, accession):
        return CFO_BUY if accession.endswith("000012") else BARE_DIRECTOR_BUY
    def submissions(self, cik):
        return {"filings": {"recent": {
            "accessionNumber": [], 
            "form": [f for f, _ in DILUTION_FILINGS],
            "filingDate": [d for _, d in DILUTION_FILINGS]}, "files": []}}
    def get_json(self, url): return None

class FakeMarket:
    def snapshot(self, ticker):
        s = MarketSnapshot(ticker=ticker, market_cap=800e6, price=12.0, high_52w=20.0,
                           analyst_count=2, total_cash=200e6, total_debt=50e6, ok=True)
        s.drawdown_pct = 40.0
        return s

scan.EdgarClient = FakeClient
scan.get_provider = lambda kind: FakeMarket()

cards = scan.run_scan(
    user_agent="Test test@example.com",
    lookback_days=3, end=date(2026, 8, 8), min_value=25_000,
)
assert cards, "pipeline returned nothing"
c = cards[0]
print(f"\n  top result: {c.ticker} score_v3 {c.v3.get('score')}  "
      f"${c.context['total_value']:,.0f}")
for f in c.flags: print("    !", f)
assert c.ticker == "MWID", c.ticker
#  The component assertions went with the components. What is left is what v3
#  actually decides: the gate, and the ordering.
assert not c.blocked, "clean name should not be vetoed"
print(f"    dilution: {c.context['dilution']}")
assert c.context["dilution"] in ("CLEAR", "CAUTION", "UNKNOWN")

# --- now the trap: same buys, but a 424B5 lands days after ---------------
#  Il veto e' spento per default (dilution.veto_attivo): il comportamento storico si prova accendendolo.
DILUTION_FILINGS[:] = [("424B5", "2026-08-14"), ("S-3", "2025-11-01")]
os.environ["EDGE_LAB_DILUTION_VETO"] = "1"
trapped = scan.run_scan(
    user_agent="Test test@example.com",
    lookback_days=3, end=date(2026, 8, 20), min_value=25_000, keep_blocked=True,
)
t = trapped[0]
print(f"\n  with 424B5: score_v3 {t.v3.get('score')} "
      f"dilution={t.context['dilution']}")
assert t.context["dilution"] == "BLOCKED", t.context["dilution"]
assert t.blocked, "a vetoed name must stay blocked whatever score_v3 says"
assert any("DILUTION VETO" in f for f in t.flags), t.flags

# --- and the veto must prune it from the pipeline entirely --------------
pruned = scan.run_scan(
    user_agent="Test test@example.com",
    lookback_days=3, end=date(2026, 8, 20), min_value=25_000, keep_blocked=False,
)
assert not pruned, f"vetoed name should be dropped before scoring, got {len(pruned)}"
print("  veto prunes before the expensive history walk: OK")

# --- default: veto spento. Il predicato si calcola e si mostra, nessun nome e' fermato --
del os.environ["EDGE_LAB_DILUTION_VETO"]
kept = scan.run_scan(
    user_agent="Test test@example.com",
    lookback_days=3, end=date(2026, 8, 20), min_value=25_000, keep_blocked=False,
)
assert len(kept) == 1, f"veto off: the name must stay in the pipeline, got {len(kept)}"
k = kept[0]
assert k.context["dilution"] == "BLOCKED", k.context["dilution"]
assert not k.blocked, "veto off: the predicate is information, the card is not blocked"
assert any("veto off" in f for f in k.flags) and not any("DILUTION VETO" in f for f in k.flags), k.flags
print("  veto off by default: predicate shown, name kept: OK")

print("\n  E2E PIPELINE OK")
