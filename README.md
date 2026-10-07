# edge-lab

A research lab for US market events built from SEC EDGAR data, with the method at the centre.

The stories that circulate about small caps are simple and testable: insiders know something, forced index selling
bounces back, IPOs that trade well keep winning. edge-lab takes such a story, writes down in advance what would count
as evidence for it, builds the data from primary sources, and publishes the verdict whatever it is. The studies in
this repository **did not find an edge**, and that is the point: each one shows where a number that looked like an
effect came from, and why it did not survive a fair comparison.

This is the public half of the project. The studies whose results held up, and the operational work built on them,
live in a private version of the repository.

What is here:

- **a Form 4 insider-purchase filter** (`form4_scanner/`) that keeps only genuine open-market purchases and hands a
  human booleans and the evidence behind them, never a recommendation;
- **the research infrastructure** around it: an EDGAR client with a disk cache, a point-in-time XBRL layer, a data
  layer with a single typed entry point for prices, Fed series and SEC bulk filings (`market-data/`), an LLM
  extraction package that enriches and never decides (`edgar_llm/`), and the statistics tools (`tools/`);
- **three published studies** (`backtest/`), each with its pre-registration, addenda, decision records, code,
  aggregate results and an English summary page;
- **the method**: how a study is pre-registered, what happens when the data invalidates a backtest, and how coding
  agents were used and kept honest ([`docs/method/`](docs/method/)).

---

## Contents

