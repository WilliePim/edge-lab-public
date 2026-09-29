"""Dilution check.

The most expensive trap in insider-buying strategies: an insider buys $200k on
the open market a week before the company prices a $50M offering. The purchase
is marketing for the deal, not conviction. It is a real Form 4, real code P,
real money -- every signal filter in this scanner passes it.

This module answers three questions from EDGAR structured data:

  1. Is there a live shelf? (S-3/S-1 effective and unexpired)
  2. Has the company actually drawn on it recently? (424B* takedowns)
  3. Has the share count actually grown? (XBRL, the ground truth)

Ordering matters more than counts. An offering priced AFTER the insider bought
is the trap. An offering priced BEFORE the buy is often the opposite -- the
insider stepping in at the marked-down post-deal price. The verdict logic
distinguishes the two.

Deliberately conservative: when EDGAR data is missing it returns UNKNOWN rather
than CLEAR, because a silent pass here is exactly the failure mode that costs
money.

Recent spin-offs are the one case where missing history is expected rather than
suspicious. An entity spun off eight months ago has no 12-month share count
because it did not exist; comparing against a baseline that predates the
distribution measures the parent, not the company. Those issuers are measured
from the first observation after the spin and land on N/A -- the 12m test did
not apply -- instead of UNKNOWN, which claims a check was attempted and failed.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .edgar import submission_rows

log = logging.getLogger(__name__)

CLEAR = "CLEAR"
CAUTION = "CAUTION"
BLOCKED = "BLOCKED"
UNKNOWN = "UNKNOWN"
NOT_APPLICABLE = "N/A"

#  IL VETO E' SPENTO PER DEFAULT. Il predicato si calcola sempre e il suo verdetto (anche BLOCKED) finisce nei flag e
#  nell'archivio; ma nessun nome viene fermato ne' nascosto dai report finche' il predicato non e' validato. Chi vuole
#  il comportamento storico accende il veto dall'ambiente: EDGE_LAB_DILUTION_VETO=1 (anche true/si/yes/on).
#  `DilutionReport.blocked` resta il valore del PREDICATO (lo usano i backfill); il veto si applica solo dove il
#  predicato fermava un nome: `Card.blocked` e il filtro di scan.py.
VETO_ENV = "EDGE_LAB_DILUTION_VETO"


def veto_attivo() -> bool:
    """True solo se il veto sulla diluizione e' acceso esplicitamente. Default: spento."""
    return (os.environ.get(VETO_ENV) or "").strip().lower() in ("1", "true", "si", "yes", "on")

# Shelf registrations. An effective S-3 is a licence to issue at will.
SHELF_FORMS = {"S-3", "S-3/A", "S-3ASR", "S-3MEF", "S-1", "S-1/A", "S-1MEF"}

# Prospectus supplements = an actual takedown. 424B5 is the classic
# follow-on/ATM supplement; 424B3 often covers resale of PIPE shares.
TAKEDOWN_FORMS = {
    "424B1", "424B2", "424B3", "424B4", "424B5", "424B7", "424B8", "FWP",
}

# Dilutive instruments that price off the market and ratchet down.
TOXIC_FORMS = {"S-3D", "SB-2"}

# SEC Rule 415: a shelf goes stale after three years.
SHELF_LIFE_DAYS = 365 * 3

# Form 10-12B registers a class of securities for exchange listing -- the
# mechanism a spin-off uses to distribute the new entity's stock. 10-12G is
# deliberately NOT here: it is general registration, used mostly by non-traded
# BDCs and lending LPs, which are not spin-offs and would pollute the rule.
SPINOFF_FORMS = {"10-12B", "10-12B/A"}

# Past a year the entity has its own 12-month history and the normal test works.
SPINOFF_MAX_AGE_DAYS = 365

# Two share counts a fortnight apart say nothing about dilution.
MIN_SPIN_BASELINE_GAP_DAYS = 30


@dataclass
class DilutionReport:
    issuer_cik: str
    verdict: str = UNKNOWN
    reasons: list = field(default_factory=list)
    live_shelf: tuple | None = None          # (form, date)
    takedowns_before: list = field(default_factory=list)
    takedowns_after: list = field(default_factory=list)
    shares_growth_pct: float | None = None
    shares_now: float | None = None
    first_filing: date | None = None         # issuer's earliest EDGAR filing
    spin_off_date: date | None = None        # latest 10-12B, if within 12 months
    growth_window_days: int | None = None    # span the growth figure covers

    @property
    def blocked(self) -> bool:
        return self.verdict == BLOCKED

    def summary(self) -> str:
        return f"{self.verdict}: " + "; ".join(self.reasons) if self.reasons else self.verdict


def _growth_phrase(rep: "DilutionReport") -> str:
    """Label a growth figure with the span it actually covers.

    A spin-off's +12% over four months must never render as "+12% in 12m".
    """
    if rep.spin_off_date and rep.growth_window_days:
        return (f"share count {rep.shares_growth_pct:+.0f}% since spin-off "
                f"({rep.growth_window_days}d of history, not a 12m figure)")
    return f"share count +{rep.shares_growth_pct:.0f}% in 12m"


