import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner.classify import (NOVEL, OPPORTUNISTIC, ROUTINE, SPARSE,
                                    classify_insider)
from form4_scanner.cluster import group_by_issuer, holdings_increase_pct
from form4_scanner.market import MarketSnapshot
from form4_scanner.parse import open_market_buys, parse_ownership_xml
from form4_scanner.scan import parse_master_index
from form4_scanner.flags import evaluate_cluster

# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

CFO_BUY = """<?xml version="1.0"?>
<ownershipDocument>
  <schemaVersion>X0508</schemaVersion>
  <documentType>4</documentType>
  <periodOfReport>2026-08-04</periodOfReport>
  <aff10b5One>0</aff10b5One>
  <issuer>
    <issuerCik>0001234567</issuerCik>
    <issuerName>Midcap Widgets Inc</issuerName>
    <issuerTradingSymbol>mwid</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId>
      <rptOwnerCik>0001111111</rptOwnerCik>
      <rptOwnerName>Rossi Maria</rptOwnerName>
    </reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>0</isDirector>
      <isOfficer>1</isOfficer>
      <isTenPercentOwner>0</isTenPercentOwner>
      <officerTitle>Chief Financial Officer</officerTitle>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-08-04</value></transactionDate>
      <transactionCoding>
        <transactionFormType>4</transactionFormType>
        <transactionCode>P</transactionCode>
        <equitySwapInvolved>0</equitySwapInvolved>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>40000</value></transactionShares>
        <transactionPricePerShare><value>12.50</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts>
        <sharesOwnedFollowingTransaction><value>140000</value></sharesOwnedFollowingTransaction>
      </postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-08-04</value></transactionDate>
      <transactionCoding>
        <transactionFormType>4</transactionFormType>
        <transactionCode>F</transactionCode>
      </transactionCoding>
      <transactionAmounts>
        <transactionShares><value>900</value></transactionShares>
        <transactionPricePerShare><value>12.50</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <derivativeTable>
    <derivativeTransaction>
      <securityTitle><value>Stock Option</value></securityTitle>
      <transactionDate><value>2026-08-04</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>5000</value></transactionShares>
        <transactionPricePerShare><value>1.00</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
    </derivativeTransaction>
  </derivativeTable>
</ownershipDocument>
"""

# Two owners on one filing, and the plan disclosed only in a footnote.
JOINT_PLAN_BUY = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <periodOfReport>2026-08-05</periodOfReport>
  <issuer>
    <issuerCik>0001234567</issuerCik>
    <issuerName>Midcap Widgets Inc</issuerName>
    <issuerTradingSymbol>MWID</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>0002222222</rptOwnerCik><rptOwnerName>Bianchi Luca</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>1</isDirector><isOfficer>0</isOfficer><isTenPercentOwner>0</isTenPercentOwner>
    </reportingOwnerRelationship>
  </reportingOwner>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>0003333333</rptOwnerCik><rptOwnerName>Bianchi Family Trust</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>0</isDirector><isOfficer>0</isOfficer><isTenPercentOwner>1</isTenPercentOwner>
    </reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-08-05</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>10000</value></transactionShares>
        <transactionPricePerShare><value>12.10</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>60000</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
  <footnotes>
    <footnote id="F1">Purchase made pursuant to a Rule 10b5-1 trading plan adopted March 3, 2026.</footnote>
  </footnotes>
