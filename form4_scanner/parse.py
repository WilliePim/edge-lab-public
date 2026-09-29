"""Parse SEC ownership XML (Form 3/4/5) into flat Transaction records.

Of the transaction codes only `P` is an open-market purchase. The rest are kept
apart and dropped by `open_market_buys`: `S` sale, `A` grant or award, `M` option
exercise, `F` shares withheld for tax, `G` gift, `C` conversion, `D` disposition
to the issuer, `X` in-the-money exercise.

Handles the things that break naive parsers:
  - multiple <reportingOwner> blocks on one filing (joint/family filings)
  - <value> wrapper elements that are sometimes absent
  - the document-level Rule 10b5-1 checkbox (<aff10b5One>), plus footnote fallback
    for filings that disclose the plan in prose instead
  - derivative-table rows, which we keep separate from open-market stock buys
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime

from lxml import etree

_PLAN_RE = re.compile(r"10\s*b5[\s\-]*1", re.I)


def norm_cik(raw: str) -> str:
    """EDGAR emits CIKs both zero-padded and bare, sometimes within one feed.

    Everything downstream keys on CIK -- issuer grouping, insider classification,
    watchlist overlap -- so normalise once, here, or clusters silently split.
    """
    raw = (raw or "").strip()
    return raw.lstrip("0") or raw


@dataclass
class Transaction:
    accession: str
    filed_at: date | None
    issuer_cik: str
    issuer_name: str
    ticker: str
    owner_cik: str
    owner_name: str
    is_director: bool
    is_officer: bool
    is_ten_pct: bool
    officer_title: str
    txn_date: date | None
    code: str
    acquired_disposed: str
    shares: float
    price: float
    value: float
    shares_after: float
    direct: bool
    is_derivative: bool
    plan_10b5_1: bool
    security_title: str = ""
    # Position of this transaction row within its filing. A joint filing emits
    # one Transaction per (row x reporting owner), so (accession, txn_index) is
    # the only stable identity for the underlying *economic* trade. Aggregates
    # that sum value or count buyers must dedupe on it or they multiply by the
    # number of co-filers -- see cluster.economic_txns.
    txn_index: int = -1

    @property
    def role(self) -> str:
        """Coarse role bucket: ceo / cfo / officer / director / ten_pct / other.

        Used by the flags and by the buyer-role measurements, never weighted:
        the rubric that paid points per role was removed.
        """
        t = (self.officer_title or "").lower()
        if self.is_officer:
            if re.search(r"\b(cfo|chief financial|finance officer|principal financial)\b", t):
                return "CFO"
            if re.search(r"\b(ceo|chief executive|president and chief|pres\.? & ceo)\b", t):
                return "CEO"
            if re.search(r"\b(coo|chief operating)\b", t):
                return "COO"
            return "Officer"
        if self.is_ten_pct and not self.is_director:
            return "10% Owner"
        if self.is_director:
            return "Director"
        return "Other"

    def as_dict(self) -> dict:
        d = asdict(self)
        d["role"] = self.role
        return d


def _txt(node, path: str) -> str:
    """Read an element that may or may not wrap its content in <value>."""
    el = node.find(path)
    if el is None:
        return ""
    v = el.find("value")
    target = v if v is not None else el
    return (target.text or "").strip()


def _num(node, path: str) -> float:
    raw = _txt(node, path).replace(",", "").replace("$", "")
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _date(raw: str) -> date | None:
    raw = (raw or "").strip()[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _bool(node, path: str) -> bool:
    return _txt(node, path).lower() in {"1", "true", "y", "yes"}


def parse_ownership_xml(
    xml: str | bytes,
    accession: str = "",
    filed_at: date | None = None,
) -> list[Transaction]:
    if isinstance(xml, str):
        xml = xml.encode("utf-8", errors="replace")
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True)
    try:
        root = etree.fromstring(xml, parser=parser)
    except etree.XMLSyntaxError:
        return []
    if root is None:
        return []

    issuer_cik = norm_cik(_txt(root, "issuer/issuerCik"))
    issuer_name = _txt(root, "issuer/issuerName")
    ticker = _txt(root, "issuer/issuerTradingSymbol").upper()

    # Document-level 10b5-1 checkbox (added by the Dec 2022 Form 4 amendments).
    plan_flag = _bool(root, "aff10b5One")
    if not plan_flag:
        footnotes = " ".join(
            (el.text or "") for el in root.iter() if el.tag in ("footnote", "remarks")
        )
        plan_flag = bool(_PLAN_RE.search(footnotes))

    owners = []
    for ro in root.findall("reportingOwner"):
        owners.append(
            {
                "owner_cik": norm_cik(_txt(ro, "reportingOwnerId/rptOwnerCik")),
                "owner_name": _txt(ro, "reportingOwnerId/rptOwnerName"),
                "is_director": _bool(ro, "reportingOwnerRelationship/isDirector"),
                "is_officer": _bool(ro, "reportingOwnerRelationship/isOfficer"),
                "is_ten_pct": _bool(ro, "reportingOwnerRelationship/isTenPercentOwner"),
                "officer_title": _txt(ro, "reportingOwnerRelationship/officerTitle"),
            }
        )
    if not owners:
        return []

    out: list[Transaction] = []
    tables = [
        ("nonDerivativeTable/nonDerivativeTransaction", False),
        ("derivativeTable/derivativeTransaction", True),
    ]
    row_no = 0
    for path, is_deriv in tables:
        for tx in root.findall(path):
            code = _txt(tx, "transactionCoding/transactionCode").upper()
            if not code:
                continue
            row_no += 1
            shares = _num(tx, "transactionAmounts/transactionShares")
            price = _num(tx, "transactionAmounts/transactionPricePerShare")
            ad = _txt(tx, "transactionAmounts/transactionAcquiredDisposedCode").upper()
            after = _num(tx, "postTransactionAmounts/sharesOwnedFollowingTransaction")
            direct = _txt(tx, "ownershipNature/directOrIndirectOwnership").upper() != "I"
            tdate = _date(_txt(tx, "transactionDate"))

            for o in owners:
                out.append(
                    Transaction(
                        accession=accession,
                        filed_at=filed_at,
                        issuer_cik=issuer_cik,
                        issuer_name=issuer_name,
                        ticker=ticker,
                        txn_date=tdate,
                        code=code,
                        acquired_disposed=ad,
                        shares=shares,
                        price=price,
                        value=round(shares * price, 2),
                        shares_after=after,
                        direct=direct,
                        is_derivative=is_deriv,
                        plan_10b5_1=plan_flag,
                        security_title=_txt(tx, "securityTitle"),
                        txn_index=row_no,
                        **o,
                    )
                )
    return out


def open_market_buys(txns: list[Transaction], min_value: float = 0.0) -> list[Transaction]:
    """Filter 2: code P, acquired, non-derivative, not a 10b5-1 plan buy."""
    return [
        t
        for t in txns
        if t.code == "P"
        and t.acquired_disposed == "A"
        and not t.is_derivative
        and not t.plan_10b5_1
        and t.value >= min_value
    ]
