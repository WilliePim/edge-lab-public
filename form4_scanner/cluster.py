"""Group buys by issuer and detect insider clusters."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from .parse import Transaction


@dataclass
class IssuerCluster:
    issuer_cik: str
    issuer_name: str
    ticker: str
    txns: list[Transaction] = field(default_factory=list)

    @property
    def economic_txns(self) -> list[Transaction]:
        """One Transaction per underlying trade, co-filers collapsed.

        A joint filing emits one Transaction per (row x reporting owner), which
        is right for attribution and wrong for every total. Observed live: four
        affiliated Forbion vehicles on one accession turned $64.8M of buying
        into $259.2M. Dedupe on (accession, txn_index) before summing anything.
        """
        seen: dict[tuple, Transaction] = {}
        for t in self.txns:
            seen.setdefault((t.accession, t.txn_index), t)
        return list(seen.values())

    @property
    def buyer_groups(self) -> list[set[str]]:
        """Owner CIKs merged into one group per independent buying decision.

        Owners who co-file are one decision, not several: a fund's management
        company, its GP and its two feeders sign the same Form 4 for the same
        trade. Owners are merged transitively, so an insider who files alone on
        one accession and jointly on another still counts once.
        """
        parent: dict[str, str] = {}

        def find(x: str) -> str:
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        by_accession: dict[str, list[str]] = defaultdict(list)
        for t in self.txns:
            find(t.owner_cik)
            by_accession[t.accession].append(t.owner_cik)
        for co_filers in by_accession.values():
            for other in co_filers[1:]:
                union(co_filers[0], other)

        groups: dict[str, set[str]] = defaultdict(set)
        for cik in list(parent):        # find() writes to parent; don't iterate it live
            groups[find(cik)].add(cik)
        return list(groups.values())

    @property
    def distinct_buyers(self) -> int:
        return len(self.buyer_groups)

    @property
    def uniform_price(self) -> float | None:
        """The single price every buyer paid, if there is one.

        Open-market executions land on different prints; an offering fills
        everyone at the deal price. Two or more independent buyers paying the
        identical price to the cent is the tell that this is an allocation.
        """
        econ = [t for t in self.economic_txns if t.price > 0]
        if len(econ) < 2 or self.distinct_buyers < 2:
            return None
        prices = {t.price for t in econ}
        return prices.pop() if len(prices) == 1 else None

    @property
    def total_value(self) -> float:
        return round(sum(t.value for t in self.economic_txns), 2)

    @property
    def first_date(self) -> date | None:
        ds = [t.txn_date for t in self.txns if t.txn_date]
        return min(ds) if ds else None

    @property
    def last_date(self) -> date | None:
        ds = [t.txn_date for t in self.txns if t.txn_date]
        return max(ds) if ds else None

    @property
    def roles(self) -> set[str]:
        return {t.role for t in self.txns}

    def max_window_buyers(self, window_days: int = 30) -> int:
        """Largest number of distinct buyers falling inside any `window_days` span.

        A cluster is only meaningful if the buys are close together -- four
        insiders spread over nine months is not agreement, it is a calendar.
        Counts buyer *groups*, so co-filing affiliates of one fund cannot
        manufacture a cluster on their own.
        """
        group_of = {cik: i for i, g in enumerate(self.buyer_groups) for cik in g}
        dated = sorted(
            [t for t in self.txns if t.txn_date], key=lambda t: t.txn_date
        )
        best = 0
        for i, anchor in enumerate(dated):
            cutoff = anchor.txn_date + timedelta(days=window_days)
            owners = {
                group_of[t.owner_cik] for t in dated[i:] if t.txn_date <= cutoff
            }
            best = max(best, len(owners))
        return best

    def largest_by_value(self) -> Transaction | None:
        return max(self.txns, key=lambda t: t.value) if self.txns else None


def group_by_issuer(txns: list[Transaction]) -> list[IssuerCluster]:
    buckets: dict[str, IssuerCluster] = {}
    for t in txns:
        c = buckets.get(t.issuer_cik)
        if c is None:
            c = IssuerCluster(t.issuer_cik, t.issuer_name, t.ticker)
            buckets[t.issuer_cik] = c
        if not c.ticker and t.ticker:
            c.ticker = t.ticker
        c.txns.append(t)
    return sorted(buckets.values(), key=lambda c: -c.total_value)


def holdings_increase_pct(t: Transaction) -> float | None:
    """Purchase as a % of the insider's pre-existing position.

    >25% means the insider changed the size of their bet rather than topping it up.
    Returns None when the filing omits post-transaction holdings.
    """
    if not t.shares_after or t.shares_after <= 0 or t.shares <= 0:
        return None
    before = t.shares_after - t.shares
    if before <= 0:
        return float("inf")  # new position from zero
    return round(100.0 * t.shares / before, 1)