def _d(s: str) -> date | None:
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _all_filings(client, cik: str) -> list[tuple[str, date]]:
    """(form, filing_date) for every filing by an issuer, shards included."""
    out: list[tuple[str, date]] = []
    for row in submission_rows(client, cik):
        d = _d(row["filed"])
        if d:
            out.append((row["form"], d))
    return out


def _spin_off_date(filings: list[tuple[str, date]], as_of: date) -> date | None:
    """Distribution date of a spin-off completed within the last 12 months.

    Anchored on the LAST 10-12B/A rather than the first 10-12B: the registration
    is amended right up to the distribution, so the final amendment sits within
    days of when the stock actually began trading. The initial filing can lead
    it by months, which would shorten the measurable window for no reason.
    """
    spins = sorted(d for f, d in filings if f in SPINOFF_FORMS)
    if not spins:
        return None
    spun = spins[-1]
    return spun if 0 <= (as_of - spun).days <= SPINOFF_MAX_AGE_DAYS else None


def _share_facts(client, cik: str, as_of: date) -> list[tuple[date, float]]:
    """Sorted (date, share count) observations from XBRL, up to as_of."""
    data = client.company_concept(cik, "dei", "EntityCommonStockSharesOutstanding")
    if not data:
        return []
    facts = []
    for unit_rows in (data.get("units") or {}).values():
        for row in unit_rows:
            #  NON point-in-time: si filtra su `end` (fine periodo del fatto), non su
            #  `filed`. Un dato depositato dopo `as_of` entra comunque. È la deviazione
            #  dichiarata in CLAUDE.md; il percorso point-in-time vive in tools/backfill_gates.py.
            d = _d(row.get("end", ""))
            val = row.get("val")
            if d and val and d <= as_of:
                facts.append((d, float(val)))
    facts.sort()
    return facts


def post_spin_share_growth(
    client, cik: str, as_of: date, spun: date,
) -> tuple[float | None, float | None, int | None]:
    """(pct growth since the spin, latest count, window days) for a young spin-off.

    Baseline is the first observation on or after the distribution, because
    anything earlier belongs to the parent. The window is whatever history the
    entity has -- shorter than a year by definition -- so callers must label the
    figure with its span rather than let it read as a 12-month number.
    """
    facts = _share_facts(client, cik, as_of)
    if not facts:
        return None, None, None

    latest_d, latest_v = facts[-1]
    post = [f for f in facts if f[0] >= spun]
    if len(post) < 2:
        return None, latest_v, None

    prior_d, prior_v = post[0]
    window = (latest_d - prior_d).days
    if window < MIN_SPIN_BASELINE_GAP_DAYS or prior_v <= 0:
        return None, latest_v, None

    return round(100.0 * (latest_v - prior_v) / prior_v, 1), latest_v, window


def share_count_growth(client, cik: str, as_of: date) -> tuple[float | None, float | None]:
    """(pct growth over ~1y, latest share count) from XBRL. The ground truth.

    Shelves and prospectuses are intent; the share count is what actually
    happened. A company can carry a shelf for years and never draw on it.
    """
    facts = _share_facts(client, cik, as_of)
    if len(facts) < 2:
        return None, (facts[0][1] if facts else None)

    latest_d, latest_v = facts[-1]

    # Nearest observation to 12 months before the latest one.
    target = latest_d - timedelta(days=365)
    prior_d, prior_v = min(facts[:-1], key=lambda f: abs((f[0] - target).days))

    # Refuse to compute against a stale or too-recent baseline.
    gap = (latest_d - prior_d).days
    if gap < 180 or gap > 700 or prior_v <= 0:
        return None, latest_v

    return round(100.0 * (latest_v - prior_v) / prior_v, 1), latest_v


