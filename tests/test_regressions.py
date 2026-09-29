"""Regressions from the first live run (2026-08-07, 572 filings).

Three defects that only real data exposed. Every fixture below is modelled on
the filing that produced it, with the real numbers, so a future refactor that
reintroduces the bug fails here with a recognisable figure.

  1. Joint filings multiplied every aggregate by the number of co-filers.
     Accession 0001193125-26-340528: four affiliated Forbion vehicles, two
     transaction rows, $64.8M of buying reported as $259.2M.
  2. An offering priced days BEFORE the buy read as favourable. On BRVE and
     ATTO the 424B4 landed one day earlier and the insiders were buying the
     IPO allocation itself.
  3. NOVEL was awarded to CIKs registered days before the trade.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner.classify import (NOVEL, UNSEASONED, classify_insider,
                                    first_filing_date)
from form4_scanner.cluster import group_by_issuer
from form4_scanner.dilution import BLOCKED, CAUTION, check_dilution
from form4_scanner.market import MarketSnapshot
from form4_scanner.parse import open_market_buys, parse_ownership_xml
from form4_scanner.flags import evaluate_cluster


def _owner(cik, name):
    return f"""
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>{cik}</rptOwnerCik><rptOwnerName>{name}</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship>
      <isDirector>0</isDirector><isOfficer>0</isOfficer><isTenPercentOwner>1</isTenPercentOwner>
    </reportingOwnerRelationship>
  </reportingOwner>"""


def _row(shares, price, after):
    return f"""
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-08-07</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>{shares}</value></transactionShares>
        <transactionPricePerShare><value>{price}</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>{after}</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>I</value></directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>"""


# Four affiliated vehicles signing one filing for two trades -- the Forbion shape.
FUND_JOINT = f"""<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <issuer>
    <issuerCik>2131524</issuerCik>
    <issuerName>Braveheart Bio, Inc.</issuerName>
    <issuerTradingSymbol>BRVE</issuerTradingSymbol>
  </issuer>{_owner("2000001", "Forbion Growth III Management B.V.")}{_owner("2000002", "Forbion Growth Opportunities Fund III")}{_owner("2000003", "Forbion Ventures Fund VII Cooperatief")}{_owner("2000004", "Forbion Ventures VII Management B.V.")}
  <nonDerivativeTable>{_row(1920000, "18.00", 1920000)}{_row(1680000, "18.00", 1680000)}</nonDerivativeTable>
</ownershipDocument>
"""

# A single director on his own filing, same issuer, same offering price.
DIRECTOR_SOLO = """<?xml version="1.0"?>
<ownershipDocument>
  <documentType>4</documentType>
  <issuer>
    <issuerCik>2131524</issuerCik>
    <issuerName>Braveheart Bio, Inc.</issuerName>
    <issuerTradingSymbol>BRVE</issuerTradingSymbol>
  </issuer>
  <reportingOwner>
    <reportingOwnerId><rptOwnerCik>1500001</rptOwnerCik><rptOwnerName>Lubner David Charles</rptOwnerName></reportingOwnerId>
    <reportingOwnerRelationship><isDirector>1</isDirector><isOfficer>0</isOfficer><isTenPercentOwner>0</isTenPercentOwner></reportingOwnerRelationship>
  </reportingOwner>
  <nonDerivativeTable>
    <nonDerivativeTransaction>
      <securityTitle><value>Common Stock</value></securityTitle>
      <transactionDate><value>2026-08-07</value></transactionDate>
      <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts>
        <transactionShares><value>55555</value></transactionShares>
        <transactionPricePerShare><value>18.00</value></transactionPricePerShare>
        <transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode>
      </transactionAmounts>
      <postTransactionAmounts><sharesOwnedFollowingTransaction><value>55555</value></sharesOwnedFollowingTransaction></postTransactionAmounts>
      <ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>
    </nonDerivativeTransaction>
  </nonDerivativeTable>
