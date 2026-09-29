"""Tests for run-to-run deltas.

The case that matters is the one that prompted this module: PRQR left the
2026-08-22 scan because its purchase fell out the back of a rolling 30-day
window. Nothing about the company changed. Reported as a plain absence it reads
identically to a name whose score collapsed, and that is the reading this must
make impossible.
"""
import csv
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness import check, report

from form4_scanner.compare import (AGED_OUT, DROPPED, GATED, NEW, SCORE_DOWN,
                                   SCORE_UP, UNCHANGED, compare, load_previous,
                                   render)
from form4_scanner.flags import Card as CartaVera


class _Veto:
    """Il minimo che `Card.blocked` legge: un rapporto di diluizione bloccante."""

    blocked = True


def Card(ticker, cik, score, blocked=False, name=""):
    """La Card VERA del pacchetto, non un sosia.

    Il test precedente definiva una classe con un attributo `.score` che `flags.Card`
    non ha piu' dalla potatura v3: la suite restava verde mentre `--compare` andava in
    errore a ogni uso (AttributeError). Si costruisce quella vera, e il punteggio sta
    dove sta in produzione, cioe' in `v3`.
    """
    return CartaVera(ticker=ticker, issuer_name=name or ticker, issuer_cik=cik,
                     v3={"score": score}, dilution=_Veto() if blocked else None)


def prev_row(ticker, cik, score, last_buy=""):
    return {"ticker": ticker, "cik": cik, "issuer": ticker,
            "score_v3": str(score), "last_buy_date": last_buy}


def kinds(deltas):
    return {d.ticker: d.kind for d in deltas}


WINDOW_START = date(2026, 7, 23)

# --------------------------------------------------------------------------
print("[compare] THE case: a buy that fell out of the window is not a worse score")
previous = {
    "111": prev_row("PRQR", "111", 2, "2026-07-20"),   # 3 days before the window
    "222": prev_row("SMRT", "222", 2, "2026-08-10"),
}
cards = [Card("SMRT", "222", 3)]
d = compare(previous, cards, WINDOW_START)
k = kinds(d)
check("PRQR is AGED-OUT, not a departure with an implied verdict",
      k.get("PRQR") == AGED_OUT, str(k))
check("SMRT is judged on its score", k.get("SMRT") == SCORE_UP, str(k))

prqr = next(x for x in d if x.ticker == "PRQR")
check("the aged-out row states the buy date", "2026-07-20" in prqr.detail,
      prqr.detail)
check("the aged-out row states the distance from the window",
      "3d before the window" in prqr.detail, prqr.detail)
check("the aged-out row carries no new score", prqr.new_score is None,
      str(prqr.new_score))
check("...but remembers what it scored", prqr.prev_score == 2,
      str(prqr.prev_score))

print("[compare] a buy still inside the window is NOT aged out")
previous = {"111": prev_row("AAA", "111", 7, "2026-08-01")}
d = compare(previous, [], WINDOW_START)
check("still-in-window absence is GATED, not AGED-OUT",
      kinds(d).get("AAA") == GATED, str(kinds(d)))
check("...and says what that means",
      "pruned before scoring" in d[0].detail, d[0].detail)

print("[compare] deterioration is called deterioration")
previous = {"111": prev_row("BBB", "111", 3, "2026-08-01")}
d = compare(previous, [Card("BBB", "111", 1)], WINDOW_START)
b = d[0]
#  Non esiste piu' una soglia da cui cadere: score_v3 e' un ordinamento. Quel che
#  resta e' il verso del movimento, e non va confuso con l'uscita dalla finestra.
check("a falling score is SCORE DOWN", b.kind == SCORE_DOWN, b.kind)
check("...with both scores shown", (b.prev_score, b.new_score) == (3, 1),
      str((b.prev_score, b.new_score)))
check("SCORE DOWN is not AGED-OUT even though the name left the CSV",
      b.kind != AGED_OUT)

print("[compare] entries, moves and holds")
previous = {
    "1": prev_row("UP", "1", 1, "2026-08-01"),
    "2": prev_row("DOWN", "2", 3, "2026-08-01"),
    "3": prev_row("SAME", "3", 2, "2026-08-01"),
}
cards = [Card("UP", "1", 3), Card("DOWN", "2", 1), Card("SAME", "3", 2),
         Card("FRESH", "4", 2)]
k = kinds(compare(previous, cards, WINDOW_START))
check("a rising score is SCORE UP", k.get("UP") == SCORE_UP, str(k))
check("a falling score is SCORE DOWN", k.get("DOWN") == SCORE_DOWN, str(k))
check("an unchanged score is UNCHANGED", k.get("SAME") == UNCHANGED, str(k))
check("a name absent from the previous run is NEW", k.get("FRESH") == NEW,
      str(k))

