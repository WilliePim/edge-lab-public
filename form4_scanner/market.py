"""Market-data adapter.

Deliberately thin and swappable. yfinance is the default because it is free and
needs no key, but it is scraped data -- treat analyst counts and balance-sheet
fields as indicative, not authoritative. Swap in your existing data source by
implementing the same three methods.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

log = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    ticker: str
    market_cap: float | None = None
    price: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    drawdown_pct: float | None = None      # from 52w high, positive number
    off_low_pct: float | None = None       # how far above the 52w low
    analyst_count: int | None = None
    total_cash: float | None = None
    total_debt: float | None = None
    free_cash_flow: float | None = None
    ok: bool = False
    #  Where these numbers came from and when. Four of them -- market_cap,
    #  drawdown_pct, analyst_count, survivability_flag -- cannot be rebuilt from
    #  EDGAR, and yfinance returns TODAY's value, never the one that was true on
    #  a past run date. Without provenance a silent change of definition upstream
    #  would move the archive and leave nothing to notice it by. Stamped at fetch
    #  time rather than by the caller, because only the fetch knows the moment.
    source: str = ""
    fetched_at: str = ""

    @property
    def net_cash(self) -> float | None:
        if self.total_cash is None or self.total_debt is None:
            return None
        return self.total_cash - self.total_debt

    @property
    def survivability_flag(self) -> str:
        """Veto gate. Insider conviction does not prevent a covenant breach."""
        if self.net_cash is None and self.free_cash_flow is None:
            return "unknown"
        if (self.net_cash or 0) > 0:
            return "net cash"
        if (self.free_cash_flow or 0) > 0:
            return "fcf positive"
        return "LEVERED + BURNING"


class NullMarketData:
    """Fallback that returns empty snapshots.

    With no market data every cap is None, so the market-cap band gate lets the
    issuer through (scan.py) and the price context in the report reads empty.
    """

    def snapshot(self, ticker: str) -> MarketSnapshot:
        return MarketSnapshot(
            ticker=ticker, ok=False, source="none",
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))


class YFinanceMarketData:
    def __init__(self):
        import yfinance  # noqa: F401  (fail loudly at construction, not mid-scan)

        self._yf = yfinance
        self._cache: dict[str, MarketSnapshot] = {}

    def snapshot(self, ticker: str) -> MarketSnapshot:
        if not ticker:
            return MarketSnapshot(ticker="", ok=False)
        if ticker in self._cache:
            return self._cache[ticker]

        snap = MarketSnapshot(
            ticker=ticker, source="yfinance",
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        try:
            tk = self._yf.Ticker(ticker)
            info = tk.info or {}

            snap.market_cap = info.get("marketCap")
            snap.price = info.get("currentPrice") or info.get("regularMarketPrice")
            snap.high_52w = info.get("fiftyTwoWeekHigh")
            snap.low_52w = info.get("fiftyTwoWeekLow")
            snap.analyst_count = info.get("numberOfAnalystOpinions")
            snap.total_cash = info.get("totalCash")
            snap.total_debt = info.get("totalDebt")
            snap.free_cash_flow = info.get("freeCashflow")

            if snap.price and snap.high_52w and snap.high_52w > 0:
                snap.drawdown_pct = round(
                    100.0 * (snap.high_52w - snap.price) / snap.high_52w, 1
                )
            if snap.price and snap.low_52w and snap.low_52w > 0:
                snap.off_low_pct = round(
                    100.0 * (snap.price - snap.low_52w) / snap.low_52w, 1
                )
            snap.ok = snap.price is not None
        except Exception as e:  # yfinance throws a wide variety of things
            log.warning("market data failed for %s: %s", ticker, e)

        self._cache[ticker] = snap
        return snap


def get_provider(kind: str = "yfinance"):
    if kind == "none":
        return NullMarketData()
    try:
        return YFinanceMarketData()
    except ImportError:
        log.warning("yfinance not installed -- running without market data. "
                    "pip install yfinance to enable the market-cap band gate "
                    "and the price context in the report.")
        return NullMarketData()
