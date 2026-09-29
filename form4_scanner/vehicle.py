"""Externally-managed vehicles: BDCs, REITs, and who sponsors them.

An insider buy at an operating company and an insider buy at an externally
managed vehicle are different events wearing the same form. At an operating
company the buyer runs the business. At an externally managed BDC or mortgage
REIT there is no business to run and often no employees at all: the buyer is an
officer of the *manager*, and the manager earns fees on assets under management.
Buying units of the vehicle it manages is a defensible signal, but it is not the
signal this scanner reads: it says something about the manager's fee base, not
about a person putting their own money behind a business they run.

Two things are reliably detectable from structured EDGAR data and one is not.

  Detectable: **BDC status**, from the N-54A election, which is definitive; and
  **REIT status**, from SIC 6798.

  Not detectable: **whether management is external.** It lives in prose in the
  10-K, and the tell that would identify it mechanically -- no employees --
  is not a tagged fact. So this module does not claim it. It reports the vehicle
  class, which it knows, and says plainly that external management is inferred
  from that class rather than verified. `vehicles.json` lets the operator pin
  the answer either way for names they have actually read.

The sponsor grouping exists because two vehicles from one sponsor are not two
independent signals. Chicago Atlantic BDC and Chicago Atlantic Real Estate
Finance appearing in the same week is one manager, twice.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from .edgar import submission_rows

log = logging.getLogger(__name__)

BDC = "BDC"
REIT = "REIT"
REAL_ESTATE = "REAL ESTATE"

#  A BDC elects its status on Form N-54A and withdraws it on N-54C. The election
#  is definitive -- there is no ambiguity about whether a filer is a BDC.
BDC_ELECTION_FORMS = frozenset({"N-54A"})
BDC_WITHDRAWAL_FORMS = frozenset({"N-54C"})

REIT_SIC = frozenset({"6798"})
REAL_ESTATE_SIC = frozenset({"6500", "6512", "6531", "6552"})

#  Legal wrappers and vehicle nouns, stripped before comparing names. They carry
#  no sponsor information: half the vehicles in existence are called something
#  "Capital Trust Inc".
_NOISE = frozenset({
    "inc", "incorporated", "corp", "corporation", "co", "company", "llc", "lp",
    "llp", "ltd", "limited", "plc", "nv", "sa", "ag", "trust", "the",
})

_PUNCT = re.compile(r"[^A-Za-z0-9 ]+")

#  Two vehicles are treated as sharing a sponsor only when their names agree on
#  at least this many leading tokens. One is not enough: "Chicago Atlantic BDC"
#  and "Chicago Bridge & Iron" share a first word and nothing else.
MIN_SPONSOR_TOKENS = 2


@dataclass
class VehicleReport:
    issuer_cik: str
    issuer_name: str = ""
    kind: str = ""                      # BDC | REIT | REAL ESTATE | ""
    sic: str = ""
    #  True/False only when vehicles.json says so; None means "inferred from the
    #  class, not verified".
    externally_managed: bool | None = None
    sponsor: str = ""
    sponsor_peers: tuple = ()           # other tickers in this run, same sponsor
    reasons: list = field(default_factory=list)

    @property
    def is_vehicle(self) -> bool:
        return bool(self.kind)

    def flag(self) -> str:
        """The line the report shows. Says how much is known, not more."""
        if not self.is_vehicle:
            return ""
        if self.externally_managed is False:
            head = f"internally-managed {self.kind}"
        elif self.externally_managed is True:
            head = f"externally-managed {self.kind}"
        else:
            #  The usual structure for these vehicles, but usual is not
            #  verified, and the flag must not read as though it were.
            head = f"{self.kind} (external mgmt inferred, unverified)"
        bits = [head]
        if self.externally_managed is not False:
            bits.append("a buy here may be the manager buying its own vehicle")
        if self.sponsor:
            bits.append(f"sponsor: {self.sponsor}")
        if self.sponsor_peers:
            bits.append(f"same sponsor as {', '.join(self.sponsor_peers)} in "
                        f"this run -- one manager, not independent signals")
        for r in self.reasons:
            bits.append(r)
        return "; ".join(bits)


def name_tokens(name: str) -> tuple:
    """Normalised leading tokens of an issuer name, noise words removed."""
    cleaned = _PUNCT.sub(" ", str(name or ""))
    return tuple(t.upper() for t in cleaned.split()
                 if t and t.lower() not in _NOISE)


def shared_sponsor(a: str, b: str) -> str:
    """The common sponsor prefix of two issuer names, or "" if they differ."""
    ta, tb = name_tokens(a), name_tokens(b)
    common = []
    for x, y in zip(ta, tb):
        if x != y:
            break
        common.append(x)
    if len(common) < MIN_SPONSOR_TOKENS:
        return ""
    return " ".join(common).title()


def classify_vehicle(client, issuer_cik: str, issuer_name: str = "",
                     overrides: dict | None = None) -> VehicleReport:
    """Vehicle class for one issuer. One cached submissions read."""
    rep = VehicleReport(issuer_cik=issuer_cik, issuer_name=issuer_name)
    overrides = overrides or {}

    subs = client.submissions(issuer_cik) or {}
    rep.sic = str(subs.get("sic", "") or "").strip()

    #  The WHOLE filing history, shards included. Reading `recent` alone would
    #  miss the N-54A of any BDC that elected more than a few hundred filings
    #  ago -- which is most of them, and exactly the long-established vehicles
    #  worth flagging.
    forms = {row["form"] for row in submission_rows(client, issuer_cik)}

    if forms & BDC_ELECTION_FORMS:
        rep.kind = BDC
        rep.reasons.append("elected BDC status on Form N-54A")
        if forms & BDC_WITHDRAWAL_FORMS:
            #  Election and withdrawal both present: the filer has been a BDC at
            #  some point, and only the dates say whether it still is. Reported
            #  rather than resolved, because guessing here is worse than saying.
            rep.reasons.append("N-54C withdrawal also on file -- BDC status may "
                               "have lapsed, check the dates")
    elif rep.sic in REIT_SIC:
        rep.kind = REIT
        rep.reasons.append(f"SIC {rep.sic}, real estate investment trust")
    elif rep.sic in REAL_ESTATE_SIC:
        rep.kind = REAL_ESTATE
        rep.reasons.append(f"SIC {rep.sic}, real estate")

    if not rep.is_vehicle:
        return rep

    key = str(issuer_cik).lstrip("0")
    entry = overrides.get(key) or overrides.get(str(issuer_cik)) \
        or overrides.get((issuer_name or "").upper())
    if isinstance(entry, dict):
        if "externally_managed" in entry:
            rep.externally_managed = bool(entry["externally_managed"])
            rep.reasons.append("management structure confirmed by hand in "
                               "vehicles.json")
        if entry.get("sponsor"):
            rep.sponsor = str(entry["sponsor"])
    elif isinstance(entry, bool):
        rep.externally_managed = entry
        rep.reasons.append("management structure confirmed by hand in "
                           "vehicles.json")

    return rep


def link_sponsors(reports, tickers: dict | None = None) -> None:
    """Fill in `sponsor` and `sponsor_peers` across one run, in place.

    Two vehicles from one sponsor are one manager appearing twice, not two
    independent signals, and the report should say so where it can see it.
    """
    tickers = tickers or {}
    vehicles = [r for r in reports if r.is_vehicle]
    for i, a in enumerate(vehicles):
        peers, sponsor = [], a.sponsor
        for j, b in enumerate(vehicles):
            if i == j:
                continue
            common = shared_sponsor(a.issuer_name, b.issuer_name)
            if not common:
                continue
            sponsor = sponsor or common
            label = tickers.get(b.issuer_cik) or b.issuer_name
            if label:
                peers.append(label)
        a.sponsor = sponsor
        a.sponsor_peers = tuple(sorted(set(peers)))
