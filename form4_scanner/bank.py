"""Depository institutions: no ranking on insider buying alone.

A bank's insider buy looks identical to any other on a Form 4, but the thing
that kills a bank is not on the Form 4 at all -- it is the loan book. Insiders
at a bank with a deteriorating book have every reason to buy publicly while the
book deteriorates privately, and nothing this scanner reads on the filing -- who
bought, how many of them, how close together -- looks any different on a healthy
bank and a sick one.

So the asset-quality answer travels with the name instead of being folded into
it. The check is NPA / gross loans, both from XBRL. Roughly half of small banks
tag nonaccruals; the other half disclose them only in 10-K prose, which this
module deliberately does not parse -- guessing at asset quality is worse than
saying the check did not run.

What comes out is one of three words -- ELEVATED, OK, UNVERIFIED -- rendered as a
flag on the card (flags.py). It caps nothing: the cap it used to feed was a
ceiling on the twelve-point score, and that score was removed after measurement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

log = logging.getLogger(__name__)

OK = "OK"
ELEVATED = "ELEVATED"
UNVERIFIED = "UNVERIFIED"

# SIC codes that mean "takes deposits and lends them out". 6712 is the bank
# holding company wrapper most listed banks actually file under. Insurance
# (63xx) and brokers (62xx) are deliberately absent: they carry different risk
# and the NPA ratio would be meaningless for them.
DEPOSITORY_SIC = {
    "6020",  # national commercial banks
    "6021",  # state commercial banks, national
    "6022",  # state commercial banks
    "6035",  # savings institutions, federally chartered
    "6036",  # savings institutions, state chartered
    "6712",  # bank holding companies
}

# Post-CECL and pre-CECL spellings of the same disclosure.
NONACCRUAL_TAGS = (
    "FinancingReceivableRecordedInvestmentNonaccrualStatus",
    "FinancingReceivableExcludingAccruedInterestNonaccrual",
    "FinancingReceivableNonaccrual",
    "LoansAndLeasesReceivableNonaccrualStatus",
)

GROSS_LOAN_TAGS = (
    "FinancingReceivableExcludingAccruedInterestBeforeAllowanceForCreditLoss",
    "LoansAndLeasesReceivableNetReportedAmount",
    "NotesReceivableGross",
)

# Above this the loan book is the story, not the insider buy.
NPA_ELEVATED_PCT = 2.0

# Nonaccruals and loan balances must describe the same balance sheet.
MAX_PAIRING_GAP_DAYS = 100

@dataclass
class BankReport:
    issuer_cik: str
    is_depository: bool = False
    sic: str = ""
    status: str = UNVERIFIED
    npa_pct: float | None = None
    nonaccrual: float | None = None
    gross_loans: float | None = None
    as_of: date | None = None
    reasons: list = field(default_factory=list)

    @property
    def capped(self) -> bool:
        """A depository that did not clear the asset-quality check."""
        return self.is_depository and self.status != OK

    def summary(self) -> str:
        return f"{self.status}: " + "; ".join(self.reasons) if self.reasons else self.status


def _latest_fact(client, cik: str, tags, as_of: date) -> tuple[date, float] | None:
    """Newest (end, value) at or before as_of across a list of candidate tags."""
    best: tuple[date, float] | None = None
    for tag in tags:
        data = client.company_concept(cik, "us-gaap", tag)
        if not data:
            continue
        for unit_rows in (data.get("units") or {}).values():
            for row in unit_rows:
                end = row.get("end", "")
                val = row.get("val")
                if val is None:
                    continue
                try:
                    d = date.fromisoformat(end[:10])
                except (ValueError, TypeError):
                    continue
                if d > as_of:
                    continue
                if best is None or d > best[0]:
                    best = (d, float(val))
        if best is not None:
            # First tag that yields anything wins; the alternates are spellings
            # of the same disclosure, not independent measurements to merge.
            return best
    return best


def is_depository(client, cik: str) -> tuple[bool, str]:
    subs = client.submissions(cik) or {}
    sic = str(subs.get("sic", "") or "").strip()
    return sic in DEPOSITORY_SIC, sic


def check_bank(client, issuer_cik: str, as_of: date | None = None) -> BankReport:
    """Asset-quality gate for depositories. Non-banks come back untouched."""
    as_of = as_of or date.today()
    rep = BankReport(issuer_cik=issuer_cik)

    rep.is_depository, rep.sic = is_depository(client, issuer_cik)
    if not rep.is_depository:
        rep.status = OK
        return rep

    na = _latest_fact(client, issuer_cik, NONACCRUAL_TAGS, as_of)
    gl = _latest_fact(client, issuer_cik, GROSS_LOAN_TAGS, as_of)

    if na is None or gl is None:
        missing = "nonaccruals" if na is None else "gross loans"
        rep.status = UNVERIFIED
        rep.reasons.append(
            f"no {missing} tagged in XBRL -- asset quality not verifiable from "
            f"structured data, check the 10-K credit-quality tables by hand"
        )
        return rep

    (na_d, na_v), (gl_d, gl_v) = na, gl
    if abs((na_d - gl_d).days) > MAX_PAIRING_GAP_DAYS:
        rep.status = UNVERIFIED
        rep.reasons.append(
            f"nonaccruals ({na_d}) and loan balance ({gl_d}) are "
            f"{abs((na_d - gl_d).days)}d apart -- not the same balance sheet"
        )
        return rep
    if gl_v <= 0:
        rep.status = UNVERIFIED
        rep.reasons.append("gross loan balance is zero or negative")
        return rep

    rep.nonaccrual, rep.gross_loans = na_v, gl_v
    rep.as_of = na_d
    rep.npa_pct = round(100.0 * na_v / gl_v, 2)

    if rep.npa_pct > NPA_ELEVATED_PCT:
        rep.status = ELEVATED
        rep.reasons.append(
            f"NPA/loans {rep.npa_pct:.2f}% as of {na_d} -- above the "
            f"{NPA_ELEVATED_PCT:.1f}% line; the loan book is the story here"
        )
    else:
        rep.status = OK
        rep.reasons.append(f"NPA/loans {rep.npa_pct:.2f}% as of {na_d}")
    return rep
