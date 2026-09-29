"""Two sign predicates, counted on the live population. A measuring tool.

PREDICATES, NOT VALIDATED. Neither predicate runs in
the scanner's pipeline and neither has been validated: the historical replay in
tools/backfill_gates.py is descriptive (no pre-registration, no matched
control). Every name gets equity, leverage, equity/EV and the no-EBITDA state
reported, the names that pass included.

  NO_EBITDA_WITH_NET_DEBT   net debt > 0 and EBITDA <= 0.        would block
                            A sign test: positive debt with nothing to service
                            it from.

  NEGATIVE_EQUITY_LEVERED   equity < 0 AND net_debt/EBITDA > 4.0.  advisory
                            Computed and printed -- a reader has to be able to
                            see it on a name without it removing the name.

WHY 4.0 CAME BACK AFTER BEING REJECTED, and now qualifies an advisory rather than
a gate. It was rejected as a gate over the whole population, where the
distribution is a gradient -- median 2.47x, p75 4.98x -- so any cut fell through
the body. It was then reinstated to qualify a set already narrowed by a sign
test. Neither use has been validated.

THE DRAWDOWN COLUMN. The criterion that awarded a point for buying into
weakness was removed from score.py after the historical replay showed the point
was being handed out along a monotonically worsening gradient. The measurement
did not leave with the point: it is printed here with its band and with what
that band has historically been worth, so the depth is read together with its
record rather than as a bare percentage.

Counts and reports. Decides nothing that was not already decided.
"""
from __future__ import annotations

import csv
import logging
import statistics
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

ANNUAL_FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A"}

#  SELF-CONTAINED BY DESIGN. The v3 prune removes calibrate_leverage.py
#  and backfill_fetch.py; what this file needed from them is inlined below,
#  copied verbatim before their removal. A gate measurement that stops
#  working when the calibration scaffolding is cleared is not a measurement
#  you can run again.