</ownershipDocument>
"""

# --------------------------------------------------------------------------
print("\n[joint filings] co-filers must not multiply the totals")
joint = open_market_buys(
    parse_ownership_xml(FUND_JOINT, accession="0001193125-26-340528"), min_value=500_000
)
check("one Transaction per row x owner is preserved", len(joint) == 8, f"got {len(joint)}")

cluster = group_by_issuer(joint)[0]
check("economic trades deduped to the two real rows",
      len(cluster.economic_txns) == 2, str(len(cluster.economic_txns)))
check("value is $64.8M, not the $259.2M the naive sum gives",
      cluster.total_value == 64_800_000.0, f"${cluster.total_value:,.0f}")
check("four affiliated vehicles count as one buyer",
      cluster.distinct_buyers == 1, str(cluster.distinct_buyers))
check("and cannot manufacture a cluster on their own",
      cluster.max_window_buyers(30) == 1, str(cluster.max_window_buyers(30)))

print("\n[joint filings] independent filers still count separately")
mixed = joint + open_market_buys(
    parse_ownership_xml(DIRECTOR_SOLO, accession="0001470831-26-000796"), min_value=500_000
)
mc = group_by_issuer(mixed)[0]
check("fund group + solo director = 2 buyers", mc.distinct_buyers == 2, str(mc.distinct_buyers))
check("totals add without double counting",
      mc.total_value == 64_800_000.0 + 55_555 * 18.0, f"${mc.total_value:,.0f}")

print("\n[offering price] identical fills are an allocation, not a market")
check("uniform price surfaced", mc.uniform_price == 18.0, str(mc.uniform_price))
card = evaluate_cluster(mc, {}, MarketSnapshot(ticker="BRVE"))
#  The flag used to say "offering price, not open market", which is the
#  conclusion and not the field. It now carries the fields the conclusion was
#  drawn from -- CLAUDE.md, confine fra scanner e giudizio -- so the assertion
#  moves to the fact: the code, and that every fill was the same price.
check("flagged on the scorecard, as fields",
      any("identical" in f and "code P" in f for f in card.flags),
      str(card.flags))

varied = open_market_buys(
    parse_ownership_xml(DIRECTOR_SOLO.replace("18.00", "17.42").replace("1500001", "1500002"),
                        accession="acc-varied"),
    min_value=500_000,
)
vc = group_by_issuer(mixed + varied)[0]
check("different prints -> no flag", vc.uniform_price is None, str(vc.uniform_price))


# --------------------------------------------------------------------------
class FakeClient:
    def __init__(self, filings=(), shares=(), stamps=None, shard_from=None):
        self._filings = list(filings)
        self._shares = list(shares)
        self._stamps = stamps
        self._shard_from = shard_from

    def submissions(self, cik):
        if self._stamps is None:
            recent = {"form": [f for f, _ in self._filings],
                      "filingDate": [d for _, d in self._filings]}
        else:
            recent = {"form": ["4"] * len(self._stamps), "filingDate": list(self._stamps)}
        files = [{"name": "old.json", "filingFrom": self._shard_from}] if self._shard_from else []
        return {"filings": {"recent": recent, "files": files}}

    def get_json(self, url):
        return None

    def company_concept(self, cik, taxonomy, tag):
        if not self._shares:
            return None
        return {"units": {"shares": [{"end": d, "val": v} for d, v in self._shares]}}


BUY = date(2026, 8, 7)
AS_OF = date(2026, 8, 10)
FLAT = [("2025-06-30", 40_000_000), ("2026-06-30", 40_400_000)]

print("\n[dilution] the mirror trap: deal priced days BEFORE the buy")
c = FakeClient(filings=[("424B4", "2026-08-06"), ("S-1MEF", "2026-08-05"),
                        ("S-1/A", "2026-07-20"), ("8-K", "2026-08-07")], shares=FLAT)
r = check_dilution(c, "2131524", BUY, as_of=AS_OF)
check("424B4 one day before the buy -> BLOCKED", r.verdict == BLOCKED, r.summary())
check("reason names it as participation",
      "participation in the offering" in r.summary(), r.summary())
check("newly-public issuer noted",
      any("newly public" in x for x in r.reasons), r.summary())

print("\n[dilution] the same form, long enough before, is still favourable")
c = FakeClient(filings=[("424B5", "2026-05-02"), ("S-3", "2025-11-01")], shares=FLAT)
r = check_dilution(c, "123", BUY, as_of=AS_OF)
check("97 days before -> not blocked", r.verdict != BLOCKED, r.summary())
check("still read as stepping in post-deal",
      any("BEFORE the buy" in x and "stepping in" in x for x in r.reasons), r.summary())

print("\n[dilution] boundary of the participation window")
c = FakeClient(filings=[("424B5", "2026-08-02")], shares=FLAT)     # 5 days
check("5 days before -> BLOCKED",
      check_dilution(c, "123", BUY, as_of=AS_OF).verdict == BLOCKED)
c = FakeClient(filings=[("424B5", "2026-08-01")], shares=FLAT)     # 6 days
check("6 days before -> not blocked",
      check_dilution(c, "123", BUY, as_of=AS_OF).verdict != BLOCKED)

# --------------------------------------------------------------------------
print("\n[classify] an empty history the CIK was too new to have")
new_cik = FakeClient(stamps=["2026-08-05", "2026-08-07"])
first = first_filing_date(new_cik, "2000003")
check("first filing found", first == date(2026, 8, 5), str(first))
p = classify_insider("2000003", "Forbion Ventures Fund VII", [], BUY, cik_first_filing=first)
check("CIK registered 2 days earlier -> unseasoned, not novel",
      p.label == UNSEASONED, f"{p.label}: {p.reason}")

old_cik = FakeClient(stamps=["2026-07-01"], shard_from="2008-02-13")
first = first_filing_date(old_cik, "1500001")
check("shard filingFrom read without opening the shard",
      first == date(2008, 2, 13), str(first))
p = classify_insider("1500001", "Redmile Group", [], BUY, cik_first_filing=first)
check("long-established CIK with no buys stays novel", p.label == NOVEL, p.label)

p = classify_insider("9", "Unknowable", [], BUY, cik_first_filing=None)
check("unknown first-filing date does not invent a downgrade", p.label == NOVEL, p.label)

print("\n[score] unseasoned buyers earn nothing and say so")
card = evaluate_cluster(cluster, {t.owner_cik: UNSEASONED for t in cluster.txns},
                        MarketSnapshot(ticker="BRVE"))
#  It used to be worth zero points. With no points, the property that has to
#  survive is that the label is written down as unseasoned and not silently
#  read as sparse -- "no history" and "a thin history" are different facts.
check("buyer_quality recorded as unseasoned, not sparse",
      card.inputs["buyer_quality"]["labels_present"] == [UNSEASONED],
      str(card.inputs["buyer_quality"]["labels_present"]))
check("flag explains why, and does not claim they are routine",
      any("too new" in f for f in card.flags) and not any("routine" in f for f in card.flags),
      str(card.flags))

if __name__ == "__main__":
    sys.exit(report("ALL REGRESSION TESTS PASSED"))
