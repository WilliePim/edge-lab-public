"""Run-to-run deltas, with the reason a name left stated rather than implied.

A rolling window drops names for reasons that look identical in the output and
mean opposite things. A name whose purchase simply fell out the back of the
window has not deteriorated -- nothing about it changed except the date. A name
whose score_v3 fell from 3 to 1 did deteriorate. Both vanish from the report in
exactly the same way, and reading the second meaning into the first is the error
this module exists to prevent.

So the departure reasons are separated:

    AGED-OUT     the last purchase now predates the window. Expiry, not decay.
    GATED        pruned before scoring -- cap band, or the dilution veto.
    DROPPED      absent, and the previous file cannot say which of the above.

There is no "below the gate" departure any more: score_v3 has no pass mark, so a
name cannot fall under one. A CSV written before the prune carries the 12-point
`score` column instead of `score_v3`; the two are different scales and are not
compared -- those names report as unchanged, with the reason stated.

That last one matters. A CSV written before this module existed has no
`last_buy_date` column, and without it aged-out is not determinable. The honest
answer is to say so per file, once, rather than to quietly classify every
absence as deterioration.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

log = logging.getLogger(__name__)

NEW = "NEW"
AGED_OUT = "AGED-OUT"
GATED = "GATED"
DROPPED = "DROPPED"
SCORE_UP = "SCORE UP"
SCORE_DOWN = "SCORE DOWN"
UNCHANGED = "UNCHANGED"

#  Departures, in the order the report should read them: the ones that mean
#  something first, the ones that mean "the calendar moved" last.
DEPARTURES = (GATED, DROPPED, AGED_OUT)

LAST_BUY_COLUMN = "last_buy_date"


@dataclass(frozen=True, slots=True)
class Delta:
    kind: str
    ticker: str
    issuer_cik: str
    issuer_name: str = ""
    prev_score: int | None = None
    new_score: int | None = None
    detail: str = ""

    def __str__(self) -> str:
        scores = ""
        if self.prev_score is not None and self.new_score is not None:
            scores = f" {self.prev_score} -> {self.new_score}"
        elif self.new_score is not None:
            scores = f" {self.new_score}"
        elif self.prev_score is not None:
            scores = f" was {self.prev_score}"
        tail = f"  ({self.detail})" if self.detail else ""
        return f"{self.kind:<11} {self.ticker or '?':<8}{scores}{tail}"


def _d(raw) -> date | None:
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _norm(cik) -> str:
    return str(cik).strip().lstrip("0") or str(cik).strip()


def load_previous(path: str | Path) -> tuple:
    """({cik: row}, has_last_buy_date). Missing file is not fatal."""
    p = Path(path)
    if not p.exists():
        log.warning("%s not found -- no comparison", p)
        return {}, False
    with open(p, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fields = reader.fieldnames or []
    return ({_norm(r.get("cik", "")): r for r in rows},
            LAST_BUY_COLUMN in fields)


def _punteggio(card) -> int:
    """score_v3 della carta. Una carta senza `v3` non e' stata scorata: 0."""
    return (getattr(card, "v3", None) or {}).get("score") or 0


def _punteggio_precedente(prev: dict) -> tuple[int | None, str]:
    """(punteggio nella riga vecchia, motivo se non c'e'). Un CSV scritto prima della
    potatura porta `score` su 12 punti: scala diversa, non si confronta."""
    grezzo = prev.get("score_v3", "")
    if grezzo not in (None, ""):
        try:
            return int(grezzo), ""
        except (TypeError, ValueError):
            return None, ""
    if prev.get("score", "") not in (None, ""):
        return None, "il file precedente ha il punteggio su 12: scale diverse, non confrontabili"
    return None, ""


