"""Command line entrypoint.

    python -m form4_scanner.cli --user-agent "Nome Cognome nome@example.com"
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from .compare import compare, load_previous, render
from .scan import (DEFAULT_CACHE_DIR, DEFAULT_LOOKBACK_DAYS,
                   DEFAULT_MAX_MARKET_CAP, DEFAULT_MIN_MARKET_CAP,
                   DEFAULT_MIN_VALUE, run_scan)


def load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        logging.warning("%s not found -- continuing without it", path)
        return {}
    return json.loads(p.read_text())


def verdict_main(argv) -> int:
    """`python -m form4_scanner.cli verdict add --ticker AAA ...`

    Il giudizio e' dell'operatore. Questo comando lo scrive, gli assegna un id, lo
    lega al precedente sullo stesso CIK e lo rilegge ad alta voce. Non deduce
    niente: senza verdict, thesis o invalidation rifiuta, perche' un default su
    uno di quei tre sarebbe lo scanner che si inventa un giudizio.
    """
    from . import verdicts as v

    ap = argparse.ArgumentParser(prog="form4 verdict")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="registra un verdetto")
    a.add_argument("--ticker", required=True)
    a.add_argument("--cik", default=None,
                   help="se assente si cerca nell'archivio observations")
    a.add_argument("--verdict", required=True, choices=list(v.CLASSES))
    a.add_argument("--thesis", required=True,
                   help="una riga, parole tue: perche' questo verdetto")
    a.add_argument("--invalidation", action="append", default=[],
                   help="ripetibile: cosa direbbe che il verdetto era sbagliato")
    a.add_argument("--upgrade-trigger", action="append", default=[])
    a.add_argument("--price", type=float, default=None)
    a.add_argument("--cap-bucket", default=None)
    a.add_argument("--terreno", default=None)
    a.add_argument("--score-v3", type=int, default=None)
    a.add_argument("--review-date", default=None)
    a.add_argument("--source-report", default=None)
    a.add_argument("--has-13d", action="store_true", default=None)
    a.add_argument("--expected-return", type=float, default=None,
                   help="l'attesa in percentuale, tua, da confrontare come le altre")
    a.add_argument("--expected-horizon", default=None,
                   help="l'orizzonte dell'attesa, es. '18-22 mesi'")
    a.add_argument("--date", default=None, help="YYYY-MM-DD, default oggi")

    sub.add_parser("list", help="i verdetti in vigore")

    ns = ap.parse_args(argv)

    if ns.cmd == "list":
        cur = v.current()
        if not cur:
            print("nessun verdetto registrato")
            return 0
        for cik, r in sorted(cur.items(), key=lambda kv: kv[1]["date"]):
            print("  {}  {:<7} {:<11} {}  (rivedere entro {})".format(
                r["date"], r.get("ticker") or cik, r["verdict"],
                r["thesis"][:52], r.get("review_date") or "-"))
        return 0

    cik = ns.cik
    if not cik:
        cik = _cik_for_ticker(ns.ticker)
        if not cik:
            print("CIK non trovato per {}: passalo con --cik".format(ns.ticker))
            return 2
    try:
        rec = v.add(
            cik, ns.ticker, ns.verdict, ns.thesis, ns.invalidation,
            price_at_verdict=ns.price, cap_bucket=ns.cap_bucket,
            terreno=ns.terreno, score_v3=ns.score_v3,
            upgrade_triggers=ns.upgrade_trigger, review_date=ns.review_date,
            source_report=ns.source_report, has_13d=ns.has_13d,
            expected_return_pct=ns.expected_return,
            expected_horizon_months=ns.expected_horizon,
            on=(datetime.strptime(ns.date, "%Y-%m-%d").date() if ns.date
                else date.today()))
    except ValueError as e:
        print("RIFIUTATO: {}".format(e))
        return 2

    print("\nscritto in {}\n".format(v.LEDGER))
    for k in ("id", "date", "ticker", "cik", "verdict", "price_at_verdict",
              "cap_bucket", "terreno", "score_v3", "has_13d",
              "expected_return_pct", "expected_horizon_months", "thesis",
              "invalidation", "upgrade_triggers", "review_date",
              "source_report", "supersedes"):
        print("  {:<18} {}".format(k, rec.get(k)))
    if rec.get("supersedes"):
        print("\n  supersede il verdetto {} sullo stesso CIK".format(
            rec["supersedes"]))
    return 0


def _cik_for_ticker(ticker):
    """Il CIK dall'archivio observations. Nessuna rete."""
    root = Path(__file__).resolve().parents[1]
    obs = root / "state" / "observations" / "form4"
    if not obs.exists():
        return None
    t = (ticker or "").upper()
    for f in sorted(obs.glob("*.jsonl"), reverse=True):
        for line in f.read_text(encoding="utf-8").splitlines():
            if t not in line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("kind") == "observation" and (r.get("ticker") or "").upper() == t:
                return r.get("issuer_cik")
    return None



