# When the data invalidates a backtest

A case study from October 2026. A pre-registered backtest on US small caps ran to completion, a routine control found
vendor price errors inside it, and the run was thrown away instead of being explained away. This page describes what
was found, what was done about it, and what was left unsolved. It is about the data layer and the method. The study
has no entry yet in the project's register of verdicts and is not part of this repository. Nothing here describes its
rules or its results, and nothing about its outcome should be read into its absence.

The decision records are in Italian, in [`market-data/docs/adr/`](../../market-data/docs/adr/):
[ADR 010](../../market-data/docs/adr/010-verifica-salti-con-le-azioni.md) (share-based verification of suspicious
jumps), [ADR 011](../../market-data/docs/adr/011-barre-isolate.md) (isolated bars),
[ADR 012](../../market-data/docs/adr/012-salti-di-livello.md) (unexplained level jumps), and the debt recorded as
ADR-058 in [`DECISIONS.md`](../../DECISIONS.md).

## 1. The setting

The backtest used a universe of about 2,000 US small caps, rebuilt point-in-time for 2017-2026 from a licensed
end-of-day price archive and SEC filings. It had a pre-registration: rules, comparisons and verdict criteria written
and committed before any return was computed ([`preregistration.md`](preregistration.md)).

Prices came from the archive's *clean* view, which already applied the quality checks of the data layer: missing
splits, repeated zero volume, and "suspicious jumps" (a one-day move close to a typical split ratio, with no split on
record and no reversal). A flagged, unverified period is excluded from the clean prices.

## 2. A first problem, found by counting

The first stop of a study produces counts only. Those counts showed that the clean view had a look-ahead built into
it: an unverified suspicious jump removes the whole history of a ticker *before* the jump, so a company that later
has a genuine one-day crash of about one half, two thirds or three quarters has no clean price on the earlier date
when the universe is formed, and silently drops out of it. Membership depended on the future. Depending on the year,
between 23 and 172 companies were lost this way.

The fix was a new verification, written before the first run: compare the shares outstanding filed with the SEC before
and after the jump. If the share count is unchanged the price move was real and the history comes back; if it changed
by the inverse of the jump it was a split the vendor missed and the history stays out; anything else stays "not
determinable" and excluded, and has to be counted and declared by whoever uses the option (ADR 010).

## 3. The control that found the rest

After the run, one control looked at every one-day return of a held name at or beyond +100% or -50%. There were 825 in
ten years, and **701 of them carried no data-quality flag at all**. Reading the largest ones was enough:

- **Isolated bars.** A stock closes at a few tens of cents, then at several hundred dollars on a volume of a few
  shares, then back at the first price the next day. The existing check could not see it: a suspicious jump is by
  definition a jump that does *not* come back.
- **Ticker changes chained to a different security.** The backtest chained a ticker to its successor so that a
  renamed company kept its position. Of a few hundred links followed, about four in ten did not lead to the same
  security: preferred shares, warrants, new shares issued after a reorganisation.
- **Unexplained level jumps.** Among the twenty one-day rises of ten times or more that were *not* isolated bars, in
  fifteen the new level persisted: a code that goes from a few cents to tens of dollars and stays there, with no
  split on record. These are new shares trading under the old code after a reorganisation, or reverse splits the
  vendor did not adjust. Nobody earned those returns.

## 4. The run was invalidated, not adjusted

The errors were large enough to change the outcome of a pre-registered comparison. At that point there are two
options. One is to patch the worst cases, re-run, and report the new numbers as the result. The other is to say that
the run measured the data errors and not the question, mark it invalid, and **not record its outcome** anywhere a
later reader could mistake it for a result. The second was chosen. The results of the invalid run were not entered in
the project's register of verdicts.

What cannot be undone is that those results had been *seen*. Everything that follows is built around that fact.

## 5. Rules written before counting what they remove

Two of the three corrections live in the data layer next to the share-based verification of §2. Each was written
down in a decision record, with thresholds, **before counting what it would remove**, and each record states what had
already been seen when it was written. The order is declared in each record; rule and counts were committed together,
so the commit history does not prove it.

- **Isolated bars** (ADR 011). A bar is discarded when its adjusted close is more than 50% away from *both*
  neighbouring bars, on the same side, the neighbours are within ten calendar days, and the next bar is back within
  10% of the previous one. Variants that also use volume were written at the same time and counted next to the main
  rule; the main rule was adopted exactly as written, and the variants stayed in the counts. It removes 114 of the 825
  extreme returns, and 73 bars out of about 4.9 million stock-days in that universe.
- **Unexplained level jumps** (ADR 012). A raw close at five times the previous one or more, with no recorded split of
  a compatible factor on that date, where the next five bars stay within 50% of the new level. The function returns a
  list; it removes nothing from the prices, because the prices after the jump are real prices of something else.
  This is the adopted form; the form written before counting was symmetric (see §9).

