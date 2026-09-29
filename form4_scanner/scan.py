"""Orchestration: daily index -> Form 4 buys -> classify -> cluster -> score."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from .classify import (build_purchase_history, classify_insider,
                       first_filing_date)
from .cluster import group_by_issuer
from .bank import check_bank
from .vehicle import classify_vehicle, link_sponsors
from .dilution import check_dilution, veto_attivo
from .edgar import EdgarClient
from .market import get_provider
from .parse import open_market_buys, parse_ownership_xml
from . import secdays
from . import tickers
from .flags import evaluate_cluster

log = logging.getLogger(__name__)


#  Scan defaults, defined once. They used to exist twice -- here and again as
#  argparse defaults in cli.py -- as two independent copies that nothing kept in
#  step. A default that drifts between the library and its CLI produces runs
#  that are not the runs anyone thinks they asked for.
#  60 days, and the window is the one parameter here that cannot be revisited.
#  A transaction outside it is never collected, so the archive under state/ can
#  be rescored to a NARROWER window and never a wider one, and past days cannot
#  be recovered at all. It also decides what is SEEN: a Form 4 reaching the EDGAR
#  index more than this many days after its transaction date is invisible, and no
#  later run goes back for it. A live example, found on the first real run rather
#  than reasoned about -- a buy dated 2025-12-01 arrived in a scan of August 2026,
#  nine months late.
DEFAULT_LOOKBACK_DAYS = 60
DEFAULT_MIN_VALUE = 25_000.0
#  score_v3 has no size component, and there is no measurement to calibrate one
#  with. The cap IS the size decision, taken as a gate: names above it get read
#  by hand rather than ordered badly.
#
#  It used to be 10e9 here and 2e9 in run.sh, and nothing kept the two in step --
#  the disagreement silently decided which names could be emitted. 10 of the 41
#  signals emitted on 28 Aug sit above 2e9 (one of them scoring 8 under the
#  then-current twelve-point rubric). One value now, so there is no second
#  reachable behaviour to drift back into.
DEFAULT_MAX_MARKET_CAP = 2e9
DEFAULT_MIN_MARKET_CAP = 50e6
DEFAULT_HISTORY_YEARS = 3
DEFAULT_CACHE_DIR = ".edgar_cache"


def parse_master_index(text: str, form_types=("4", "4/A")) -> list[dict]:
    """Pipe-delimited master.idx -> deduped list of filings."""
    rows, seen = [], set()
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) != 5:
            continue
        cik, name, form, filed, path = (p.strip() for p in parts)
        if form not in form_types:
            continue
        accession = path.rsplit("/", 1)[-1].replace(".txt", "")
        if accession in seen:
            continue          # one row per filer CIK; we only need the filing once
        seen.add(accession)
        rows.append(
            {"cik": cik, "company": name, "form": form,
             "filed": filed, "accession": accession, "path": path}
        )
    return rows


def collect_buys(
    client: EdgarClient,
    start: date,
    end: date,
    min_value: float = DEFAULT_MIN_VALUE,
    tally=None,
) -> tuple[list, list[str]]:
    """Every non-plan open-market purchase filed between start and end inclusive.

    Returns `(acquisti, giorni_senza_indice)`: il secondo elenca i giorni il cui
    indice EDGAR non si è potuto leggere, che non sono «nessun acquisto».

    `tally`, if given, is shown every parsed transaction and the qualifying
    subset. The breadth counts were already being computed here and discarded --
    line 109 counted them inside a log call and never assigned the result -- so
    keeping them costs one method call and no extra requests.
    """
    all_buys = []
    #  Days whose index could not be read. A missing index is NOT an empty day:
    #  the scanner does not know what was filed, and CLAUDE.md is explicit that
    #  missing data must stay distinguishable from a verified nothing. The 403
    #  on 2026-07-03 and 2026-09-01 in the first scheduled run was benign -- a
    #  holiday and a not-yet-published file -- but the archive recorded those
    #  two days as "no purchases" exactly as it would have recorded a block.
    missing_index = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            #  Un festivo non si interroga affatto. Prima si chiedeva anche
            #  li': la SEC risponde 403, il client fa tre backoff e ci mette
            #  dodici secondi per scoprire che non c'era niente da leggere.
            #  Il giorno resta in `missing_index` -- l'indice davvero non e'
            #  stato letto, e quel campo conserva il suo significato -- ma la
            #  RAGIONE la classifica `secdays`, e non e' un buco.
            if not secdays.is_filing_day(day):
                missing_index.append(day.isoformat())
                log.info("%s: %s -- EDGAR chiusa, nessun deposito da leggere",
                         day, secdays.reason(day))
                day += timedelta(days=1)
                continue
            idx = client.daily_master_index(day)
            if not idx:
                missing_index.append(day.isoformat())
            if idx:
                filings = parse_master_index(idx)
                log.info("%s: %d Form 4 filings", day, len(filings))
                for f in filings:
                    xml = client.ownership_xml(f["cik"], f["accession"])
                    if not xml:
                        continue
                    txns = parse_ownership_xml(
                        xml, accession=f["accession"], filed_at=day
                    )
                    buys = open_market_buys(txns, min_value=min_value)
                    if tally is not None:
                        #  Every transaction for the denominator, the qualifying
                        #  ones for the numerator: an issuer that filed but did
                        #  not buy still counts as an issuer that filed.
                        tally.observe(day, txns, buys)
                    all_buys.extend(buys)
            else:
                #  ERROR already went to the log from EdgarClient.get. This is
                #  the line that makes it survive into the archive.
                kind, why = secdays.why_missing(day, end)
                if kind == secdays.NON_ANCORA:
                    log.info("%s: indice non ancora pubblicato (%s)", day, why)
                else:
                    log.warning("%s: indice ILLEGGIBILE -- giorno NON "
                                "osservato, e non e' un festivo", day)
        day += timedelta(days=1)
    return all_buys, missing_index


def run_scan(
    user_agent: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    min_value: float = DEFAULT_MIN_VALUE,
    max_market_cap: float = DEFAULT_MAX_MARKET_CAP,
    min_market_cap: float = DEFAULT_MIN_MARKET_CAP,
    market_provider: str = "yfinance",
    cache_dir: str = DEFAULT_CACHE_DIR,
    history_years: int = DEFAULT_HISTORY_YEARS,
    check_dilution_flag: bool = True,
    keep_blocked: bool = False,
    vehicle_overrides: dict | None = None,
    end: date | None = None,
    tally=None,
    sink: dict | None = None,
) -> list:
    """Un giro completo: indice EDGAR → acquisti veri → emittenti → cancelli → schede.

    Restituisce le `Card` ordinate per `score_v3` decrescente, poi per numero di
    compratori nella finestra. L'ordine è l'unica graduatoria che questo codice
    produce: non c'è soglia di superamento (flags.score_v3).

    `sink`, se passato, riceve quello che il chiamante mette nel rapporto senza
    doverlo ricalcolare: `clusters`, `labels`, `funnel` (i conteggi di ogni
    passaggio), `edgar` (statistiche delle richieste), `missing_index` (i giorni
    il cui indice non si è letto), `ticker_status`, `all_clusters` e `all_snaps`
    (la popolazione prima del cancello sulla capitalizzazione, che serve al
    terreno spin-off) e `client` (quello caldo, con la cache del giro).
    """
    client = EdgarClient(user_agent, cache_dir=cache_dir)
    market = get_provider(market_provider)

    end = end or date.today()
    start = end - timedelta(days=lookback_days)

    log.info("Collecting Form 4 purchases %s -> %s", start, end)
    buys, missing_index = collect_buys(client, start, end,
                                       min_value=min_value, tally=tally)
    log.info("%d qualifying purchases (code P, non-plan, >= $%s)", len(buys), f"{min_value:,.0f}")

    clusters = group_by_issuer(buys)
    log.info("%d issuers with insider buying", len(clusters))

    #  IL SIMBOLO SI RISOLVE SUL CIK, E SI RISOLVE QUI -- prima che qualcuno
    #  lo usi. Il ticker di un Form 4 lo scrive il depositante e puo' essere
    #  stantio: il CIK 0001844971 deposita ancora come GREE mentre EDGAR quel
    #  CIK lo elenca come VIP. La riga sotto chiede i prezzi per simbolo, e un
    #  simbolo morto restituisce una societa' senza prezzi -- cioe' la sposta
    #  fra i delistati presunti, che e' la variabile che domina ogni misura di
    #  questo corpus. Correggere dopo avrebbe corretto l'etichetta e non il
    #  dato. Vedi tickers.py per il perche' non si sostituisce alla cieca.
    ticker_status = None
    try:
        ticker_status = tickers.apply_to_clusters(clusters, client)
        log.info("simboli: %s", ticker_status)
    except Exception as exc:                              # noqa: BLE001
        #  Una mappa che non si carica non deve fermare il giro: senza di lei
        #  si tiene il simbolo del deposito, com'era prima di questo codice.
        log.warning("simboli non risolti: %s", exc)

    # Market-cap gate before the expensive history walk.
    #
    #  The gate decides the GENERAL LIST. It must not decide the spin-off
    #  terrain: a daughter distributed eight weeks ago whose insiders are
    #  buying is the whole point of the terrain, and whether she happens to be
    #  worth more than the ceiling is a different question. A daughter in
    #  fascia mid was cut here and _watch.md said "no" for a purchase that was
    #  inside both windows. So every cluster and its snapshot
    #  are handed out BEFORE the gate, and the terrain join runs on those.
    kept = []
    all_snaps = {}
    senza_prezzi = get_provider("none")
    for c in clusters:
        #  "NONE" e "N/A" sono simboli che il deposito scrive quando il titolo non
        #  e' quotato: chiederli al fornitore di prezzi e' una richiesta che fallisce
        #  comunque (misurate ~49 per giro). Il risultato e' lo stesso di prima --
        #  capitalizzazione ignota, quindi l'emittente non viene tagliato dalla fascia.
        snap = (market.snapshot(c.ticker) if c.ticker and not tickers.is_placeholder(c.ticker)
                else senza_prezzi.snapshot(c.ticker or ""))
        all_snaps[c.issuer_cik] = snap
        if snap.market_cap is not None:
            if snap.market_cap > max_market_cap or snap.market_cap < min_market_cap:
                continue
        kept.append((c, snap))
    log.info("%d issuers inside the cap band", len(kept))

    # Dilution gate BEFORE the expensive history walk: two cached requests per
    # issuer, and every name it vetoes is one we don't pay to classify.
    checked = []
    if check_dilution_flag:
        log.info("Dilution check on %d issuers", len(kept))
        for c, snap in kept:
            last_buy = c.last_date or end
            try:
                rep = check_dilution(client, c.issuer_cik, last_buy, as_of=end)
            except Exception as e:
                log.warning("dilution check failed for %s: %s", c.ticker or c.issuer_cik, e)
                rep = None
            if rep and rep.blocked and veto_attivo() and not keep_blocked:
                log.info("  VETO %s -- %s", c.ticker or c.issuer_name, rep.summary())
                continue
            checked.append((c, snap, rep))
        log.info("%d issuers survive the dilution gate", len(checked))
    else:
        checked = [(c, snap, None) for c, snap in kept]

    # The expensive part: 3 years of Form 4 history per distinct insider.
    since = date(end.year - history_years, end.month, 1)
    labels: dict[str, str] = {}
    owners = {t.owner_cik for c, _, _ in checked for t in c.txns}
    log.info("Classifying %d distinct insiders (this is the slow step)", len(owners))
    #  Le transazioni per proprietario, una volta sola: prima ogni insider
    #  riattraversava tutti i cluster due volte (misurato: 747 x 2.602 x 2 passi).
    per_owner: dict = {}
    for c, _s, _r in checked:
        for t in c.txns:
            per_owner.setdefault(t.owner_cik, []).append(t)

    for i, cik in enumerate(sorted(owners), 1):
        suoi = per_owner.get(cik, [])
        as_of_dates = [t.txn_date for t in suoi]
        as_of = max(d for d in as_of_dates if d) if any(as_of_dates) else end
        #  Il primo nome nell'ordine dei cluster, come prima: `per_owner` li
        #  raccoglie in quell'ordine.
        name = next((t.owner_name for t in suoi), "")
        hist = build_purchase_history(client, cik, since)
        # Exclude the buy under evaluation from its own history.
        hist = [d for d in hist if d < as_of]
        labels[cik] = classify_insider(
            cik, name, hist, as_of, history_years,
            cik_first_filing=first_filing_date(client, cik),
        ).label
        if i % 25 == 0:
            log.info("  ...%d/%d insiders", i, len(owners))

    # Depository asset-quality gate. Two cached XBRL reads per bank, and only
    # for banks -- everything else short-circuits on the SIC code.
    banks = {}
    for c, _, _ in checked:
        try:
            banks[c.issuer_cik] = check_bank(client, c.issuer_cik, as_of=end)
        except Exception as e:
            log.warning("bank check failed for %s: %s", c.ticker or c.issuer_cik, e)
    n_dep = sum(1 for b in banks.values() if b.is_depository)
    if n_dep:
        n_capped = sum(1 for b in banks.values() if b.capped)
        log.info("%d depository institution(s); %d capped on asset quality",
                 n_dep, n_capped)

    #  Vehicle classification: one cached submissions read per issuer, already
    #  warm from the dilution gate. Sponsors are linked across the whole run
    #  because two vehicles from one manager are one signal, not two, and that
    #  is only visible with every name in hand.
    vehicles = {}
    for c, _, _ in checked:
        try:
            vehicles[c.issuer_cik] = classify_vehicle(
                client, c.issuer_cik, c.issuer_name, overrides=vehicle_overrides)
        except Exception as e:
            log.warning("vehicle check failed for %s: %s",
                        c.ticker or c.issuer_cik, e)
    link_sponsors(vehicles.values(),
                  {c.issuer_cik: c.ticker for c, _, _ in checked})
    n_veh = sum(1 for v in vehicles.values() if v.is_vehicle)
    if n_veh:
        log.info("%d externally-managed vehicle(s) flagged (BDC/REIT)", n_veh)

    cards = [
        evaluate_cluster(
            c, labels, snap,
            dilution=rep,
            bank=banks.get(c.issuer_cik),
            vehicle=vehicles.get(c.issuer_cik),
        )
        for c, snap, rep in checked
    ]
    if sink is not None:
        #  The clusters and the CMP labels, for callers that archive what was
        #  seen rather than only what was decided. Handed out rather than
        #  returned so every existing caller keeps the same signature.
        sink["clusters"] = [c for c, _, _ in checked]
        sink["labels"] = labels
        sink["funnel"] = {
            "qualifying_purchases": len(buys),
            "issuers_with_buying": len(clusters),
            "issuers_in_cap_band": len(kept),
            "issuers_past_dilution_gate": len(checked),
            "distinct_insiders_classified": len(owners),
            "issuers_evaluated": len(cards),
        }
        #  What the run cost. Handed out with everything else so the caller can
        #  put it in the log without reaching into the client.
        sink["edgar"] = dict(client.stats)
        sink["missing_index"] = missing_index
        #  Quanti simboli sono stati corretti, e quanti sono
        #  rimasti ambigui. Un conteggio, non una lista di nomi.
        sink["ticker_status"] = ticker_status or {}
        #  Everything with insider buying, before the cap gate. The terrain
        #  join needs the population the gate removed.
        sink["all_clusters"] = clusters
        sink["all_snaps"] = all_snaps
        #  Il client caldo, non uno nuovo: l'arricchimento in report.py lavora
        #  sugli emittenti NUOVI del giorno -- una dozzina -- e le loro
        #  submissions sono gia' in cache da questo giro. Un secondo client le
        #  riscaricherebbe tutte.
        sink["client"] = client

    return sorted(cards, key=lambda c: (
        -(c.v3.get("score") or 0),
        -((c.inputs.get("cluster") or {}).get("buyers_in_window") or 0),
    ))
