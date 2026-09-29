"""Breadth Phase 1, live: the weekly raw counts, captured as the scan walks past.

Phase 1 froze four weeks of hand-verified counts from the SEC bulk quarterly
datasets. This is the same measure on the live path, and it exists because
`scan.py` already parses every Form 4 in the window and then throws the counts
away -- the numbers are free, they were simply never kept.

RAW COUNTS ONLY. No percentage, no deseasonalising, no z-score. Those get
computed by hand, outside this codebase, and Phase 2 is written against those
values. A measure verified against the code that produced it is not verified.

WHY THE WEEKS ARE KEYED ON TWO DIFFERENT DATE FIELDS, deliberately, exactly as
the bulk path does it:

  numerator   -- distinct issuers with a qualifying open-market buy, keyed on
                 the TRANSACTION date: when insiders actually bought.
  denominator -- distinct issuers that filed any Form 4, keyed on the FILING
                 date: how many issuers were active in the reporting process.

ONE DIVERGENCE FROM THE BULK DEFINITION, stated because it is invisible in the
output. The bulk denominator counts issuers with a SUBMISSION row of type "4".
Here the issuer CIK is read off the parsed transactions, so an issuer whose Form
4 carries no transaction row at all -- rare, but it exists -- is not counted.
Derivative and disposal rows DO count, since `parse_ownership_xml` returns them
and only `open_market_buys` filters them out, so the gap is narrow. It is not
zero, and the two series must not be spliced without measuring it.

WHY EVERY RUN RE-OBSERVES EVERY WEEK. Form 4 has a two-business-day deadline and
late filings happen, so the numerator of a week keeps growing for days after the
week closes. The most recent week of a live series is ALWAYS incomplete. Rather
than rewrite history, each run appends its own observation of every week in its
window, stamped with the run date. A later observation of the same week
supersedes an earlier one; nothing is ever edited or deleted, so the record of
how the count grew is itself preserved.

That is also why the emission window is a ceiling. A week stops being re-observed
once it falls out the back of the window, and whatever count it had at that
moment is final.

DIVERGENCE FROM THE BULK PATH, recorded rather than papered over, because it
would surface as a discontinuity exactly where the live series is spliced onto
the backfilled one -- which is the artefact that reads as a signal:

  the bulk tables are normalised, one row per transaction. The XML path emits one
  Transaction per (row x reporting owner), so a naive count multiplies by the
  number of co-filers. Both counts are kept here, `txns_economic` and `txns_rows`,
  so the splice can be measured instead of assumed.
"""
from __future__ import annotations

import json
import os
import statistics
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION = 1


def week_start(d: date) -> date:
    """The Monday of the week containing `d`."""
    return d - timedelta(days=d.weekday())


@dataclass(frozen=True)
class WeekCount:
    """One week, as seen by one run. Counts only."""

    week_start: str
    issuers_filing: int            # denominator, by FILING date
    issuers_buying: int            # numerator, by TRANSACTION date
    filings: int                   # distinct accessions filed
    txns_economic: int             # co-filers collapsed
    txns_rows: int                 # row x reporting owner, the naive count
    median_buy_usd: float | None
    total_buy_usd: float


