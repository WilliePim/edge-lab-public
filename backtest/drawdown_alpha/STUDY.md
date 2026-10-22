# Drawdown track — Test F (early warning signals) and Test G (put spreads)

Two pre-registered tests on the same question: **can a long-only S&P 500 investor see a deep drawdown coming, or pay
for protection against it at a reasonable price?**

| test | question | verdict | report |
|---|---|---|---|
| F | Does a composite of five macro signals light up before recession drawdowns more often than chance? | **INCONCLUSIVE** | [`2026-10-01_referto_test_f.md`](2026-10-01_referto_test_f.md) |
| G | Do S&P 500 put spreads, bought when signals fire, cut the three worst drawdowns by a third at an acceptable cost? | **DOES NOT HOLD** (both budget versions) | [`2026-10-04_referto_test_g.md`](2026-10-04_referto_test_g.md) |

*Study page. The working documents in this folder are in Italian; this page is the English summary. Both reports
are marked as drafts for review: the verdicts were computed exactly as pre-registered and have not changed since.*

---

## Test F — early warning signals

### The claim being tested

Recessions are preceded by a familiar set of warnings: credit spreads widen, the short end of the yield curve
inverts, building permits fall, jobless claims rise, oil spikes. If these signals, combined, reliably fire *before*
the market's deep drawdowns, an investor could act on them.

### Design (pre-registered)

Written on 2026-09-30, before any result was computed
([`2026-09-30_preregistrazione_test_f.md`](2026-09-30_preregistrazione_test_f.md)). Decision records: ADR-059 …
ADR-067 and ADR-071 in [`DECISIONS.md`](../../DECISIONS.md). The rules for the five signals were fixed by the
user from the literature, with no optimisation.

| # | family | series | fires when |
|---|---|---|---|
| 1 | credit | excess bond premium (Gilchrist-Zakrajšek) | latest available EBP > 0 |
| 2 | rates | near-term forward spread (Engström-Sharpe 2018), from the Fed's GSW yield curve and the 3-month bill | 3-month forward rate 18 months ahead minus the 3-month rate < 0 |
| 3 | housing | building permits (PERMIT) | 3-month average < 12-month average |
| 4 | labour | initial jobless claims (ICSA) | 4-week average > 52-week average |
| 5 | oil | WTI monthly price | above the maximum of the previous 36 months (Hamilton 2003) |

- **Composite** = number of signals firing, 0 to 5; the verdict cell is composite ≥ 3, read at each month end.
- **Point in time.** Each series enters with its publication lag. PERMIT and ICSA use the vintage available on that
  day (ALFRED) where it exists; elsewhere the lags are conservative and declared.
- **Events.** S&P 500 drawdowns measured from the highest close of the previous 12 months, on `GSPC.INDX` from 1927.
  The verdict uses the six drawdowns associated with a recession in 1973-2025 (1980-02, 1980-11, 1990, 2000, 2007,
  2020).
- **Verdict.** All three criteria must hold:
  - (a) at least 2/3 of the recession drawdowns are hit;
  - (b) false alarms ≤ hits;
  - (c) the hit rate beats the 90th percentile of 1,000 random series with the same share of time "on" (seed
    20261001).

### Result

| criterion | rule | measured | outcome |
|---|---|---|---|
| (a) hits | ≥ 4 of 6 | **6 of 6** | holds |
| (b) false alarms | ≤ hits | **4** (plus 2 episodes of 2025 not yet judgeable) | holds |
| (c) random series | real rate > 90th percentile of random | real 1.000, 90th percentile **1.000**; 88.5% of random series strictly below | **fails** |

**Verdict: INCONCLUSIVE.** The composite fires before all six recession drawdowns, with 1 to 23 months of lead.
But it is on **26.4% of the time**, and a hit window is 24 months long. Under those conditions six windows placed at
random are all hit in 11.5% of random series, and five of six in the median. The signal hits everything, but no
more than chance would with the same time switched on.