print("[compare] a dilution-vetoed name does not count as present (veto acceso esplicitamente)")
#  Il veto e' spento per default (dilution.veto_attivo): il comportamento storico si prova accendendolo.
os.environ["EDGE_LAB_DILUTION_VETO"] = "1"
previous = {"1": prev_row("VETO", "1", 3, "2026-08-01")}
d = compare(previous, [Card("VETO", "1", 3, blocked=True)], WINDOW_START)
check("a blocked card is treated as departed, not as unchanged",
      d[0].kind == GATED, d[0].kind)
check("...and the report says the veto is what happened",
      "veto diluizione" in d[0].detail, d[0].detail)
del os.environ["EDGE_LAB_DILUTION_VETO"]
d = compare(previous, [Card("VETO", "1", 3, blocked=True)], WINDOW_START)
check("veto spento (default): lo stesso nome resta presente, non GATED",
      d[0].kind == UNCHANGED, d[0].kind)

print("[compare] a CSV from before the prune is not compared on a different scale")
vecchio = {"1": {"ticker": "OLD", "cik": "1", "issuer": "OLD", "score": "8",
                 "last_buy_date": "2026-08-01"}}
d = compare(vecchio, [Card("OLD", "1", 2)], WINDOW_START)
check("a 12-point score is not read as a v3 score", d[0].kind == UNCHANGED,
      d[0].kind)
check("...and the reason is stated", "scale diverse" in d[0].detail, d[0].detail)

print("[compare] CIK matching survives zero padding")
previous = {"0000001234": prev_row("PAD", "0000001234", 1, "2026-08-01")}
d = compare(previous, [Card("PAD", "1234", 3)], WINDOW_START)
check("a zero-padded CIK matches a bare one", d[0].kind == SCORE_UP,
      str(kinds(d)))
check("...and is not reported as both NEW and departed", len(d) == 1, str(d))

print("[compare] an old CSV without the column says so instead of guessing")
previous = {"1": {"ticker": "OLD", "cik": "1", "issuer": "OLD", "score_v3": "2"}}
d = compare(previous, [], WINDOW_START, has_last_buy=False)
check("without last_buy_date the absence is DROPPED, never AGED-OUT",
      d[0].kind == DROPPED, d[0].kind)
check("...and the reason is stated",
      "not determinable" in d[0].detail, d[0].detail)
out = render(d, "old.csv", has_last_buy=False)
check("the report warns once, at the top",
      "predates the last_buy_date column" in out, out)
#  The warning names the label in order to say it is unavailable, so the check
#  is that no delta ROW is labelled AGED-OUT -- not that the string is absent.
check("no row is labelled AGED-OUT when it cannot be determined",
      not any(x.kind == AGED_OUT for x in d), str(kinds(d)))

print("[compare] rendering")
previous = {
    "1": prev_row("PRQR", "1", 2, "2026-07-20"),
    "2": prev_row("HOLD", "2", 2, "2026-08-01"),
}
d = compare(previous, [Card("HOLD", "2", 2), Card("NEWCO", "3", 3)],
            WINDOW_START)
out = render(d, "scan_prev.csv")
check("the report names the file compared against", "scan_prev.csv" in out, out)
check("AGED-OUT appears as its own label", AGED_OUT in out, out)
check("NEW appears", "NEW" in out, out)
check("unchanged names are counted, not listed", "1 name(s) unchanged" in out,
      out)
check("the aged-out summary spells out the meaning",
      "nothing about them got worse" in out, out)
check("an empty delta list renders nothing", render([]) == "")

print("[compare] load_previous")
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "prev.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["score_v3", "ticker", "issuer", "cik", "last_buy_date"])
        w.writerow([2, "AAA", "Alpha", "0000000123", "2026-08-01"])
    rows, has = load_previous(p)
    check("the file is read", len(rows) == 1, str(rows))
    check("the column is detected", has is True, str(has))
    check("the CIK is normalised on load", "123" in rows, str(list(rows)))

    rows, has = load_previous(Path(tmp) / "nope.csv")
    check("a missing file is not fatal", rows == {} and has is False,
          str((rows, has)))

    p2 = Path(tmp) / "old.csv"
    with open(p2, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["score", "ticker", "issuer", "cik"])
        w.writerow([7, "AAA", "Alpha", "123"])
    _, has = load_previous(p2)
    check("a CSV without the column is detected as such", has is False, str(has))

print("[compare] the real PRQR case, from the two committed scans")
real_prev = Path(__file__).resolve().parents[1] / "scan_30d_20260818.csv"
if real_prev.exists():
    rows, has = load_previous(real_prev)
    check("the 18 Aug scan loads", len(rows) > 20, str(len(rows)))
    check("...and predates the column, so it is honest about it", has is False,
          str(has))
    prqr = [r for r in rows.values() if r.get("ticker") == "PRQR"]
    check("PRQR is in the 18 Aug scan", len(prqr) == 1, str(len(prqr)))
    d = compare(rows, [], date(2026, 7, 23), has_last_buy=has)
    check("without the column even the real case degrades to DROPPED",
          all(x.kind == DROPPED for x in d), str({x.kind for x in d}))
else:
    check("historical scan present (gitignored, skipped if absent)", True)

if __name__ == "__main__":
    sys.exit(report("ALL COMPARE TESTS PASSED"))