A third rule lives in the study's own code, not in the data layer: a series continues across a ticker change only when
it is demonstrably the same security, and otherwise ends there. A real ticker change that the vendor did not link is
then treated as the end of the series: a known cost, accepted in advance.

## 6. The default did not change, and that was checked on real data

Closed studies had used the clean view as it was. Changing its behaviour would have changed their numbers silently, so
all three data-layer rules are **explicit options that nobody gets by accident**; without the argument `prices()` runs
the same query as before:

```python
api.prices(symbols, verifica_salti="azioni")     # ADR 010: readmit history before a verified real move
api.prices(symbols, barre_isolate="scarta")      # ADR 011: drop isolated bars
api.salti_di_livello(symbols)                     # ADR 012: list unexplained level jumps
```

"Unchanged" is a claim, so it was tested on real data and not only on fixtures: for each rule, the default
`api.prices()` was run on a sample of about 1,500 US common stocks drawn for that rule (a systematic draw for the
first, a seeded random draw for the other two; 1.8 to 1.9 million rows each) with the module as of the previous commit
and with the modified module, and the row fingerprints were compared. They are identical. The unit tests assert the
same thing row by row on synthetic archives, before and after the option has been used in the same process, and that
nothing is written to the archive.

## 7. A second pre-registration that says what it knows

The backtest was run again under a second pre-registration. It differs from the first in three rules (isolated bars,
level jumps, ticker changes) and nothing else, and it declares that it is **not blind**: the results of the first run
had been seen, and the rules were written afterwards. What justifies the rules is therefore not their effect on the
outcome but the data: a price of several hundred dollars between two prices of a few cents is wrong whatever it does
to a comparison. A reader is entitled to discount the second run for this, and the document tells them so.

## 8. A pre-registered robustness marker

One of the three rules, the level-jump rule, was changed after its counts had been seen, so the second
pre-registration fixed in advance how to show whether a conclusion depends on that rule. The backtest is computed
three times: with the adopted level-jump rule, with the rule read to the letter (both directions, no exemption), and
without the rule. If the outcome of a comparison under the adopted rule differs in either diagnostic variant, the
report must print **FRAGILE** next to it. The verdict stays the one from the pre-registered main version; the marker
tells the reader how much weight it can bear.

The marker covers that rule only. The isolated-bar rule has a descriptive comparison with no pre-registered weight,
and the ticker-change rule has none: for those two the reader has only the declaration that they were written after
results had been seen.

## 9. The parts that did not go cleanly

- **One rule was changed after seeing counts.** The level-jump rule was first written symmetric (a ratio of five or
  more, *or* one fifth or less), before counting. The counts showed 80 jumps, 18 rises and 62 falls, and the falls
  were mostly real: more than half of all the jumps had over a million shares traded that day, and ten were moves the
  share-based verification had already confirmed as genuine. A cleaning rule that deletes real crashes introduces a
  bias of its own. The rule was changed to rises only, with an exemption for verified real moves, and the change is
  recorded with its date and its reason in ADR 012, which keeps the original text and its counts below the adopted
  version. The symmetric version remains available as an explicit variant, and it is one of the two diagnostics of
  the robustness marker.
- **The adopted rule catches things that are not errors.** Nine of the 18 jumps it flags are reverse splits that *are*
  on record, caught because the stock also moved by more than 25% on the split day and the tolerance on the split
  factor, written before counting, was ±25%. This was found while counting, declared, and not corrected, because the
  rule was the approved one.
- **Known residual errors.** Eleven rises of ten times or more escape every rule (tickers that end within five bars
  of the jump, levels that oscillate, errors in the adjustment factor alone). Errors on the downside, such as an
  acquired company whose code goes on trading at a few cents, are left in the data by design. A series that
  alternates between two price levels is shortened by the isolated-bar rule, not repaired.
- **These are corrections after the fact.** The isolated-bar and level-jump rules use later bars, and the share-based
  verification uses filings made after the jump. They answer "did this price ever exist?", not "where will the
  price go?", and they are legitimate in a backtest only if the discarded bar disappears for every use. None of them
  is a real-time filter, and the last bar of any series can never be checked.
- **A debt on closed studies.** The published studies E2 and E3 read the same clean view and used none of these
  options. That is recorded as an open debt (ADR-058 in `DECISIONS.md`): nothing has been re-checked or re-run, and
  their verdicts stand with that reservation stated.

## 10. What carries over

1. A control on extreme one-day returns is cheap and should run before any result is read, not after.
2. "Clean" is a property of a check, not of the data. A check that looks for jumps without reversal says nothing about
   bars that reverse.
3. When data errors move a result, the run is invalid. Its outcome is not a result with a caveat.
4. A data rule gets written, with its thresholds, before anyone counts what it removes; if it changes afterwards, the
   change is dated and the first version stays on the page.
5. A data layer that other studies depend on changes behaviour only on request, and "the default is unchanged" is
   checked on real data.
6. If the people writing a correction have seen results, say so, and pre-register a test of whether the conclusion
   depends on the correction, for every rule and not only for one.
