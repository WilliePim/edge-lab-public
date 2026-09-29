"""Flags, recorded inputs, and score_v3. What survives the removal of the rubric.

Two jobs that used to live inside `score.py` and have nothing to do with
scoring:

  the CONTEXT FLAGS -- capitalisation band, survivability, uniform fill price,
  dilution verdict -- which are read by a human and never summed;

  the RECORDED INPUTS, which are what the observations archive keeps so that a
  row written today can be re-read under a rule that does not exist yet.

Extracted here first, unchanged, so that deleting `score.py` afterwards cannot
take them with it. During the extraction commit `score.py` calls into this
module: behaviour is identical by construction, not by inspection.

SCORE_V3, and what it deliberately is not.

    cluster    >= 2 distinct opportunistic buyers inside the cluster window
    director   at least one independent director among the buyers
    no_10pct   no 10% owner among the buyers
    terreno    the purchase falls inside an active spin-off window

Four booleans, weight 1 each, no threshold. It is an ORDERING, not a measure:
nothing here is calibrated, and the gates upstream award no points for being
passed -- a veto is not a criterion.

Adding a fifth component requires a measured, pre-registered result and a line
here citing it. That rule exists because the v2 rubric grew to seven criteria of
which one was ever measured, and it was measured backwards.

The cluster window is `cluster_window_days` as the pipeline already sets it --
30 days. Every measurement in reports/ was made at 30, and changing it would
invalidate them rather than improve the score.

`terreno` is None, not False, when data/spinoffs_index.json is missing. The index
is not shipped with the code: tools/spinoffs.py builds it from EDGAR. Until it is
built, None is what the fail-closed rule leaves: not measured, which must stay
distinguishable from measured and absent.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from .bank import ELEVATED
from .classify import OPPORTUNISTIC, ROUTINE, SPARSE, UNSEASONED
from .dilution import BLOCKED, CAUTION, NOT_APPLICABLE, UNKNOWN, veto_attivo

SPINOFF_INDEX = Path(__file__).resolve().parents[1] / "data" / "spinoffs_index.json"
SPINOFF_WINDOW_DAYS = 90


# ------------------------------------------------------------- predicates ---
# ------------------------------------------------------- fasce di cap ------
#  One definition, everywhere. Before this there were two hand-written
#  comparisons in context_flags, a pair of defaults in scan.py, and the word
#  "stratum" in the spin-off tool, and nothing kept them in step. Boundaries
#  are inclusive on the left: 300e6 is `small`, not `micro`.
CAP_BANDS = (
    ("nano",   0.0,    50e6),
    ("micro",  50e6,   300e6),
    ("small",  300e6,  2e9),
    ("mid",    2e9,    10e9),
    ("large",  10e9,   200e9),
    ("mega",   200e9,  float("inf")),
)
UNKNOWN_BAND = "unknown"

def bands_for_range(lo, hi):
    """The bands a [lo, hi) capitalisation filter spans. Derived, never typed.

    scan.py keeps the numbers because the CLI can override them; this turns
    whatever numbers are in force into the band names a reader recognises.
    """
    return [name for name, l, h in CAP_BANDS if h > lo and l < hi]


def cap_bucket(cap):
    """nano / micro / small / mid / large / mega, or 'unknown' when absent.

    The ONLY place a market capitalisation is compared with a number.
    """
    if cap is None:
        return UNKNOWN_BAND
    try:
        v = float(cap)
    except (TypeError, ValueError):
        return UNKNOWN_BAND
    if v != v or v < 0:                       # NaN, or a negative that is noise
        return UNKNOWN_BAND
    for name, lo, hi in CAP_BANDS:
        if lo <= v < hi:
            return name
    return UNKNOWN_BAND


def is_independent_director(txn) -> bool:
    """Director, and neither an officer nor a 10% holder.

    The distinction the v2 rubric never drew: `role` collapsed to "Director"
    whenever the officer and ten-percent booleans were both false, which is the
    same set, but it was worth 0 points beside CEO's 2. Neither weight had a
    measurement behind it, and none is used now.
    """
    return bool(txn.is_director and not txn.is_officer and not txn.is_ten_pct)


#  A reporting owner is a natural person or an entity, and Form 4 has no field
#  that says which: the distinction has to come from the name. These are the
#  tokens, declared here and in RULES.md so the rule is reproducible. A name
#  that matches nothing is NOT called a person -- it is simply not called an
#  entity, which is the fail-closed reading.
ENTITY_TOKENS = (
    " LLC", " L.L.C", " LP", " L.P", " INC", " CORP", " LTD", " PLC", " TRUST",
    " FUND", " PARTNERS", " CAPITAL", " MANAGEMENT", " ADVISORS", " ADVISERS",
    " HOLDINGS", " GROUP", " ASSOCIATES", " VENTURES", " GP", " & CO",
)


def looks_like_entity(owner_name: str) -> bool:
    """True when the owner name carries one of ENTITY_TOKENS. Declared, not learned."""
    n = " " + (owner_name or "").upper().replace(",", " ").replace(".", ". ")
    return any(tok in n for tok in ENTITY_TOKENS)


def max_window_count(txns, window_days: int = 30) -> int:
    """Most purchases falling inside any `window_days` span. Same shape as
    cluster.max_window_buyers, counting transactions instead of buyers."""
    dates = sorted(t.txn_date for t in txns if t.txn_date)
    best = 0
    for i, start in enumerate(dates):
        j = i
        while j < len(dates) and (dates[j] - start).days <= window_days:
            j += 1
        best = max(best, j - i)
    return best


def is_ten_pct(txn) -> bool:
    return bool(txn.is_ten_pct)


# ---------------------------------------------------------------- terreno ---
@lru_cache(maxsize=1)
def _load_spinoffs():
    """L'indice degli spin-off, letto una volta per processo.

    Lo scanner e' un comando che parte e finisce; prima il file (46 KB) veniva
    riletto e ri-analizzato per ogni emittente valutato.
    """
    if not SPINOFF_INDEX.exists():
        return None
    try:
        return json.loads(SPINOFF_INDEX.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def in_spinoff_window(issuer_cik: str, buy_date: date,
                      window_days: int = SPINOFF_WINDOW_DAYS):
    """True / False / None. None while the index does not exist.

    None is not a soft False. A missing index means the question was never
    asked, and an archive that cannot tell that from "asked and the answer was
    no" is the archive CLAUDE.md forbids.
    """
    idx = _load_spinoffs()
    if idx is None:
        return None
    cik = str(issuer_cik).lstrip("0")
    for child in idx.get("children", []):
        if str(child.get("cik", "")).lstrip("0") != cik:
            continue
        raw = child.get("date_distribution")
        if not raw:
            continue
        try:
            start = date.fromisoformat(raw)
        except ValueError:
            continue
        if start <= buy_date <= start + timedelta(days=window_days):
            return True
    return False


# --------------------------------------------------------------- score_v3 ---
def score_v3(cluster, labels: dict, cluster_window_days: int = 30) -> dict:
    """{score, cluster, director, no_10pct, terreno} -- four booleans, weight 1.

    `score` sums only the booleans that are True; a None (terreno, with no
    index) adds nothing and is reported as None rather than folded into False.
    """
    opp_groups = 0
    for group in cluster.buyer_groups:
        if any(labels.get(c) == OPPORTUNISTIC for c in group):
            opp_groups += 1
    #  Counted on buyer GROUPS, not CIKs: co-filing affiliates of one fund are
    #  one decision. cluster.buyer_groups already unions them by accession.
    has_cluster = opp_groups >= 2 and cluster.max_window_buyers(
        cluster_window_days) >= 2

    txns = cluster.txns
    has_director = any(is_independent_director(t) for t in txns)
    no_10pct = not any(is_ten_pct(t) for t in txns)

    first_buy = min((t.txn_date for t in txns if t.txn_date), default=None)
    terreno = (in_spinoff_window(cluster.issuer_cik, first_buy)
               if first_buy else None)

    out = {"cluster": has_cluster, "director": has_director,
           "no_10pct": no_10pct, "terreno": terreno}
    out["score"] = sum(1 for k in ("cluster", "director", "no_10pct", "terreno")
                       if out[k] is True)
    return out


# ------------------------------------------------------------------ flags ---
def context_flags(card, snap, cluster) -> str:
    """Capitalisation band, survivability, uniform fill. Appends to card.flags.

    Returns the survivability verdict because the caller records it too, and
    computing it twice would be two places to change it.
    """
    #  The band, and nothing about what the band is worth. "anomaly largely
    #  arbitraged away" and "promotional risk, check for ATM/dilution" were
    #  a verdict and an instruction, and neither traces to a filing field or to
    #  a rule in RULES.md -- CLAUDE.md, confine fra scanner e giudizio.
    band = cap_bucket(snap.market_cap)
    card.context["cap_bucket"] = band
    if band in ("large", "mega"):
        card.flags.append(
            f"market cap ${snap.market_cap / 1e9:.1f}B -- fascia {band}")
    elif band == "nano":
        card.flags.append(
            f"market cap ${snap.market_cap / 1e6:.0f}M -- fascia nano")
    surv = snap.survivability_flag
    if surv == "LEVERED + BURNING":
        card.flags.append("VETO CHECK: levered and cash-burning")

    # Independent of EDGAR: open-market executions land on different prints, an
    # offering fills everyone at the deal price. Corroborates the dilution
    # gate's participation veto, and catches the case where the prospectus is
    # filed too late for the gate to see it.
    px = cluster.uniform_price
    if px is not None:
        #  Was "offering price, not open market", which is the conclusion the
        #  reader should draw, not a field. The fields: the transaction code
        #  (open_market_buys admits only P), the identical fill, how many
        #  filled at it, and the snapshot price with the hour it was taken.
        #  The market price ON THE TRANSACTION DATE is not available on the
        #  live path -- MarketSnapshot carries a spot quote, not a series --
        #  so it is not claimed. See RULES.md 9.
        n_at = len([t for t in cluster.txns if t.price == px])
        ref = (f"; snapshot ${snap.price:g} at {snap.fetched_at}"
               if snap.price else "")
        card.flags.append(
            f"code P, {n_at} fill(s) at an identical ${px:g}{ref}")
    return surv


def dilution_flags(card, dilution) -> None:
    """The dilution predicate, as a flag (a predicate, not validated). The
    verdict itself goes in context."""
    if dilution:
        if dilution.verdict == BLOCKED and veto_attivo():
            card.flags.append(f"DILUTION VETO -- {'; '.join(dilution.reasons)}")
        elif dilution.verdict == BLOCKED:
            card.flags.append(
                f"dilution predicate: blocked (veto off, not validated) -- {'; '.join(dilution.reasons)}")
        elif dilution.verdict in (CAUTION, UNKNOWN, NOT_APPLICABLE):
            card.flags.append(
                f"dilution {dilution.verdict.lower()} -- {'; '.join(dilution.reasons)}")



# ------------------------------------------------------------------- card ---
@dataclass
class Card:
    """What one issuer's cluster looks like after v3. No score, no components.

    `context` replaces the old `components` dict for the underscore-prefixed
    keys the rubric used as a scratch area -- first/last buy date, market cap,
    survivability, total value. They were never scores; they were only stored
    there because that dict happened to exist.
    """
    ticker: str
    issuer_name: str
    issuer_cik: str
    flags: list = field(default_factory=list)
    inputs: dict = field(default_factory=dict)
    context: dict = field(default_factory=dict)
    v3: dict = field(default_factory=dict)
    dilution: object = None
    bank: object = None
    vehicle: object = None

    @property
    def blocked(self) -> bool:
        #  Il predicato puo' dire BLOCKED; il nome e' fermato solo col veto acceso (dilution.veto_attivo).
        return bool(self.dilution and self.dilution.blocked and veto_attivo())

    def record(self, name: str, **values) -> None:
        self.inputs[name] = values


def evaluate_cluster(cluster, labels, snap, dilution=None, bank=None,
                     vehicle=None, cluster_window_days: int = 30) -> Card:
    """Everything score_cluster did except award points.

    Three inputs are recorded, not seven: buyer_quality, cluster, role. The
    four that are gone -- size, drawdown, coverage, specialist_overlap -- were
    removed because they were measured and did not separate, not because they
    were expensive. reports/size_component_test.md and
    reports/rubric_discrimination.md carry the verdicts.
    """
    card = Card(ticker=cluster.ticker, issuer_name=cluster.issuer_name,
                issuer_cik=cluster.issuer_cik,
                dilution=dilution, bank=bank, vehicle=vehicle)

    #  Un CIK assente da `labels` non è misurato: nell'archivio ci va None, non SPARSE,
    #  altrimenti una classificazione mancata diventerebbe per sempre una misurata
    #  (fail-closed, CLAUDE.md). Per i flag qui sotto vale ancora il ripiego prudente.
    misurate = {t.owner_cik: labels.get(t.owner_cik) for t in cluster.txns}
    quality = {e or SPARSE for e in misurate.values()}
    card.record("buyer_quality", labels_by_owner=misurate, labels_present=sorted(quality))
    if ROUTINE in quality:
        #  Was "historically no signal": a gloss with no measurement cited. The
        #  flag now states the classification (Cohen-Malloy-Pomorski, classify.py)
        #  and claims no effect.
        card.flags.append(
            "routine buyer in the cluster (CMP classification; no effect claimed)")
    if UNSEASONED in quality:
        card.flags.append(
            "buyer CIKs too new to have a history -- no signal either way")

    n = cluster.max_window_buyers(cluster_window_days)
    card.record("cluster", window_days=cluster_window_days, buyers_in_window=n,
                distinct_buyers=cluster.distinct_buyers,
                buyer_groups=len(cluster.buyer_groups))

    roles = cluster.roles
    card.record("role", roles=sorted(roles),
                officer_titles=sorted({t.officer_title for t in cluster.txns
                                       if t.officer_title}))
    if "10% Owner" in roles:
        #  Was "fund accumulation", which read the buyer's intention off a
        #  checkbox. What is on the filing: the flag, whether the name is an
        #  entity by the declared token rule, and how many of its purchases
        #  fall inside one 30-day window.
        tens = [t for t in cluster.txns if is_ten_pct(t)]
        n_tens = max_window_count(tens, cluster_window_days)
        kind = ("entity by name" if any(looks_like_entity(t.owner_name)
                                        for t in tens) else "name not matched")
        card.flags.append(
            f"10% owner on the filing ({kind}) -- {n_tens} purchase(s) "
            f"in {cluster_window_days}d")

    surv = context_flags(card, snap, cluster)
    dilution_flags(card, dilution)

    #  The depository cap was a ceiling on a score. With no score it becomes
    #  what it always described: a bank whose loan book nobody has looked at.
    if bank and bank.capped:
        why = ("NPA elevated" if bank.status == ELEVATED
               else "asset quality unverified")
        card.context["npa_pct"] = bank.npa_pct
        card.flags.append(f"DEPOSITORY -- {why}; {'; '.join(bank.reasons)}")
    elif bank and bank.is_depository:
        card.context["npa_pct"] = bank.npa_pct
        card.flags.append(
            f"depository, asset quality checked -- {'; '.join(bank.reasons)}")

    if vehicle is not None and vehicle.is_vehicle:
        card.context["vehicle"] = vehicle.kind
        card.flags.append(vehicle.flag())

    card.context.update(
        first_buy_date=cluster.first_date, last_buy_date=cluster.last_date,
        survivability=surv, market_cap=snap.market_cap,
        total_value=cluster.total_value,
        dilution=(dilution.verdict if dilution else "not checked"),
    )
    card.v3 = score_v3(cluster, labels, cluster_window_days)
    return card