A reading error in the GSW curve file (holiday rows marked `NA`) was found and fixed on 2026-10-04 (ADR-071). The
test was re-run: 6/6 hits, 4 false alarms, verdict unchanged. The closed report is not rewritten; the correction is a
dated note at its end.

---

## Test G — put spreads on the S&P 500

### The claim being tested

If the drawdown cannot be timed, maybe it can be insured: buy a put spread on the index, either always or when the
signals of Test F fire, and accept a small, steady cost to cut the depth of the worst falls.

### Design (pre-registered)

Written on 2026-10-04 and frozen before any return was computed
([`2026-10-04_preregistrazione_test_g.md`](2026-10-04_preregistrazione_test_g.md)); decision records ADR-072 …
ADR-074.

- **Instrument.** Put spread with strikes 5% and 25% below the index. It is priced with Black-Scholes, using VIX as
  the volatility and a 2% continuous dividend yield (0% as a sensitivity). Maturities of 3, 6, 9 and 12 months;
  period 1990-2025.
- **Entry rules.** Rule 2: composite ≥ 3. Rule 3: composite ≥ 3 and VIX below its median. Rule 4: the Faber rule
  (monthly close below the 10-month average). Read monthly, without look-ahead.
- **Budget, two versions with one verdict each.**
  - A: premium 1.5% of the portfolio at 3 months and 3% at 6-12 months, capped at 6% a year.
  - B: 3% per trade.
- **Verdict cells.** A = rule 3 × 12 months; B = rule 3 × 3 months. 32 combinations in all, 30 of them descriptive.
- **Verdict rule.**
  - HOLDS if the mean reduction of the three worst drawdowns of the unprotected portfolio (2007-09, 2000-02, 2020)
    is ≥ 1/3 **and** the cost is ≤ 1.5 points of annual return.
  - DOES NOT HOLD if the reduction is < 1/5 **or** the cost is > 3 points.
  - INCONCLUSIVE otherwise.

### Result

| version | cell | mean reduction of the three worst drawdowns | cost (points of annual return) | verdict |
|---|---|---:|---:|---|
| A | rule 3 × 12 months | 12.4% | −0.003 | **DOES NOT HOLD** |
| B | rule 3 × 3 months | 8.2% | +0.33 | **DOES NOT HOLD** |

In both cells the verdict comes from the reduction, not from the cost: the protection is cheap because it buys
little. The sensitivities (skew, dividend yield, intrinsic value) change no verdict.

**Descriptive, outside the verdict.** The only cell that clears both thresholds is Faber × 3 months in version B
(35.1% reduction, 1.14 points). It gets there by holding spreads on up to **358%** of the portfolio. With coverage
capped at 100% the reduction falls to 25.8%, below one third. For this reason the planned confirmation on 1928-1989
(Test H) was not started. In all, 177 series were looked at, 17 of them after the results and declared as such.

**Limit.** Option prices are modelled, not market quotes. Real puts under stress cost more, which would only make
the result worse.

---

## Reproducing

- **Code.** `test_f.py` (signals, composite, events, verdict), `eventi_f.py` (event lists), `episodi.py` (drawdown
  definition), `test_g_dati.py` (pricing, strikes, maturities), `test_g.py` (simulation, measures, verdicts), `dati.py`
  (FRED and Yahoo download for the earlier descriptive tests).
- **Data.**
  - Index closes come from the licensed end-of-day archive through `market_data.api` and are not redistributable.
  - The macro series (FRED, ALFRED, EBP, GSW) are public and read through `api.fred()`, `api.ebp()` and `api.gsw()`.
  - ALFRED needs a free `FRED_API_KEY` in the environment.
- **Tests** run on synthetic data, offline:
  - `python tests/test_f_curva.py` (the GSW reading fix);
  - `python tests/test_g_prezzi.py` (pricing);
  - `python tests/test_g_simulazione.py` (simulation).
- **Not in this folder.** Earlier descriptive tests of the same track (A, B: yield curve and credit spread as
  signals) and the shared protocol of 2026-09-23 are cited by the documents but not published here.
