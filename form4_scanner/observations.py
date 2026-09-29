"""Every issuer the rubric scored, kept forever. Append-only, no judgement.

WHY THIS EXISTS, and why it logs the names that scored badly. No outcome has ever
been recorded for any signal this scanner produced, and the twelve weights have
never been compared against anything -- they are a priori judgement. Testing
whether the rubric discriminates needs the names it judged BADLY as much as the
ones it liked; logging only what cleared the pass mark would truncate the sample
on exactly the variable under test.

This is NOT the signal queue. The queue in `state/signals/form4/` is a live set
of decisions with a TTL, deduplication and archiving, and it means "act on this".
These rows mean "this is what was seen". Mixing them would destroy what
`_expired` means. Nothing here expires, deduplicates or is ever rewritten.

WHAT MAKES A ROW RESCORABLE. `components` holds the points the rubric awarded;
`inputs` holds what each criterion read to award them; `transactions` holds the
cluster itself. Weights can be changed and the archive replayed from `inputs`.
Parameters that change which transactions COUNT -- the cluster window above all
-- need `transactions`, which is why they are stored in full.

THE WINDOW IS A CEILING, NOT A FILTER. A transaction outside the emission window
is never collected, so a past run can be rescored to a NARROWER window but never
a wider one, and past days can never be recovered at all. The window in use is
the permanent upper bound on everything this archive will ever be able to answer.
Recorded on every row for that reason.

FOUR FIELDS CANNOT BE REBUILT FROM EDGAR: market_cap, drawdown_pct,
analyst_count and survivability_flag all come from the market provider, which
returns today's value and has no memory. market_cap is the worst of them,
because it decides which issuers enter the cap band at all -- a change in its
definition upstream would alter the population, not just a column. Each carries
its source and fetch time.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from .flags import cap_bucket
from . import secdays

SCHEMA_VERSION = 1

#  Bumped BY HAND whenever a weight, a threshold or a criterion changes. Rows
#  written either side of such a change are not comparable, and without a version
#  on the row nothing would say so -- the dataset would corrupt in silence while
#  looking perfectly well formed.
#
#  2: the drawdown criterion left the rubric. This is the first bump, and the
#  case the field was put there for.


def git_sha(repo_root=None) -> str:
    """The commit the scanner ran at. Empty string if unknowable, never a guess."""
    try:
        root = Path(repo_root or Path(__file__).resolve().parents[1])
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=str(root), capture_output=True, text=True,
                             timeout=5)
        sha = out.stdout.strip()
        if out.returncode != 0 or not sha:
            return ""
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=str(root),
                               capture_output=True, text=True, timeout=5)
        #  A dirty tree means the sha does not describe the code that ran. Saying
        #  so is the difference between a reproducible row and one that merely
        #  looks reproducible.
        return sha + ("-dirty" if dirty.stdout.strip() else "")
    except Exception:
        return ""


@dataclass(frozen=True)
class TxnRecord:
    """One transaction row, as filed.

    `txn_index` is not decoration: a joint filing emits one row per reporting
    owner, and (accession, txn_index) is the only stable identity of the
    underlying trade. Without it a downstream sum multiplies by the number of
    co-filers -- observed live turning $64.8M into $259.2M.

    `is_10b5_1` is always False here, and that is not a bug: `open_market_buys`
    excludes plan transactions upstream, so no clustered buy can be one. It is
    recorded so the column means something if that filter ever moves, but it
    cannot be used to study 10b5-1 adoption from this archive.
    """

    transaction_date: str | None
    owner_cik: str
    owner_name: str
    role: str
    officer_title: str
    shares: float
    price: float
    value: float
    shares_after: float
    is_10b5_1: bool
    cmp_label: str
    accession_number: str
    txn_index: int
    filed_at: str | None


@dataclass(frozen=True)
class Observation:
    """One issuer, one run. Judgement recorded, never acted on."""

    kind: str
    schema_version: int
    scanner_git_sha: str
    run_date: str
    observed_at: str
    window_days: int
    issuer_cik: str
    ticker: str
    issuer_name: str
    blocked: bool
    #  Four booleans and their sum. Recorded for every issuer, vetoed ones
    #  included, so the ordering can be re-derived from the row rather than
    #  trusted. terreno is None until data/spinoffs_index.json exists.
    score_v3: int | None
    v3_cluster: bool | None
    v3_director: bool | None
    v3_no_10pct: bool | None
    v3_terreno: bool | None
    inputs: dict
    context: dict
    sources: dict
    flags: list
    transactions: list


def _iso(d) -> str | None:
    return d.isoformat() if isinstance(d, date) else (str(d) if d else None)


def txn_records(cluster, labels: dict) -> list:
    """The cluster's transactions, with the CMP label that was in force."""
    out = []
    for t in cluster.txns:
        out.append(TxnRecord(
            transaction_date=_iso(t.txn_date),
            owner_cik=t.owner_cik,
            owner_name=t.owner_name,
            role=t.role,
            officer_title=t.officer_title or "",
            shares=t.shares,
            price=t.price,
            value=t.value,
            shares_after=t.shares_after,
            is_10b5_1=bool(t.plan_10b5_1),
            cmp_label=labels.get(t.owner_cik, ""),
            accession_number=t.accession,
            txn_index=t.txn_index,
            filed_at=_iso(t.filed_at),
        ))
    return out


