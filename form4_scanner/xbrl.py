"""Balance-sheet arithmetic: the quantities that are not a matter of strategy.

Net debt is debt minus cash. EBITDA is operating income plus depreciation.
Leverage is one over the other. Those are arithmetic, and there is exactly one
right answer -- so they live in one place, below whoever asks for them.

Today the askers are the measurement tools (tools/backfill_gates.py,
tools/sign_gates_count.py), not the live pipeline: the two sign gates built on
these numbers are still being measured and do not block anything
(RULES.md, "misurati, NON in pipeline"). The layer stays here rather than inside
a tool because two copies of `net_debt / EBITDA` that drift apart would keep
returning confident numbers while disagreeing, and nothing would fail.

Everything here is pure: floats and None in, a Metric out. No client, no I/O, no
configuration. The rules that ARE strategy -- which tax rate to impute, which
window to measure over, where a floor sits -- stay with whoever decided them.

Every function names its unit, and that is a standing rule paid for once: "the
maximum of the range" was answered in EV/EBIT units to a guard working in return
units, which would have read 14.2 where it expected 0.142. A multiple and a
return are both `float` and the type system cannot tell them apart -- so `Metric`
carries the unit as data.
"""

from __future__ import annotations

from dataclasses import dataclass


# Units. Not decoration -- see the module docstring.
RATIO = "ratio"        # a pure ratio expressed as a decimal: 0.0701 is 7.01%
MULTIPLE = "multiple"  # a valuation or leverage multiple: 2.63 is 2.63x
RATE = "rate"          # a compound annual rate as a decimal
USD = "usd"


@dataclass(frozen=True, slots=True)
class Metric:
    """A number that knows what it is, or an explained absence.

    `value is None` is a real answer, not a failure to produce one. `flags`
    carries what the diagnostics must count; `reason` says why an absence
    happened, so the report can explain rather than shrug.
    """

    value: float | None
    unit: str
    flags: tuple = ()
    reason: str = ""

    @property
    def present(self) -> bool:
        return self.value is not None

    def with_flags(self, *extra: str) -> "Metric":
        return Metric(self.value, self.unit, tuple(self.flags) + extra,
                      self.reason)

    def __str__(self) -> str:
        if self.value is None:
            return f"None ({self.reason or 'no reason recorded'})"
        if self.unit == MULTIPLE:
            return f"{self.value:.4g}x"
        if self.unit in (RATIO, RATE):
            return f"{self.value * 100:.2f}%"
        return f"{self.value:,.0f}"


def _absent(unit: str, reason: str, *flags: str) -> Metric:
    return Metric(None, unit, tuple(flags) or ("missing_input",), reason)


def _have(*vals) -> bool:
    """True when every input is present. Checked BEFORE any arithmetic."""
    return all(v is not None for v in vals)


def net_debt(lt_debt: float | None, st_debt: float | None,
             cash: float | None, *, balance_sheet_read: bool = False) -> Metric:
    """Net debt in USD: `lt_debt + st_debt - cash`.

    D-002/I5: an absent debt component is assumed zero **only** where the year
    shows the balance sheet was actually parsed (total assets or equity
    present). Otherwise the absence is unknown, not zero. A company reporting no
    short-term borrowings genuinely has none; a company whose balance sheet we
    failed to read tells us nothing, and the two must not produce one number.
    """
    flags: list = []
    lt, st = lt_debt, st_debt

    for name, val in (("lt_debt", lt_debt), ("st_debt", st_debt)):
        if val is None:
            if not balance_sheet_read:
                return _absent(USD, f"{name} absent and no balance-sheet "
                                    f"evidence for the year")
            flags.append(f"assumed_zero:{name}")

    lt = 0.0 if lt is None else lt
    st = 0.0 if st is None else st
    if not _have(cash):
        return _absent(USD, "cash absent")
    return Metric(lt + st - cash, USD, tuple(flags))


def ebitda(ebit: float | None, da: float | None) -> Metric:
    """EBITDA in USD: `operating income + D&A`.

    D-014: a D&A assembled from components is admitted and flagged, not
    refused. A composed sum is real data; the caller passes the Phase 1 note
    through so the report can say so.
    """
    if not _have(ebit, da):
        return _absent(USD, "operating income or D&A absent")
    return Metric(ebit + da, USD)


def leverage(net_debt_: Metric | float | None,
             ebitda_: Metric | float | None) -> Metric:
    """Net debt / EBITDA, as a MULTIPLE.

    D-015: a non-positive EBITDA refuses the ratio rather than returning a number
    that reads as leverage. What to conclude from "no EBITDA and net debt" is the
    caller's decision, not this function's.
    """
    nd = net_debt_.value if isinstance(net_debt_, Metric) else net_debt_
    eb = ebitda_.value if isinstance(ebitda_, Metric) else ebitda_
    if not _have(nd, eb):
        return _absent(MULTIPLE, "net debt or EBITDA absent")
    if eb <= 0:
        return Metric(None, MULTIPLE, ("ebit_negative",),
                      "EBITDA is not positive; the ratio would invert sign")
    return Metric(nd / eb, MULTIPLE)