def check_dilution(
    client,
    issuer_cik: str,
    last_buy_date: date,
    as_of: date | None = None,
    lookback_days: int = 540,
    trap_window_days: int = 75,
    participation_window_days: int = 5,
    growth_block_pct: float = 25.0,
    growth_caution_pct: float = 10.0,
) -> DilutionReport:
    """Classify an issuer's dilution posture around an insider purchase."""
    as_of = as_of or date.today()
    rep = DilutionReport(issuer_cik=issuer_cik)

    filings = _all_filings(client, issuer_cik)
    if not filings:
        rep.verdict = UNKNOWN
        rep.reasons.append("no filing history retrieved")
        return rep

    horizon = as_of - timedelta(days=lookback_days)
    rep.first_filing = min(d for _, d in filings)

    # --- live shelf ------------------------------------------------------
    shelves = sorted(
        [(f, d) for f, d in filings
         if f in SHELF_FORMS and (as_of - d).days <= SHELF_LIFE_DAYS],
        key=lambda x: x[1],
    )
    if shelves:
        rep.live_shelf = shelves[-1]

    # --- takedowns, split by side of the insider buy ----------------------
    for f, d in filings:
        if f not in TAKEDOWN_FORMS and f not in TOXIC_FORMS:
            continue
        if d < horizon:
            continue
        if d >= last_buy_date:
            rep.takedowns_after.append((f, d))
        else:
            rep.takedowns_before.append((f, d))
    rep.takedowns_after.sort(key=lambda x: x[1])
    rep.takedowns_before.sort(key=lambda x: x[1])

    # --- realised dilution ------------------------------------------------
    # A spin-off younger than 12 months has no 12-month share history by
    # construction. The normal path refuses any baseline under 180 days old and
    # returns None, which then reads as UNKNOWN -- indistinguishable from an
    # issuer whose XBRL is genuinely broken. Anchor on the spin instead.
    rep.spin_off_date = _spin_off_date(filings, as_of)
    if rep.spin_off_date:
        (rep.shares_growth_pct, rep.shares_now,
         rep.growth_window_days) = post_spin_share_growth(
            client, issuer_cik, as_of, rep.spin_off_date)
    else:
        rep.shares_growth_pct, rep.shares_now = share_count_growth(
            client, issuer_cik, as_of)

    # --- verdict ----------------------------------------------------------
    # The trap: insider buys, then the company prices a deal days later.
    trap = [
        (f, d) for f, d in rep.takedowns_after
        if 0 <= (d - last_buy_date).days <= trap_window_days
    ]
    if trap:
        f, d = trap[0]
        rep.verdict = BLOCKED
        rep.reasons.append(
            f"{f} filed {(d - last_buy_date).days}d AFTER the insider buy "
            f"-- purchase likely marketing for the offering"
        )
        return rep

    # The mirror trap: the deal priced days BEFORE the buy. Weeks later this is
    # an insider stepping in at the marked-down price, which is the favourable
    # reading the ordering logic was built for. Days later it is the opposite --
    # they are buying the offering itself, at the offering price, allocated to
    # them. Observed live on two IPOs (BRVE, ATTO): 424B4 one day before, every
    # buyer filled at the identical price. Same form, same side, opposite
    # meaning; only the lag separates them.
    participation = [
        (f, d) for f, d in rep.takedowns_before
        if 0 <= (last_buy_date - d).days <= participation_window_days
    ]
    if participation:
        f, d = participation[-1]
        rep.verdict = BLOCKED
        rep.reasons.append(
            f"{f} priced {(last_buy_date - d).days}d BEFORE the buy "
            f"-- purchase is participation in the offering, not open-market conviction"
        )
        if rep.first_filing and (last_buy_date - rep.first_filing).days <= 365:
            rep.reasons.append(
                f"issuer's first EDGAR filing {(as_of - rep.first_filing).days}d ago "
                f"-- newly public, consistent with an IPO allocation"
            )
        return rep

    if rep.shares_growth_pct is not None and rep.shares_growth_pct >= growth_block_pct:
        rep.verdict = BLOCKED
        rep.reasons.append(_growth_phrase(rep))
        return rep

    if rep.takedowns_after:
        f, d = rep.takedowns_after[0]
        rep.verdict = CAUTION
        rep.reasons.append(f"{f} filed {(d - last_buy_date).days}d after the buy")

    if rep.shares_growth_pct is not None and rep.shares_growth_pct >= growth_caution_pct:
        rep.verdict = CAUTION          # ogni via BLOCKED qui sopra ha gia' restituito
        rep.reasons.append(_growth_phrase(rep))

    if rep.live_shelf and not rep.takedowns_after:
        f, d = rep.live_shelf
        age = (as_of - d).days
        if rep.verdict == UNKNOWN:
            rep.verdict = CAUTION
        rep.reasons.append(f"live {f} shelf filed {age}d ago, not yet drawn post-buy")

    if rep.takedowns_before and rep.verdict in (UNKNOWN, CAUTION):
        f, d = rep.takedowns_before[-1]
        rep.reasons.append(
            f"note: {f} priced {(last_buy_date - d).days}d BEFORE the buy "
            f"-- insider may be stepping in post-deal"
        )

    if rep.verdict == UNKNOWN:
        if rep.spin_off_date:
            # Nothing adverse found, but this issuer never sat the 12-month
            # test. CLEAR would overstate it and UNKNOWN would understate it:
            # the check did not fail, it does not apply yet.
            age = (as_of - rep.spin_off_date).days
            rep.verdict = NOT_APPLICABLE
            if rep.shares_growth_pct is None:
                rep.reasons.append(
                    f"spun off {age}d ago -- too little post-spin share history to "
                    f"measure; no shelf or takedown found"
                )
            else:
                rep.reasons.append(
                    f"spun off {age}d ago -- no shelf, no takedown, "
                    f"{_growth_phrase(rep)}"
                )
        elif rep.shares_growth_pct is None:
            rep.reasons.append("no share-count history; no shelf or takedown found")
        else:
            rep.verdict = CLEAR
            rep.reasons.append(
                f"no shelf, no takedown, share count {rep.shares_growth_pct:+.1f}% in 12m"
            )

    return rep