def observation_for(card, labels: dict, run_date: date, window_days: int,
                    sha: str, observed_at: str, cluster=None) -> Observation:
    """One row per evaluated issuer, vetoed ones included.

    v3 schema. Gone: score, max_score, pass_mark, passes, uncapped_score,
    components, rubric_version -- there is no rubric to version. In their place
    `score_v3` and the four booleans it sums, recorded for every issuer so the
    ordering can be re-derived from the row instead of trusted.
    """
    ctx = card.context or {}
    v3 = card.v3 or {}
    return Observation(
        kind="observation",
        schema_version=SCHEMA_VERSION,
        scanner_git_sha=sha,
        run_date=run_date.isoformat(),
        observed_at=observed_at,
        window_days=window_days,
        issuer_cik=card.issuer_cik,
        ticker=card.ticker or "",
        issuer_name=card.issuer_name,
        blocked=bool(card.blocked),
        score_v3=v3.get("score"),
        v3_cluster=v3.get("cluster"),
        v3_director=v3.get("director"),
        v3_no_10pct=v3.get("no_10pct"),
        v3_terreno=v3.get("terreno"),
        #  What each criterion read to reach it.
        inputs=dict(card.inputs or {}),
        #  Neither: context the rubric carried but did not score on.
        context={
            "market_cap": ctx.get("market_cap"),
            #  The raw number AND the band, because every question asked of
            #  this archive so far has been asked by band, and re-deriving it
            #  downstream is how two definitions start drifting apart.
            "cap_bucket": ctx.get("cap_bucket") or cap_bucket(
                ctx.get("market_cap")),
            "total_buy_usd": ctx.get("total_value"),
            "first_buy_date": _iso(ctx.get("first_buy_date")),
            "last_buy_date": _iso(ctx.get("last_buy_date")),
            "survivability": ctx.get("survivability"),
            "dilution": ctx.get("dilution"),
            "npa_pct": ctx.get("npa_pct"),
            "vehicle": ctx.get("vehicle"),
        },
        sources=_sources(card),
        flags=list(card.flags or []),
        transactions=[asdict(t) for t in txn_records(cluster, labels)]
        if cluster is not None else [],
    )


def _sources(card) -> dict:
    """Provenance for the fields EDGAR cannot rebuild.

    market_cap is the only market-derived field left in the row; drawdown and
    the analyst count went with the criteria that used them.
    """
    dd = {}
    return {
        "market": {"provider": dd.get("source", ""),
                   "fetched_at": dd.get("fetched_at", ""),
                   "fields": ["market_cap", "drawdown_pct", "analyst_count",
                              "survivability"]},
        "edgar": {"provider": "sec.gov", "fields": ["transactions", "dilution",
                                                    "npa_pct", "vehicle",
                                                    "cmp_label"]},
    }