INSTANT = {
    "equity":  ["StockholdersEquity",
                "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "lt_debt": ["LongTermDebtNoncurrent", "LongTermDebt",
                "DebtLongtermAndShorttermCombinedAmount"],
    "st_debt": ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings"],
    "cash":    ["CashAndCashEquivalentsAtCarryingValue",
                "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "assets":  ["Assets"],
}


DURATION = {
    "ebit": ["OperatingIncomeLoss"],
    "da":   ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"],
}


def _d(raw):
    try:
        return datetime.strptime(str(raw)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _facts(client, cik, tag, as_of):
    data = client.company_concept(cik, "us-gaap", tag)
    if not data:
        return []
    out = []
    for rows in (data.get("units") or {}).values():
        for r in rows:
            if str(r.get("form") or "").strip().upper() not in ANNUAL_FORMS:
                continue
            end, val = _d(r.get("end")), r.get("val")
            if end is None or val is None or end > as_of:
                continue
            out.append((end, _d(r.get("start")), float(val), r.get("filed")))
    return sorted(out)


def latest_instant(client, cik, concept, as_of):
    """Most recent balance-sheet value for a concept, first chain hit wins."""
    for tag in INSTANT[concept]:
        rows = [r for r in _facts(client, cik, tag, as_of) if r[1] is None]
        if rows:
            return rows[-1][2], rows[-1][0], tag
    return None, None, None


def trailing_four_quarters(client, cik, concept, as_of):
    """Sum of the four most recent QUARTERLY facts -- EBITDA is not a GAAP tag."""
    for tag in DURATION[concept]:
        rows = [r for r in _facts(client, cik, tag, as_of)
                if r[1] is not None and 60 <= (r[0] - r[1]).days <= 100]
        if len(rows) >= 4:
            last4 = rows[-4:]
            return sum(r[2] for r in last4), last4[-1][0], tag
    return None, None, None

from form4_scanner.bank import DEPOSITORY_SIC
from form4_scanner.edgar import EdgarClient
from form4_scanner.xbrl import ebitda, leverage, net_debt

INSURANCE_SIC = {"6311", "6321", "6324", "6331", "6351", "6361", "6399", "6411"}
EXCLUDED_SIC = set(DEPOSITORY_SIC) | INSURANCE_SIC

LEVERAGE_CEILING = 4.0
CAP = 2e9

#  Cash actually paid to retire stock. The mechanism that turns a profitable
#  company's equity negative without any distress: buy back more than you have
#  retained, and the balancing figure goes below zero.
BUYBACK_TAGS = ["PaymentsForRepurchaseOfCommonStock",
                "PaymentsForRepurchaseOfEquity"]


def buybacks_8q(client, cik, as_of):
    """Cash spent retiring stock over the eight most recent quarters."""
    for tag in BUYBACK_TAGS:
        rows = [r for r in _facts(client, cik, tag, as_of)
                if r[1] is not None and 60 <= (r[0] - r[1]).days <= 100]
        if rows:
            last8 = rows[-8:]
            return sum(r[2] for r in last8), len(last8), tag
    return None, 0, None


def evaluate(client, cik, mc, as_of):
    """Every metric for one issuer. No verdict yet."""
    eq, _, _ = latest_instant(client, cik, "equity", as_of)
    lt, _, _ = latest_instant(client, cik, "lt_debt", as_of)
    st, _, _ = latest_instant(client, cik, "st_debt", as_of)
    cash, _, _ = latest_instant(client, cik, "cash", as_of)
    assets, _, _ = latest_instant(client, cik, "assets", as_of)
    ebit, _, _ = trailing_four_quarters(client, cik, "ebit", as_of)
    da, _, _ = trailing_four_quarters(client, cik, "da", as_of)

    read = eq is not None or assets is not None
    nd = net_debt(lt, st, cash, balance_sheet_read=read)
    eb = ebitda(ebit, da)
    lev = leverage(nd, eb)

    debt = ((lt or 0.0) + (st or 0.0)) if (read and (lt is not None or st is not None)) else None
    ev = pct = None
    if mc is not None and debt is not None and cash is not None:
        ev = mc + debt - cash
        if ev > 0:
            pct = mc / ev

    bb, nq, _ = buybacks_8q(client, cik, as_of)
    return {"eq": eq, "nd": nd.value, "eb": eb.value, "lev": lev.value,
            "ev": ev, "eq_pct_ev": pct, "debt": debt, "cash": cash,
            "buyback_8q": bb, "buyback_quarters": nq}


def gates(m):
    """What WOULD block. One condition, not two.

    Predicate, not validated: this is a count, not a
    filter, and nothing in the scanner's pipeline calls it.
    NEGATIVE_EQUITY_LEVERED is kept as an advisory, also not validated.

    The advisory condition is still computed and still reported -- demoted, not
    deleted. A reader must be able to see it on a name without it removing that
    name.
    """
    hits = []
    if (m["nd"] is not None and m["nd"] > 0
            and m["eb"] is not None and m["eb"] <= 0):
        hits.append("NO_EBITDA_WITH_NET_DEBT")
    return hits


def advisories(m):
    """Reported beside the verdict, never acting on it."""
    out = []
    if (m["eq"] is not None and m["eq"] < 0
            and m["lev"] is not None and m["lev"] > LEVERAGE_CEILING):
        out.append("NEGATIVE_EQUITY_LEVERED")
    return out


#  Le fasce di drawdown con la loro mediana storica stavano qui, per leggere la
#  profondita' insieme a quanto e' valsa. La colonna non esiste piu' nel CSV dopo
#  la potatura; i numeri restano in reports/rubric_discrimination.md.
def fm(v, w=13):
    return f"{v / 1e6:>{w},.0f}M" if v is not None else f"{'--':>{w + 1}}"


def fx(v, w=7):
    return f"{v:>{w}.2f}x" if v is not None else f"{'--':>{w + 1}}"


def fp(v, w=7):
    return f"{v * 100:>{w}.1f}%" if v is not None else f"{'--':>{w + 1}}"


def main() -> int:
    client = EdgarClient(sys.argv[1])
    as_of = date(2026, 8, 28)
    logging.basicConfig(level=logging.ERROR)
    src = sys.argv[2] if len(sys.argv) > 2 else "out/scan_30d_full.csv"

    rows = list(csv.DictReader(open(src, encoding="utf-8")))
    print(f"popolazione: {len(rows)} emittenti scorati ({src})\n")

    recs, excluded = [], []
    for i, r in enumerate(rows, 1):
        subs = client.submissions(r["cik"]) or {}
        sic = str(subs.get("sic", "") or "").strip()
        if sic in EXCLUDED_SIC:
            excluded.append(r["ticker"])
            continue
        mc = float(r["market_cap"]) if r["market_cap"] else None
        m = evaluate(client, r["cik"], mc, as_of)
        #  Dalla potatura il CSV porta `score_v3` (quattro booleani) e non piu'
        #  `score` su 12: leggerlo con r["score"] faceva morire lo strumento con
        #  un KeyError su ogni scansione recente. La colonna del drawdown non
        #  esiste piu' affatto.
        try:
            v3 = int(r.get("score_v3") or 0)
        except ValueError:
            v3 = 0
        m.update(t=r["ticker"], cik=r["cik"], sic=sic, mc=mc, score_v3=v3)
        m["hits"] = gates(m)
        m["advisory"] = advisories(m)
        recs.append(m)
        if i % 50 == 0:
            print(f"  ...{i}/{len(rows)}", flush=True)

    n = len(recs)
    neg = [m for m in recs if m["eq"] is not None and m["eq"] < 0]
    noeb = [m for m in recs if "NO_EBITDA_WITH_NET_DEBT" in m["hits"]]
    negl = [m for m in recs if "NEGATIVE_EQUITY_LEVERED" in m["advisory"]]
    blocked = [m for m in recs if m["hits"]]
    #  Non esiste piu' una soglia di superamento, quindi non esiste una "coda
    #  futura": si guarda la popolazione sotto il tetto di capitalizzazione, che
    #  e' l'unico taglio ancora in piedi.
    sotto_tetto = [m for m in recs if m["mc"] is not None and m["mc"] <= CAP]
    bl_em = [m for m in sotto_tetto if m["hits"]]

    print("\n" + "=" * 92)
    print(f"esclusi per settore: {len(excluded)}   valutabili: {n}\n")
    print("1. LA CONGIUNZIONE")
    print(f"   equity < 0                            {len(neg):>4} su {n}")
    lev_known = [m for m in neg if m["lev"] is not None]
    print(f"   ...di cui con leva calcolabile        {len(lev_known):>4}"
          f"   (le altre hanno EBITDA <= 0)")
    print(f"   ...di cui leva > {LEVERAGE_CEILING}                  "
          f"{len(negl):>4}   <- ADVISORY NEGATIVE_EQUITY_LEVERED")
    survivors = [m for m in neg if m not in negl]
    print(f"   equity < 0 che SOPRAVVIVONO           {len(survivors):>4}")

    print("\n2. SOTTO IL TETTO DI CAPITALIZZAZIONE (2e9)")
    print(f"   emittenti                             {len(sotto_tetto):>4}")
    print(f"   bloccati in totale                    {len(bl_em):>4}"
          f"   ({100 * len(bl_em) / max(1, len(sotto_tetto)):.1f}%)")
    for code in ("NO_EBITDA_WITH_NET_DEBT",):
        k = [m for m in sotto_tetto if code in m["hits"]]
        print(f"     {code:<28}{len(k):>4}   {sorted(m['t'] for m in k)}")

    print("\n3. RIACQUISTI -- i sopravvissuti sono dominati dai buyback?")
    #  The mechanism the leverage filter is meant to spare: a company whose equity
    #  went negative by returning cash, not by losing it. If cumulative buybacks
    #  over eight quarters exceed the size of the equity hole, the hole is bought
    #  back rather than burned.
    def bb_line(group, label):
        with_bb = [m for m in group if m["buyback_8q"]]
        covering = [m for m in with_bb
                    if m["buyback_8q"] >= abs(m["eq"] or 0)]
        print(f"   {label:<34} {len(group):>3} nomi | "
              f"con riacquisti {len(with_bb):>3} | "
              f"riacquisti >= buco di equity {len(covering):>3}")
        return covering

    cov_s = bb_line(survivors, "sopravvissuti al filtro leva")
    bb_line(negl, "bloccati da NEGATIVE_EQUITY_LEVERED")
    print(f"   i sopravvissuti coperti da riacquisti: "
          f"{sorted(m['t'] for m in cov_s)}")

    print("\n" + "=" * 92)
    print("DOSSIER -- ogni nome valutabile: cio' che blocca e' un sottoinsieme "
          "di cio' che informa")
    print(f"{'ticker':<8}{'v3':>3}{'equity':>15}{'net debt':>15}{'EBITDA':>15}"
          f"{'leva':>9}{'eq/EV':>9}  verdetto")
    for m in sorted(recs, key=lambda x: (not x["hits"], -x["score_v3"], x["t"])):
        print(f"{m['t']:<8}{m['score_v3']:>3}{fm(m['eq'], 14)}{fm(m['nd'], 14)}"
              f"{fm(m['eb'], 14)}{fx(m['lev'], 8)}{fp(m['eq_pct_ev'], 8)}  "
              f"{','.join(m['hits']) or '-'}"
              f"{'  [adv ' + ','.join(m['advisory']) + ']' if m['advisory'] else ''}")

    print(f"\ntotale bloccati: {len(blocked)}/{n}")
    lv = sorted(m["lev"] for m in recs if m["lev"] is not None)
    if lv:
        print(f"leva calcolabile su {len(lv)}: mediana {statistics.median(lv):.2f}x, "
              f"p75 {lv[int(len(lv) * .75)]:.2f}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