@dataclass
class BreadthTally:
    """Accumulates while `collect_buys` walks the window. Mutable by design."""

    min_value: float
    #  Sets, not counters: an issuer filing three Form 4s in a week is one issuer.
    _filing: dict = field(default_factory=dict)
    _buying: dict = field(default_factory=dict)
    _accessions: dict = field(default_factory=dict)
    #  week -> {(accession, txn_index): value}. Keyed on the economic identity so
    #  the value of a joint filing is stored once no matter how many co-filers
    #  reported it, and the median is a median of trades rather than of rows.
    _econ: dict = field(default_factory=dict)
    _rows: dict = field(default_factory=dict)

    def observe(self, filed_on: date, txns: list, buys: list) -> None:
        """One filing day: everything parsed, and the subset that qualified.

        `txns` is every transaction in every Form 4 filed that day, including
        sales, derivatives and plan buys -- the denominator must count issuers
        that filed, not issuers that bought.
        """
        fw = week_start(filed_on).isoformat()
        self._filing.setdefault(fw, set()).update(t.issuer_cik for t in txns)
        self._accessions.setdefault(fw, set()).update(t.accession for t in txns)

        for t in buys:
            #  Keyed on the transaction date, which is why a buy filed today can
            #  land in a week already written by an earlier run.
            if t.txn_date is None:
                continue
            tw = week_start(t.txn_date).isoformat()
            self._buying.setdefault(tw, set()).add(t.issuer_cik)
            self._econ.setdefault(tw, {}).setdefault(
                (t.accession, t.txn_index), t.value)
            self._rows[tw] = self._rows.get(tw, 0) + 1

    def weeks(self) -> list[WeekCount]:
        out = []
        for wk in sorted(set(self._filing) | set(self._buying)):
            #  Economic values only: summing the row-level values would multiply
            #  a joint filing by its number of co-filers. Observed live at
            #  $64.8M turning into $259.2M -- see cluster.economic_txns.
            econ = self._econ.get(wk, {})
            econ_vals = list(econ.values())
            out.append(WeekCount(
                week_start=wk,
                issuers_filing=len(self._filing.get(wk, ())),
                issuers_buying=len(self._buying.get(wk, ())),
                filings=len(self._accessions.get(wk, ())),
                txns_economic=len(econ),
                txns_rows=self._rows.get(wk, 0),
                median_buy_usd=(statistics.median(econ_vals) if econ_vals else None),
                total_buy_usd=sum(econ_vals),
            ))
        return out


def write_weeks(tally: BreadthTally, state_dir, run_date: date,
                window_days: int, scanner_sha: str = "",
                start: date | None = None, end: date | None = None) -> Path:
    """Append this run's observation of every week in its window.

    Append-only. No TTL, no dedup, no archiving: a week observed twice is two
    rows, and that is the point -- the pair shows how much the count grew after
    the week closed.
    """
    d = Path(state_dir) / "breadth" / "form4"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{run_date.isoformat()}.jsonl"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    current = week_start(run_date).isoformat()
    #  A late filing drags its transaction's week into the output even when that
    #  week sits far outside the scan window -- a buy dated 2025-12-01 arrived in
    #  a run covering three days of August 2026. Such a row has a numerator and
    #  no denominator, and a reader computing a ratio would divide by zero, or
    #  worse, get a number. The week was not observed; it was grazed.
    #
    #  So every row says whether its week was actually inside the window on both
    #  date axes. Only those can carry a rate. The rest are still worth keeping:
    #  they are the record of how late Form 4s actually arrive, which is the
    #  quantity that decides how wide the window has to be.
    lo = start.isoformat() if start else None
    hi = end.isoformat() if end else None
    lines = []
    for w in tally.weeks():
        row = {
            "kind": "week",
            "schema_version": SCHEMA_VERSION,
            "run_date": run_date.isoformat(),
            "observed_at": now,
            "window_days": window_days,
            "min_value": tally.min_value,
            "scanner_git_sha": scanner_sha,
            #  Says out loud that this week is still moving. The current week is
            #  never final, and a reader who forgets that reads the missing late
            #  filings as a collapse in insider buying.
            "week_complete": w.week_start != current,
            "window_start": lo,
            "window_end": hi,
            #  True only if the whole Monday-to-Sunday week fell inside the
            #  scanned window. False means: do NOT compute a rate from this row.
            "week_in_window": bool(
                lo and hi and w.week_start >= lo
                and (date.fromisoformat(w.week_start)
                     + timedelta(days=6)).isoformat() <= hi),
        }
        row.update(asdict(w))
        lines.append(json.dumps(row, sort_keys=True))

    #  Atomic: a half-written line would corrupt a file nothing ever rewrites.
    tmp = path.with_suffix(".jsonl.tmp")
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    tmp.write_text(existing + "".join(ln + "\n" for ln in lines), encoding="utf-8")
    os.replace(tmp, path)
    return path