def main(argv=None) -> int:
    #  Sottocomando prima del parser principale, cosi' daily.sh e ogni invocazione
    #  esistente restano identiche: solo `verdict` devia.
    args = sys.argv[1:] if argv is None else list(argv)
    if args and args[0] == "verdict":
        return verdict_main(args[1:])

    ap = argparse.ArgumentParser(description="SEC Form 4 opportunistic-buy scanner")
    ap.add_argument("--user-agent", required=True,
                    help="SEC requires 'Name email@domain'. Requests without it are blocked.")
    ap.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS, help="lookback window in days")
    ap.add_argument("--end", default=None, help="end date YYYY-MM-DD (default today)")
    ap.add_argument("--min-value", type=float, default=DEFAULT_MIN_VALUE)
    ap.add_argument("--max-cap", type=float, default=DEFAULT_MAX_MARKET_CAP)
    ap.add_argument("--min-cap", type=float, default=DEFAULT_MIN_MARKET_CAP)
    ap.add_argument("--market", default="yfinance", choices=["yfinance", "none"])
    ap.add_argument("--vehicles", default="config/vehicles.json",
                    help="{cik: {externally_managed: bool, sponsor: str}} "
                    "you maintain by hand for BDCs and REITs you have read")
    ap.add_argument("--cache", default=DEFAULT_CACHE_DIR)
    ap.add_argument("--out", default="out/form4_scan.csv")
    ap.add_argument("--all", action="store_true",
                    help="keep dilution-vetoed names in the CSV too")
    ap.add_argument("--no-dilution", action="store_true",
                    help="skip the dilution gate (faster, but you MUST check S-3/424B by hand)")
    ap.add_argument("--compare", help="a previous run CSV; the report then "
                    "reports what entered, left and moved, and says WHY each "
                    "name left -- an aged-out buy is not a worse score")
    ap.add_argument("--show-blocked", action="store_true",
                    help="keep dilution-vetoed names in the output, marked")
    #  On by default, opt-out by flag. A flag you have to remember is how the
    #  signal emission stayed silently inert until someone looked: the archive
    #  that must never miss a day cannot depend on anyone recalling a switch.
    ap.add_argument("--no-observations", action="store_true",
                    help="do not append this run to state/observations/ and "
                         "state/breadth/ (they are written by default)")
    ap.add_argument("--observations-dir", default=None,
                    help="where the append-only archive lives (default: <repo>/state)")
    ap.add_argument("--reports-dir", default=None,
                    help="where daily_YYYY-MM-DD.md and spinoffs/_watch.md go "
                         "(default: <repo>/reports)")
    ap.add_argument("--no-reports", action="store_true",
                    help="skip the two markdown reports (the CSV still lands)")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if a.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    end = datetime.strptime(a.end, "%Y-%m-%d").date() if a.end else date.today()
    #  The window run_scan will use, recomputed here so the delta report can
    #  say whether a departed name simply fell out the back of it.
    start = end - timedelta(days=a.days)

    started = time.monotonic()
    sink: dict = {}
    tally = None
    if not a.no_observations:
        from .breadth import BreadthTally
        tally = BreadthTally(min_value=a.min_value)

    cards = run_scan(
        user_agent=a.user_agent,
        lookback_days=a.days,
        min_value=a.min_value,
        max_market_cap=a.max_cap,
        min_market_cap=a.min_cap,
        market_provider=a.market,
        cache_dir=a.cache,
        check_dilution_flag=not a.no_dilution,
        #  The archive needs the names the gate rejected: 77 of 336 issuers on
        #  the 28 Aug run, pruned BEFORE scoring and therefore never judged. The
        #  rubric is being tested, so a sample truncated on the gate is the same
        #  mistake as one truncated on the pass mark, one level up. Costs the
        #  expensive history walk on those names -- about +30% run time.
        keep_blocked=a.show_blocked or not a.no_observations,
        vehicle_overrides=load_json(a.vehicles),
        end=end,
        tally=tally,
        sink=sink,
    )

    #  Before `shown` exists. The archive keeps every issuer the rubric scored,
    #  including the ones it scored badly: the pass mark is the variable under
    #  test, so filtering on it would truncate the sample on exactly that.
    #  Written before the CSV too, so a failure there cannot cost the record.
    if not a.no_observations:
        try:
            from . import breadth as breadth_mod
            from . import observations as obs_mod
            #  NOT a.state_dir: that pointed at an external repo's shared queue.
            #  The archive is this package's own, and a standalone package has
            #  no business writing its history into another project.
            obs_dir = a.observations_dir or (
                obs_mod.Path(__file__).resolve().parents[1] / "state")
            sha = obs_mod.git_sha()
            op = obs_mod.write(
                cards, obs_dir, end, a.days,
                params={"days": a.days, "min_value": a.min_value,
                        "min_cap": a.min_cap, "max_cap": a.max_cap,
                        "market": a.market, "dilution": not a.no_dilution,
                        #  The EFFECTIVE value, not the flag. The archive turns
                        #  keep_blocked on by itself, so recording `--show-blocked`
                        #  here wrote "false" onto runs that had in fact scored the
                        #  vetoed names -- a parameter that decides the population,
                        #  described wrongly on every row of that population.
                        "keep_blocked": bool(a.show_blocked or not a.no_observations),
                        "show_blocked_flag": bool(a.show_blocked)},
                funnel=sink.get("funnel", {}),
                labels=sink.get("labels", {}),
                clusters=sink.get("clusters", []),
                index_unavailable=sink.get("missing_index", []),
                ticker_status=sink.get("ticker_status", {}))
            print(f"\n  observations: {len(cards)} emittenti -> {op}")
            if tally is not None:
                bp = breadth_mod.write_weeks(tally, obs_dir, end, a.days,
                                             scanner_sha=sha, start=start,
                                             end=end)
                print(f"  breadth: {len(tally.weeks())} settimane -> {bp}")
        except Exception as e:
            #  Loud, and it does not stop the run: the CSV and the queue are
            #  still worth producing on a day the archive could not be written.
            print(f"\n  ARCHIVIO NON SCRITTO: {e}")

    #  The two files a person reads. Written before the CSV for the same
    #  reason the archive is: a failure further down must not cost them.
    if not a.no_reports:
        try:
            from . import report as report_mod
            rep_dir = a.reports_dir or (Path(__file__).resolve().parents[1]
                                        / "reports")
            st_dir = a.observations_dir or (Path(__file__).resolve().parents[1]
                                            / "state")
            dp, n_new, n_rep = report_mod.write_daily(
                cards, rep_dir, end, st_dir, a.days,
                funnel=sink.get("funnel", {}), edgar=sink.get("edgar", {}),
                seconds=time.monotonic() - started,
                missing_index=sink.get("missing_index", []),
                clusters=sink.get("clusters", []),
                min_cap=a.min_cap, max_cap=a.max_cap,
                ticker_status=sink.get("ticker_status", {}),
                #  Il client caldo del giro, per la colonna `emissione`. Senza,
                #  la colonna resta a trattino e il report e' quello di prima.
                client=sink.get("client"))
            wp = report_mod.write_spinoff_watch(
                cards, rep_dir, end,
                all_clusters=sink.get("all_clusters", []),
                all_snaps=sink.get("all_snaps", {}))
            #  Il mensile sui verdetti. Lo scanner NON scrive
            #  data/verdicts.jsonl: lo legge e lo misura, che e' l'unico
            #  diritto che ha su quel file.
            from . import verdicts as verdicts_mod
            cur = verdicts_mod.current()
            bench = {}
            for vr in cur.values():
                got, _n = report_mod.ew_sub2e9_return(vr["date"], end, st_dir)
                if got is not None:
                    bench[vr["date"]] = got
            snaps = sink.get("all_snaps", {})
            by_tick = {}
            for c in sink.get("all_clusters", []):
                if c.ticker:
                    by_tick[c.ticker.upper()] = snaps.get(c.issuer_cik)
            vp = report_mod.write_verdict_report(
                rep_dir, end, lambda t: by_tick.get((t or "").upper()),
                universe_caps=bench)
            print(f"\n  lista: {n_new} nuovi, {n_rep} gia' visti -> {dp}")
            print(f"  verdetti: {len(cur)} in vigore -> {vp}")
            print(f"  terreno: -> {wp}")

            #  L'esito in un file che una macchina puo' leggere. Serve a chi
            #  deve DIRE che il report esiste: uno scheduler esterno lancia lo
            #  scanner catturandone l'output, quindi le righe stampate qui sopra non
            #  le vede nessuno, e il report finisce su un disco in silenzio.
            try:
                from . import lastrun
                from .observations import git_sha
                lr = lastrun.write(
                    st_dir, end,
                    report=dp, spinoff_watch=wp, verdicts=vp, csv=a.out,
                    new=n_new, repeat=n_rep, issuers_evaluated=len(cards),
                    seconds=time.monotonic() - started,
                    missing_index=sink.get("missing_index", []),
                    sha=git_sha())
                print(f"  esito: -> {lr}")
            except Exception as e:
                #  Un aggancio per le notifiche non puo' costare il report.
                print(f"  esito NON scritto: {e}")
        except Exception as e:
            print(f"\n  REPORT NON SCRITTI: {e}")

    #  Everything that cleared the gates, ordered. There is no pass mark to
    #  clear any more: the gates decide who is in the list and score_v3 only
    #  decides the order within it.
    shown = cards if a.all else [c for c in cards if not c.blocked]
    vetoed = [c for c in cards if c.blocked]

    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        #  La colonna tiene i NOMI dei booleani veri («director+no_10pct»), non
        #  dei punti: si chiamava "points" da quando i punti esistevano.
        w.writerow(["score_v3", "booleani", "ticker", "issuer", "cik",
                    "total_buy_usd", "market_cap", "survivability", "dilution",
                    "buyers_in_window", "shares_growth_1y_pct",
                    "first_buy_date", "last_buy_date", "flags"])
        for c in shown:
            got = [k for k in ("cluster", "director", "no_10pct", "terreno")
                   if c.v3.get(k) is True]
            w.writerow([
                c.v3.get("score", 0), "+".join(got),
                c.ticker, c.issuer_name, c.issuer_cik,
                f"{c.context.get('total_value') or 0:.0f}",
                c.context.get("market_cap") or "",
                c.context.get("survivability", ""),
                c.context.get("dilution", ""),
                (c.inputs.get("cluster") or {}).get("buyers_in_window", ""),
                (c.dilution.shares_growth_pct if c.dilution and
                 c.dilution.shares_growth_pct is not None else ""),
                c.context.get("first_buy_date") or "",
                c.context.get("last_buy_date") or "",
                " | ".join(c.flags),
            ])

    took = time.monotonic() - started
    ed = sink.get("edgar", {})
    print(f"\n{len(cards)} issuers evaluated, {len(shown)} written to {a.out}")
    print(f"  durata {took:.0f}s ({took / 60:.1f} min) -- EDGAR "
          f"{ed.get('network', 0):,} rete, {ed.get('cache', 0):,} cache, "
          f"{ed.get('backoff', 0):,} backoff, {ed.get('fail', 0):,} falliti\n")
    for c in shown[:25]:
        #  I booleani nominati, non una frazione: 2/4 accanto a 3/4 invita a
        #  leggere una distanza calibrata, e qui non e' calibrato niente.
        got = [k for k in ("cluster", "director", "no_10pct", "terreno")
               if c.v3.get(k) is True]
        print(f"  {c.v3.get('score', 0)}  {c.ticker or '?':<7} "
              f"{c.issuer_name[:38]:<38} "
              f"${(c.context.get('total_value') or 0):>12,.0f}  "
              f"{'+'.join(got) if got else '-'}")
        for f in c.flags:
            print(f"          ! {f}")
    if not shown:
        print("  every issuer was vetoed on dilution -- "
              "rerun with --all to see them")

    if vetoed:
        print(f"\n  {len(vetoed)} name(s) scored well but were vetoed on dilution:")
        for c in vetoed[:10]:
            print(f"    {c.v3.get('score', 0)}  {c.ticker or '?':<7} {c.dilution.summary()}")
    elif not a.show_blocked and a.no_observations:
        #  Without --show-blocked the vetoed names are pruned inside
        #  run_scan, before the expensive history walk, so there is
        #  nothing here to count. That pruning is the point -- a vetoed
        #  name is one we do not pay to classify -- but the report should
        #  say the list exists rather than let the reader assume nothing
        #  was vetoed.
        print("\n  dilution-vetoed names were pruned before scoring; "
              "rerun with --show-blocked to see them")

    #  The signal export lived here. emit.py keyed its dedup on the score
    #  (emit.py:140, `dedup: str(card.score)`), so it could not survive the
    #  rubric's removal unchanged, and rewriting it before v3 has a measured
    #  threshold would be inventing one. There is no signal export until v3
    #  has a measured threshold.

    if a.compare:
        #  The full card list, not `shown`: a name that fell from 7 to 5 is
        #  still scored, and telling that apart from a name that never reached
        #  scoring is what makes the delta readable.
        previous, has_last_buy = load_previous(a.compare)
        if previous:
            deltas = compare(previous, cards, start, has_last_buy=has_last_buy)
            print(render(deltas, a.compare, has_last_buy))
    return 0


if __name__ == "__main__":
    sys.exit(main())