def compare(previous: dict, cards, window_start: date,
            has_last_buy: bool = True) -> list:
    """Classify every name that entered, left or moved between two runs.

    `cards` is the FULL list, vetoed names included: the difference between "was
    vetoed this run" and "never reached scoring" is exactly what makes the report
    readable.
    """
    #  Normalise BOTH sides. load_previous already does it, but a caller
    #  building the dict another way would otherwise get every name reported
    #  twice -- once as NEW under the bare CIK, once as departed under the
    #  padded one. Relying on the caller for a key normalisation is how a join
    #  silently half-works.
    previous = {_norm(k): v for k, v in previous.items()}
    by_cik = {_norm(c.issuer_cik): c for c in cards}
    presenti = {k: c for k, c in by_cik.items() if not c.blocked}

    out: list = []

    for cik, card in presenti.items():
        ora = _punteggio(card)
        prev = previous.get(cik)
        if prev is None:
            out.append(Delta(NEW, card.ticker, cik, card.issuer_name,
                             new_score=ora))
            continue
        was, motivo = _punteggio_precedente(prev)
        if was is None or was == ora:
            out.append(Delta(UNCHANGED, card.ticker, cik, card.issuer_name,
                             was, ora, motivo))
        else:
            kind = SCORE_UP if ora > was else SCORE_DOWN
            out.append(Delta(kind, card.ticker, cik, card.issuer_name, was, ora))

    for cik, prev in previous.items():
        if cik in presenti:
            continue
        ticker = prev.get("ticker", "")
        name = prev.get("issuer", "")
        was, _motivo = _punteggio_precedente(prev)

        card = by_cik.get(cik)
        if card is not None:
            #  Ancora dentro la finestra, ma questo giro il veto diluizione lo
            #  ferma prima del punteggio. E' il caso che AGED-OUT non deve mai
            #  assorbire: qui e' successo qualcosa, li' e' passato il calendario.
            out.append(Delta(GATED, ticker or card.ticker, cik,
                             name or card.issuer_name, was, None,
                             "veto diluizione in questo giro"))
            continue

        if not has_last_buy:
            out.append(Delta(DROPPED, ticker, cik, name, was, None,
                             "previous file has no last_buy_date; "
                             "aged-out not determinable"))
            continue

        last_buy = _d(prev.get(LAST_BUY_COLUMN, ""))
        if last_buy is not None and last_buy < window_start:
            #  Nothing about this issuer changed. The window moved past it.
            days = (window_start - last_buy).days
            out.append(Delta(AGED_OUT, ticker, cik, name, was, None,
                             f"last buy {last_buy}, {days}d before the window "
                             f"opened on {window_start}"))
        else:
            out.append(Delta(GATED, ticker, cik, name, was, None,
                             "still inside the window but pruned before "
                             "scoring -- cap band or dilution veto"))
    return out


def render(deltas: list, previous_path: str = "",
           has_last_buy: bool = True) -> str:
    """The delta section of the report."""
    if not deltas:
        return ""

    lines = [f"\n  changes vs {previous_path or 'previous run'}"]
    if not has_last_buy:
        lines.append("    ! the previous file predates the last_buy_date "
                     "column, so AGED-OUT cannot be told apart from")
        lines.append("      other departures; absences are reported as DROPPED")

    by_kind: dict = {}
    for d in deltas:
        by_kind.setdefault(d.kind, []).append(d)

    order = [NEW, SCORE_UP, SCORE_DOWN] + list(DEPARTURES)
    for kind in order:
        group = by_kind.get(kind)
        if not group:
            continue
        lines.append("")
        for d in sorted(group, key=lambda x: (-(x.new_score or x.prev_score or 0),
                                              x.ticker)):
            lines.append(f"    {d}")

    unchanged = len(by_kind.get(UNCHANGED, []))
    if unchanged:
        lines.append("")
        lines.append(f"    {unchanged} name(s) unchanged")

    aged = len(by_kind.get(AGED_OUT, []))
    if aged:
        lines.append("")
        lines.append(f"    {aged} name(s) aged out: their buys left the window, "
                     f"nothing about them got worse")
    return "\n".join(lines)