- [Published studies](#published-studies)
- [Method](#method)
- [Architecture](#architecture)
- [Data layer and data quality](#data-layer-and-data-quality)
- [The Form 4 filter](#the-form-4-filter)
- [Reproducing the tests](#reproducing-the-tests)
- [Repository layout](#repository-layout)
- [Known limits](#known-limits)

---

## Published studies

Verdict labels: **HOLDS**, **INCONCLUSIVE**, **DOES NOT HOLD**, with the rule for each fixed before any return was
computed. The working documents are in Italian; each study has an English summary page.

### US insider buying in $50-300M stocks: an effect found, then not confirmed

[`backtest/rematch_50_300m/STUDY.md`](backtest/rematch_50_300m/STUDY.md)

One story in three steps. On 2026-09-01 a descriptive backtest over the whole Form 4 corpus showed insider purchases
in $50-300M stocks beating the small-cap index by +3.50% over 126 sessions, t 4.30. The same day a matched control
shrank it, and the effect concentrated in the stocks that had fallen most, which is the signature of reversal rather
than information. The pre-registered re-test of 2026-09-15 compared events with peers of the same size and momentum
and checked the comparison with placebo windows before the event: against the index the effect is still there,
against comparable companies it is not distinguishable from zero, and the matched peers already differed from the
event stocks 18-24 months **before** the purchase. Verdict: **INCONCLUSIVE** (row R1, "placebo not ≈ 0, no matching
fixes it"). The same idea tested on Swedish insider filings does not hold either:
<https://github.com/WilliePim/fi-insider-scanner>.

### E2 — Stocks that drop out of the Russell 2000

[`backtest/russell_exits/STUDY.md`](backtest/russell_exits/STUDY.md)

The story: index funds sell deleted stocks on a fixed date regardless of price, so the price should recover once the
selling is over. Index membership was rebuilt from the iShares funds' own SEC filings for 2015-2025 and checked
against the official deletion lists. Both pre-registered cells, "buy when the selling looks over and hold a year" and
"short rebound after reconstitution", **DO NOT HOLD**: the t-statistic across years is 0.24 and 0.45, and in the
investment cell a placebo of stocks that were **not** deleted did better than the deleted ones.

### E3 — Broken IPOs and strong IPOs (US, 2012-2024)

[`backtest/ipo_e3/STUDY.md`](backtest/ipo_e3/STUDY.md)

Two opposite stories tested with the same machinery. "Healthy IPOs crushed below the offer price recover" is
**INCONCLUSIVE**: only 17 cases passed the health filters, below the size the rule requires, and their median was
negative against peers. "IPOs that never traded below the offer price keep winning" **DOES NOT HOLD**: the median
strong IPO lost to comparable companies over the following year, and the positive mean was carried by a few very large
winners (t 1.07).

**What is not in this repo.** The studies that did find an edge, and everything built to use them, are in a private
version of this repository. What is published here is what was tested and could not be confirmed.

---

## Method

- **Pre-registration** ([`docs/method/preregistration.md`](docs/method/preregistration.md)): the rule, the sample,
  the verdict cell and the kill criterion are committed before a single return is computed. Changes are dated
  addenda, never rewrites; a change made after seeing returns is labelled post hoc and never replaces the registered
  verdict. Every non-obvious choice is a decision record in [`DECISIONS.md`](DECISIONS.md).
- **Statistics that do not flatter**: issuer-clustered standard errors (CR1) instead of iid t-statistics on
  overlapping events, yearly means with a t across years so that one busy year cannot carry a result, matched peers,
  and placebo windows that test whether the comparison itself is fair.
- **When the data invalidates a backtest** ([`docs/method/data-quality.md`](docs/method/data-quality.md)): a case
  study, drawn from work that is not published here and has no entry in the register of verdicts yet. A
  pre-registered small-cap backtest ran, a control on extreme one-day returns found vendor price errors inside it,
  and the run was marked invalid and not recorded. The cleaning rules were written before counting what they remove
  (one was then changed after its counts, and says so), the default behaviour of the data layer was left unchanged
  and checked, and the re-run was pre-registered again with a declaration of what had already been seen and a marker
  for conclusions that depend on the rule that was changed.
- **Coding agents** ([`docs/method/coding-agents.md`](docs/method/coding-agents.md)): most of the code, tests and
  documents were written by coding agents under standing instructions ([`CLAUDE.md`](CLAUDE.md)). Every rule that
  matters is either checked by code (boundary tests on the syntax tree, a test that every cited code line still holds
  the symbol the sentence names, a test that every cited decision record exists) or verified against the real state of
  the repository.

---

## Architecture

```mermaid
flowchart LR
  SEC[("SEC EDGAR<br/>Form 4, XBRL, filings")]
  YF[("Yahoo prices<br/>yfinance")]
  EOD[("EODHD archive<br/>licensed, outside the repo")]
  FED[("Federal Reserve<br/>FRED, ALFRED, EBP, GSW")]
  BULK[("SEC bulk files<br/>companyfacts, submissions")]
  ANT[("Anthropic API<br/>optional")]
  subgraph repo["edge-lab"]
    SC["form4_scanner/<br/>daily filter: facts, not judgements"]
    LLM["edgar_llm/<br/>LLM extraction, never decides"]
    MD["market-data/<br/>market_data.api"]
    TL["tools/<br/>statistics and backfill"]
    BT["backtest/<br/>pre-registered studies"]
    TS["tests/<br/>offline suites and AST boundary tests"]
  end
  SEC --> SC
  SEC --> LLM
  YF --> SC
  YF --> TL
  EOD --> MD
  FED --> MD
  BULK --> MD
  ANT --> LLM
  SC -- "optional report column" --> LLM
  TL --> SC
  BT --> TL
  BT --> SC
  BT -- "market_data.api only" --> MD
  TS -. "imports resolve inside the repo" .-> repo
  TS -. "only market_data.api outside market-data" .-> MD
  LLM -. "own perimeter guard" .-> LLM
```

The boundaries are tested, not just drawn:

- [`tests/test_confine_repo.py`](tests/test_confine_repo.py) reads the syntax tree of every Python file: each import
  resolves to the standard library, a module of this repository or a declared dependency; no user path is hard-coded;
  no script leaves the repository root.
- [`tests/test_market_data_confine.py`](tests/test_market_data_confine.py): outside `market-data/`, prices are read
  only through `market_data.api`, never through the archive's internal modules or files.
- `edgar_llm/tools/perimeter_check.py` guards the extraction package as a self-contained public perimeter (no
  e-mail addresses, absolute paths, keys, links that leave the package; private terms go in a `--deny-file`), with a
  positive fixture for every rule so that a broken pattern cannot pass silently.

More detail, with one diagram per flow (in Italian): [`docs/architecture/overview.md`](docs/architecture/overview.md).

---

## Data layer and data quality

`market-data/` is the only door to the data directory kept outside the repository (price archive, Fed downloads, SEC
bulk files); everything else imports `market_data.api` and nothing below it (a syntax-tree test enforces this). No
data are inside: the tests build the archives they read.

- **Prices** from a licensed end-of-day archive: raw responses kept compressed and never overwritten, Parquet
  partitions, DuckDB views, and a *clean* view that excludes the periods flagged by the quality checks.
- **Federal Reserve series** (`api.fred`, `api.ebp`, `api.gsw`): FRED as it is today, or, with `al_giorno`, the
  ALFRED vintage as it was read on a given day. A missing key or a missing vintage is an error, never a silent
  fallback to today's revised data, because that fallback would be lookahead. Every download is stored with its date.
- **SEC bulk files** (`api.sec_azioni`, `api.sec_bilancio`, `api.sec_societa`, `api.sec_depositi`): XBRL facts and
  filings read offline from `companyfacts.zip` and `submissions.zip`, every fact with its filing date. The reader
  makes no choices: all units, all filings, values as filed, scale errors included. Which observation counts on a
  given date is a rule of the study that reads it.
- **Three price-quality options, each explicit and opt-in.** Vendor data for small caps contain errors of specific
  shapes that ordinary checks miss, and each option answers one of them:
  `verifica_salti="azioni"` uses the shares outstanding filed with the SEC before and after a suspicious jump to tell
  a real crash from a split the vendor missed, so that a later crash no longer removes a company from a universe
  formed earlier; `barre_isolate="scarta"` drops a bar that goes and comes back (cents → hundreds of dollars → cents);
  `api.salti_di_livello()` lists closes that jump to five times the previous one and stay there with no split on
  record, typically new shares trading under an old code.

The default behaviour never changed: without the argument, `api.prices()` runs the same query as before and returns
exactly what it returned before, which was checked by fingerprinting its output over a real sample before and after
each change. The two cleaning rules (isolated bars, level jumps) were each written before counting what they remove;
the second was then modified after seeing its counts, and the decision record says so and keeps both versions. All
three use information that arrives after the bar in question (later bars, or shares filed later), so they are
corrections of the historical record, not real-time filters. The decision records (in Italian) are
`market-data/docs/adr/008` to `012`, the column-level reference is
[`market-data/DATA_DICTIONARY.md`](market-data/DATA_DICTIONARY.md), and the story of why the three options exist is in
[`docs/method/data-quality.md`](docs/method/data-quality.md).

The published studies E2 and E3 were run before these options existed and have not been re-checked with them: an
open debt, recorded as ADR-058 in [`DECISIONS.md`](DECISIONS.md).

---

## The Form 4 filter

A Form 4 row survives five conditions ([`form4_scanner/parse.py:217`](form4_scanner/parse.py#L217)):

```python
t.code == "P"                 # open-market purchase, not A (grant), M (exercise),
                              # F (tax withholding), G (gift), S (sale), C, D, X
and t.acquired_disposed == "A"
and not t.is_derivative       # the derivative table is a different animal
and not t.plan_10b5_1         # a scheduled plan buy is not a decision made today
and t.value >= min_value      # default $25,000
```

Most insider filings are not purchases: in the SEC bulk extract used as a test fixture (April-June 2022), code P is
15.8% of the non-derivative rows; grants, sales, option exercises and tax withholding make up most of the rest.

Two details that break naive parsers are handled explicitly:

- **10b5-1 detection has two paths.** The document-level checkbox only exists on filings after the December 2022
  amendments; older filings disclose the plan in a footnote, so there is a regex fallback over the footnotes and
  remarks ([`parse.py:153`](form4_scanner/parse.py#L153)). The flag is per document, so it taints every row of that
  filing.
- **Co-filers are one decision, not many.** Affiliated entities of the same fund filing the same purchase are one
  buyer, and the cluster logic unions them by accession before counting
  ([`cluster.py:34`](form4_scanner/cluster.py#L34)). On a live run one purchase of $64.8M was being read as $259.2M,
  once per co-signing entity.

What comes out is a `Card` per issuer with `score_v3`: four booleans, weight 1 each, no threshold
([`flags.py:190`](form4_scanner/flags.py#L190)). `cluster` (at least two buyer groups containing an opportunistic
insider, two buyers within 30 days), `director` (an independent director bought), `no_10pct` (no 10% owner among the
buyers), and `terreno`, which depends on an event index that is not distributed here and is therefore always `None`
in this repository: "not measured" stays distinguishable from "measured and false". The score is an ordering, not a
measure, and none of the booleans has been validated as a return filter.

**Why four booleans and no weights.** The first version scored each issuer out of 12 across seven criteria chosen by
judgement. Measured afterwards, higher scores did not pick better stocks
([`reports/rubric_discrimination.md`](reports/rubric_discrimination.md),
[`reports/backtest_v1.md`](reports/backtest_v1.md)). The rubric was removed rather than patched; a new component needs
a measurement cited in the code first.

**The dilution predicate.** An insider can buy on the open market a week before the company prices an offering. A
predicate over structured EDGAR data ([`dilution.py:223`](form4_scanner/dilution.py#L223)) labels that situation from
shelf registrations, 424B takedowns and share-count growth, with missing data labelled `UNKNOWN` and never `CLEAR`. It
is a predicate defined in advance, **not validated**: nothing in this repository shows that it separates returns.
The veto is **implemented and disabled until validated**: by default the verdict is computed and shown as a flag, and
no name is blocked or hidden (`EDGE_LAB_DILUTION_VETO=1` turns the historical behaviour back on).

**Routine buyers.** Following Cohen, Malloy and Pomorski (2012), an insider who buys in the same calendar month year
after year is classified as routine. The classifier walks the insider's own CIK history over rolling 12-month blocks
anchored on the transaction date ([`classify.py:51`](form4_scanner/classify.py#L51)); a CIK too young to have a history
is labelled `UNSEASONED`, not credited with "no history".

**Facts, not judgements.** The scanner computes booleans and numbers derived from EDGAR by join or count, each with a
declared rule; it does not weigh, interpret or recommend. Missing data is `UNKNOWN`. Every issuer evaluated is written
to an append-only archive with the scanner's git SHA, so a rule can be re-tested later against what it actually saw.
[`RULES.md`](RULES.md) lists every rule the scanner may apply, each citing the line that implements it.

---

## Reproducing the tests

Python 3.11 or later (development on 3.13). No network is needed to run the tests, and no key.

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt          # POSIX: .venv/bin/python
.venv/Scripts/python.exe -m pip install -e "./market-data[archivio]"
bash test.sh
```

`bash test.sh` runs, and reports together:

- every `tests/test_*.py` (flat suites on a small harness that records a failure and carries on);
- `pytest` for `edgar_llm/` (tests that call the Anthropic API carry the `llm` marker and are excluded by default);
- `pytest` for `market-data/` (no archive and no key needed: the tests build what they read);
- `backtest/test_studi.sh`, the study suites, on synthetic series only (tickers AAA, BBB, CCC).

Some checks need a git repository with at least one commit, because the observations archive records the scanner's
commit SHA. Setting `EDGE_LAB_STATE_DIR` points `tools/backtest_event_time.py`, and the studies that import it, at a
`state/` directory other than the repository's own (for example one holding synthetic price series).

What needs more than the fixtures:

| to do this | you need |
|---|---|
| run the scanner (`./run.sh`, `./daily.sh`) | network access to SEC EDGAR and a real User-Agent (`"Name email"`); no key |
| the LLM column and the live `edgar_llm` tests (`pytest -m llm`) | an Anthropic API key (`.env.example`) |
| download or update the price archive (`market-data/`) | a paid EODHD key; the data live outside the repository and are not redistributable |
| Fed series and SEC bulk readers (`market-data/`) | network access for FRED, a free FRED key for ALFRED vintages only; the two SEC bulk zips are downloaded by hand |
| regenerate the E2 and E3 verdicts | the licensed EODHD archive, plus EDGAR downloads |
| regenerate the insider re-test | the Form 4 corpus and XBRL from EDGAR (public) and a Yahoo price panel, not redistributed |
| the Fama-French factors | `python data/ff/fetch.py` (Kenneth R. French Data Library) |

Aggregate results of every study are kept in the repository as documents; per-security rows and price series are not.

---

## Repository layout

```
form4_scanner/        the Form 4 filter (edgar.py, parse.py, cluster.py, classify.py, dilution.py, flags.py, ...)
edgar_llm/            LLM extraction from filing text; enriches, never decides; its own ADRs and pytest suite
market-data/          data layer and typed API (no data inside): price archive client, Fed series (FRED, ALFRED,
                      EBP, GSW), SEC bulk readers, opt-in price-quality rules; its own ADRs and pytest suite
tools/                statistics (event-time backtest, matched control, CR1 regression) and backfill tools
backtest/             pre-registrations, addenda, code, results and STUDY.md pages of the published studies
reports/              measurement reports (the 2026-09-01 insider reports, rubric measurements, infrastructure notes)
docs/                 architecture, method (pre-registration, data quality, coding agents), bibliography
DECISIONS.md          decision records of the published studies, renumbered for this repository
.githooks/            pre-commit guard: blocks data files, .env, files over 5 MB and anything shaped like an API key
RULES.md              every rule the scanner applies, with the line that implements it
tests/                offline suites
config/               vehicles.json (public facts), watch.example.json
```

Code comments and working documents are mostly in Italian; this README and the study pages are in English.

---

## Known limits

1. **The window is a ceiling.** A transaction outside the scan window (60 days by default) is never collected, so the
   archive can be re-scored to a narrower window and never a wider one.
2. **`score_v3` has no calibrated threshold.** It orders; it does not classify.
3. **Market data in the scanner come from yfinance**, whose fields are sometimes wrong or missing; every cap is then
   unknown.
4. **The dilution predicate reads structured data only.** It will not see a deal negotiated but unfiled, or an equity
   line buried in an exhibit. The live path filters XBRL facts on `end`, not `filed`
   ([`dilution.py:163`](form4_scanner/dilution.py#L163)); point-in-time is the rule for the backtests only.
5. **10b5-1 detection is imperfect** for filings before the 2022 amendments.
6. **The on-disk EDGAR cache has no expiry.**

---

License: MIT, see [LICENSE](LICENSE).

*Not investment advice.*
