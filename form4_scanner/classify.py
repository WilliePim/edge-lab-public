"""Routine vs. opportunistic insider classification.

Cohen, Malloy & Pomorski (2012), "Decoding Inside Information":
an insider who trades in the *same calendar month* in each of the prior three
years is routine -- their trades carry essentially no information. Insiders who
traded in each of the prior three years without that month-pattern are
opportunistic, and it is their trades that carry the abnormal return.

Two departures from the paper, both deliberate:

  NOVEL -- an insider with no purchases at all in the prior three years. CMP
  leave these unclassified. Empirically a first purchase after a long silence is
  informative, so it gets its own bucket and is read like opportunistic.

  SPARSE -- traded in some but not all of the prior three years. Genuinely
  ambiguous; sits between the two.

  UNSEASONED -- an empty history that proves nothing, because the CIK itself is
  too new to have one. NOVEL means "a veteran broke a long silence"; a CIK
  registered days before the trade has no silence to break. Observed live: four
  Forbion vehicles collected NOVEL's full credit on CIKs created five days
  earlier. Carries no credit: it is an absence of evidence, not evidence.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from .edgar import submission_rows

ROUTINE = "routine"
OPPORTUNISTIC = "opportunistic"
NOVEL = "novel"
SPARSE = "sparse"
UNSEASONED = "unseasoned"


@dataclass
class InsiderProfile:
    owner_cik: str
    owner_name: str
    label: str
    prior_purchase_count: int
    years_active: int
    modal_month: int | None
    reason: str


def classify_insider(
    owner_cik: str,
    owner_name: str,
    prior_txn_dates: list[date],
    as_of: date,
    lookback_years: int = 3,
    cik_first_filing: date | None = None,
    min_history_days: int = 365,
) -> InsiderProfile:
    """`prior_txn_dates` = dates of this insider's purchases STRICTLY BEFORE `as_of`.

    Feed it purchases only. Mixing in sales makes a serial seller look 'active'
    and mislabels them routine.

    `cik_first_filing` is the insider CIK's earliest filing of any kind. It
    separates a genuinely empty record from an unobservable one. Left None the
    distinction cannot be drawn, and the benefit of the doubt goes to NOVEL --
    absent evidence we do not invent a downgrade.
    """
    # Rolling 12-month blocks anchored on as_of, NOT calendar years. A March
    # buyer evaluated in August must still see his three most recent Marches;
    # calendar-year buckets would drop the oldest one and mislabel him.
    def block_of(d: date) -> int | None:
        days = (as_of - d).days
        if days <= 0:
            return None
        b = days // 365
        return b if b < lookback_years else None

    by_block: dict[int, set[int]] = defaultdict(set)
    hist = []
    for d in prior_txn_dates:
        if not d:
            continue
        b = block_of(d)
        if b is None:
            continue
        hist.append(d)
        by_block[b].add(d.month)

    if not hist:
        observable = (
            (as_of - cik_first_filing).days if cik_first_filing else None
        )
        if observable is not None and observable < min_history_days:
            return InsiderProfile(
                owner_cik, owner_name, UNSEASONED, 0, 0, None,
                f"CIK first filed {observable}d ago -- empty history proves nothing",
            )
        return InsiderProfile(
            owner_cik, owner_name, NOVEL, 0, 0, None,
            f"no open-market purchases in prior {lookback_years}y",
        )

    active = len(by_block)
    modal_month = Counter(d.month for d in hist).most_common(1)[0][0]

    if active < lookback_years:
        return InsiderProfile(
            owner_cik, owner_name, SPARSE, len(hist), active, modal_month,
            f"purchases in {active}/{lookback_years} trailing years",
        )

    # Routine: one calendar month recurs in every trailing year.
    recurring = [
        m for m in range(1, 13)
        if all(m in by_block.get(b, set()) for b in range(lookback_years))
    ]
    if recurring:
        return InsiderProfile(
            owner_cik, owner_name, ROUTINE, len(hist), active, recurring[0],
            f"bought in month {recurring[0]:02d} in each of the prior {lookback_years} years",
        )

    return InsiderProfile(
        owner_cik, owner_name, OPPORTUNISTIC, len(hist), active, modal_month,
        f"active {lookback_years}/{lookback_years} years, no recurring month",
    )


def first_filing_date(client, owner_cik: str) -> date | None:
    """Earliest EDGAR filing of any kind by this CIK, or None if unknowable.

    Costs nothing extra: the submissions JSON is already fetched and disk-cached
    by the history walk, and the older shards advertise their own date range in
    `filingFrom`, so there is no need to open them.
    """
    subs = client.submissions(owner_cik)
    if not subs:
        return None
    stamps = list(subs.get("filings", {}).get("recent", {}).get("filingDate", []))
    stamps += [
        f["filingFrom"]
        for f in subs.get("filings", {}).get("files", [])
        if f.get("filingFrom")
    ]
    parsed = []
    for s in stamps:
        try:
            parsed.append(datetime.strptime(str(s)[:10], "%Y-%m-%d").date())
        except (ValueError, TypeError):
            continue
    return min(parsed) if parsed else None


def build_purchase_history(client, owner_cik: str, since: date) -> list[date]:
    """Walk an insider CIK's own submission history and collect purchase dates.

    Insiders hold their own CIK, so data.sec.gov/submissions/CIK##########.json
    returns every Form 3/4/5 they have ever filed across all issuers -- which is
    what you want, since routineness is a property of the person.
    """
    from .parse import parse_ownership_xml

    dates: list[date] = []
    for row in submission_rows(client, owner_cik):
        accession, form, filed = row["accession"], row["form"], row["filed"]
        if form not in ("4", "4/A"):
            continue
        if filed and filed < since.isoformat():
            continue
        xml = client.ownership_xml(owner_cik, accession)
        if not xml:
            continue
        for t in parse_ownership_xml(xml, accession):
            if (
                t.owner_cik.lstrip("0") == owner_cik.lstrip("0")
                and t.code == "P"
                and t.acquired_disposed == "A"
                and not t.is_derivative
                and t.txn_date
            ):
                dates.append(t.txn_date)
    return sorted(set(dates))