</ownershipDocument>
"""

# No <value> wrappers -- some filer agents emit this shape.
BARE_DIRECTOR_BUY = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <issuer>
    <issuerCik>1234567</issuerCik>
    <issuerName>Midcap Widgets Inc</issuerName>
    <issuerTradingSymbol>MWID</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>4444444</rptOwnerCik><rptOwnerName>Conti Anna</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>1</isDirector><isOfficer>0</isOfficer><isTenPercentOwner>0</isTenPercentOwner></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle>Common Stock</securityTitle>
      <transactionDate>2026-08-11</transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares>8000</transactionShares>
        <transactionPricePerShare>11.80</transactionPricePerShare>
        <transactionAcquiredDisposedCode>A</transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction>9000</sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership>D</directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""

MASTER_IDX = """Description:           Master Index of EDGAR Dissemination Feed
Last Data Received:    August 07, 2026
--------------------------------------------------------------------------------
CIK|Company Name|Form Type|Date Filed|Filename
1234567|Midcap Widgets Inc|4|2026-08-07|edgar/data/1234567/0001234567-26-000012.txt
1111111|Rossi Maria|4|2026-08-07|edgar/data/1234567/0001234567-26-000012.txt
9999999|Bigco Inc|10-Q|2026-08-07|edgar/data/9999999/0000999999-26-000004.txt
8888888|Other Corp, Inc.|4|2026-08-07|edgar/data/8888888/0000888888-26-000001.txt
"""


# --------------------------------------------------------------------------
print("\n[parse] transaction extraction")
txns = parse_ownership_xml(CFO_BUY, accession="0001234567-26-000012", filed_at=date(2026, 8, 6))
check("extracts all rows incl. derivative", len(txns) == 3, f"got {len(txns)}")
buys = open_market_buys(txns, min_value=25_000)
check("filters to the single code-P non-derivative buy", len(buys) == 1, f"got {len(buys)}")
b = buys[0]
check("value = shares * price", b.value == 500_000.0, str(b.value))
check("ticker uppercased", b.ticker == "MWID", b.ticker)
check("CFO title mapped to role", b.role == "CFO", b.role)
check("tax-withholding row (F) excluded", all(t.code != "F" for t in buys))
check("derivative code-P row excluded", all(not t.is_derivative for t in buys))

print("\n[parse] 10b5-1 detection and joint filings")
joint = parse_ownership_xml(JOINT_PLAN_BUY, accession="acc2", filed_at=date(2026, 8, 6))
check("one row per reporting owner", len(joint) == 2, f"got {len(joint)}")
check("plan detected from footnote prose", all(t.plan_10b5_1 for t in joint))
check("plan buys dropped by filter", len(open_market_buys(joint)) == 0)
check("10% owner role separated",
      {t.role for t in joint} == {"Director", "10% Owner"}, str({t.role for t in joint}))

print("\n[parse] filings without <value> wrappers")
bare = open_market_buys(parse_ownership_xml(BARE_DIRECTOR_BUY, accession="acc3"))
check("bare-element filing parses", len(bare) == 1, f"got {len(bare)}")
check("bare value correct", bare and bare[0].value == 94_400.0, str(bare[0].value if bare else None))
check("bare date correct", bare and bare[0].txn_date == date(2026, 8, 11))

print("\n[index] master.idx parsing")
rows = parse_master_index(MASTER_IDX)
check("keeps Form 4 only, deduped by accession", len(rows) == 2, f"got {len(rows)}")
check("accession extracted", rows[0]["accession"] == "0001234567-26-000012", rows[0]["accession"])
check("pipe-safe on names containing commas",
      any(r["company"] == "Other Corp, Inc." for r in rows))

# --------------------------------------------------------------------------
print("\n[classify] routine vs opportunistic")
as_of = date(2026, 8, 4)

routine_hist = [date(2024, 3, 11), date(2025, 3, 17), date(2026, 3, 14), date(2025, 9, 2)]
p = classify_insider("1", "Routine Ray", routine_hist, as_of)
check("same month in each prior year -> routine", p.label == ROUTINE, f"{p.label}: {p.reason}")

oppo_hist = [date(2024, 6, 15), date(2025, 4, 22), date(2026, 2, 10)]
p = classify_insider("2", "Oppo Olga", oppo_hist, as_of)
check("active every year, no recurring month -> opportunistic",
      p.label == OPPORTUNISTIC, f"{p.label}: {p.reason}")

p = classify_insider("3", "Novel Nick", [], as_of)
check("no prior purchases -> novel", p.label == NOVEL, p.label)

p = classify_insider("4", "Sparse Sam", [date(2024, 6, 20), date(2025, 6, 9)], as_of)
check("gaps in the record -> sparse", p.label == SPARSE, f"{p.label}: {p.reason}")

p = classify_insider("5", "Stale Steve", [date(2019, 3, 1), date(2020, 3, 1)], as_of)
check("purchases older than lookback ignored -> novel", p.label == NOVEL, p.label)

sells_only = classify_insider("6", "Seller Sue", [], as_of)
check("history built from purchases only", sells_only.label == NOVEL)

# --------------------------------------------------------------------------
print("\n[cluster] windowing and holdings math")
tight = buys + bare + open_market_buys(
    parse_ownership_xml(BARE_DIRECTOR_BUY.replace("4444444", "5555555")
                        .replace("2026-08-11", "2026-08-12"), accession="acc4")
)
clusters = group_by_issuer(tight)
check("all three buys land on one issuer", len(clusters) == 1, f"got {len(clusters)}")
c = clusters[0]
check("counts 3 distinct buyers", c.distinct_buyers == 3, str(c.distinct_buyers))
check("3 buyers inside 30d window", c.max_window_buyers(30) == 3, str(c.max_window_buyers(30)))
check("2d window excludes the buyer 7 days away", c.max_window_buyers(2) == 2, str(c.max_window_buyers(2)))
check("total value aggregated", c.total_value == 500_000 + 94_400 + 94_400, str(c.total_value))

check("holdings increase pct", holdings_increase_pct(b) == 40.0, str(holdings_increase_pct(b)))
check("new-from-zero -> inf", holdings_increase_pct(bare[0]) == 800.0,
      str(holdings_increase_pct(bare[0])))

# --------------------------------------------------------------------------
print("\n[flags] the rubric is gone; what is left is what it recorded")
snap = MarketSnapshot(ticker="MWID", market_cap=800e6, price=12.0, high_52w=20.0,
                      low_52w=10.5, analyst_count=2, total_cash=200e6,
                      total_debt=50e6, free_cash_flow=10e6, ok=True)
snap.drawdown_pct = 40.0

labels = {"1111111": OPPORTUNISTIC, "4444444": NOVEL, "5555555": SPARSE}
card = evaluate_cluster(c, labels, snap)
print("     score_v3:", card.v3["score"], "->", card.v3)

#  Three inputs, not seven. size, drawdown, coverage and specialist_overlap
#  went with the criteria that read them -- measured on the corpus and flat,
#  see reports/size_component_test.md and reports/rubric_discrimination.md.
check("evaluate_cluster records exactly three inputs",
      sorted(card.inputs) == ["buyer_quality", "cluster", "role"],
      str(sorted(card.inputs)))
check("there are no points anywhere on the card",
      not hasattr(card, "components"),
      str([a for a in dir(card) if not a.startswith("_")]))

#  The case worth pinning down: THREE distinct buyers inside the window, and
#  the cluster criterion is still False. v3 counts opportunistic buyer GROUPS,
#  not heads -- one opportunistic buyer next to a novel and a sparse one is not
#  the thing Cohen-Malloy-Pomorski measured a return on.
check("3 buyers in the window",
      card.inputs["cluster"]["buyers_in_window"] == 3,
      str(card.inputs["cluster"]["buyers_in_window"]))
check("...but only one is opportunistic, so cluster stays False",
      card.v3["cluster"] is False, str(card.v3["cluster"]))
check("a bare director is on the filing", card.v3["director"] is True)
check("no 10% owner among the buyers", card.v3["no_10pct"] is True)
#  The index is not shipped with the repository (tools/spinoffs.py builds it):
#  without it terreno is None -- not measured -- and never False.
from form4_scanner import flags as _flags
if _flags.SPINOFF_INDEX.exists():
    check("terreno is answered, not unknown, now that the index exists",
          card.v3["terreno"] is False, str(card.v3["terreno"]))
else:
    check("without the index terreno is None, not False",
          card.v3["terreno"] is None, str(card.v3["terreno"]))
check("score_v3 is the count of the Trues, weight 1 each",
      card.v3["score"] == 2, str(card.v3["score"]))
check("survivability read as net cash",
      card.context["survivability"] == "net cash",
      str(card.context["survivability"]))
#  Drawdown was removed from the scoring in v2 and from the card in v3. It is
#  still read off the snapshot, which is what "measured, not scored" means.
check("the drawdown depth is still measured", snap.drawdown_pct == 40.0,
      str(snap.drawdown_pct))

#  Fail-closed sull'archivio: un CIK che la classificazione non ha visto (storia
#  non scaricata, giro interrotto) resta None. Prima diventava SPARSE, che è una
#  classificazione MISURATA: l'archivio è append-only, quindi la bugia sarebbe
#  rimasta per sempre.
senza_storia = evaluate_cluster(c, {"1111111": OPPORTUNISTIC}, snap)
per_owner = senza_storia.inputs["buyer_quality"]["labels_by_owner"]
check("un CIK non classificato resta None nell'archivio",
      per_owner.get("4444444", "assente") is None, str(per_owner))
check("...e quello classificato resta quello che è",
      per_owner["1111111"] == OPPORTUNISTIC, str(per_owner))

routine_card = evaluate_cluster(c, {k: ROUTINE for k in labels}, snap)
check("all-routine buyers flagged",
      any("routine" in f for f in routine_card.flags), str(routine_card.flags))
#  The flag is now the whole of it. Routine buyers used to cost points; there
#  are no points, so what remains is that the reader is told.
check("...and routine buyers form no opportunistic group",
      routine_card.v3["cluster"] is False, str(routine_card.v3))

burn = MarketSnapshot(ticker="X", total_cash=10e6, total_debt=90e6, free_cash_flow=-30e6)
check("levered + burning triggers veto flag", burn.survivability_flag == "LEVERED + BURNING")

# --------------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(report("ALL TESTS PASSED"))