def run_header(run_date: date, window_days: int, sha: str, observed_at: str,
               params: dict, funnel: dict, index_unavailable=None,
               ticker_status=None) -> dict:
    """One row per run, written FIRST.

    Without it a day on which nothing was scored -- network down, EDGAR
    returning 503, an empty cap band -- produces no rows at all, and is
    indistinguishable from a day the scanner never ran. Those are different
    facts and the archive has to keep them apart.
    """
    groups = secdays.classify(index_unavailable or [], run_date)
    return {
        "kind": "run",
        "schema_version": SCHEMA_VERSION,
        "scanner_git_sha": sha,
        "run_date": run_date.isoformat(),
        "observed_at": observed_at,
        "window_days": window_days,
        "params": params,
        "funnel": funnel,
        #  The days inside the window whose EDGAR index could not be read. An
        #  empty list means every weekday in the window was actually looked at;
        #  a non-empty one means those days are UNKNOWN, not empty. Without it
        #  a blocked day and a quiet day are the same row six months later.
        #
        #  IL SIGNIFICATO DI QUESTO CAMPO NON E' CAMBIATO, apposta: e' ancora
        #  ogni giorno lavorativo il cui indice non e' stato letto, festivi
        #  compresi. Le righe scritte prima del 2026-09-10 restano quindi
        #  confrontabili con quelle scritte dopo. Cio' che si aggiunge e' la
        #  RAGIONE, nei tre campi qui sotto: un festivo non e' un buco, e
        #  prima erano indistinguibili.
        "index_unavailable": index_unavailable or [],
        #  Il sottoinsieme che e' davvero un buco: c'erano depositi e non li
        #  abbiamo visti. E' questo il numero da guardare.
        "index_unreadable": [d for d, _ in groups[secdays.ILLEGGIBILE]],
        #  EDGAR chiusa: niente da leggere, non un buco.
        "index_not_filing_day": [
            {"date": d, "reason": w}
            for d, w in groups[secdays.FESTIVO] + groups[secdays.CHIUSURA]
        ],
        #  L'indice del giorno esce la sera: il giro del mattino non lo trova.
        "index_not_yet": [d for d, _ in groups[secdays.NON_ANCORA]],
        #  Quanti simboli sono stati risolti sul CIK e con quale esito. Serve
        #  a spiegare una riga che ieri diceva CYBN e oggi dice HELP sullo
        #  stesso CIK: senza questo il cambio si vede e non si capisce.
        "ticker_status": dict(ticker_status or {}),
    }


def write(cards, state_dir, run_date: date, window_days: int, params: dict,
          funnel: dict, labels=None, clusters=None,
          index_unavailable=None, ticker_status=None) -> Path:
    """Append the run header and one row per evaluated issuer.

    Append-only: no TTL, no dedup, no archiving. It grows.
    """
    d = Path(state_dir) / "observations" / "form4"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{run_date.isoformat()}.jsonl"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    sha = git_sha()
    labels = labels or {}
    by_cik = {c.issuer_cik: c for c in (clusters or [])}

    lines = [json.dumps(run_header(run_date, window_days, sha, now, params,
                                   funnel, index_unavailable, ticker_status),
                        sort_keys=True)]
    for card in cards:
        obs = observation_for(card, labels, run_date, window_days, sha, now,
                              cluster=by_cik.get(card.issuer_cik))
        #  allow_nan=False so an infinity or a NaN raises here rather than being
        #  written as a token no strict JSON reader will accept. A row that
        #  cannot be read back is worse than a row that was never written.
        lines.append(json.dumps(asdict(obs), sort_keys=True, allow_nan=False))

    tmp = path.with_suffix(".jsonl.tmp")
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    tmp.write_text(existing + "".join(ln + "\n" for ln in lines),
                   encoding="utf-8")
    os.replace(tmp, path)
    return path
