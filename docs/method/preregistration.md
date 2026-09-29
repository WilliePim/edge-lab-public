# Pre-registration: template and verdict rules

How a study is set up in this repository, distilled from the pre-registrations published here: the insider re-test
(`backtest/2026-09-15_preregistration.md` and its addenda), the Russell 2000 exits study
(`backtest/russell_exits/2026-09-16_preregistrazione.md`) and the IPO study
(`backtest/ipo_e3/2026-09-22_preregistrazione.md`). The originals are in Italian; the verdict labels map as
**REGGE → holds**, **INCONCLUSIVO → inconclusive**, **NON REGGE → does not hold**. The numbers used as examples below
come from those three studies; each new study fixes its own before looking at any return.

## 1. The rules that do not change

1. **Written before any return.** The pre-registration is committed before a single post-event return is computed or
   looked at. The commit that contains it freezes it, together with the code commit it names.
2. **Never rewritten.** After the freeze, a change is a new dated file (an *addendum*) that says what it replaces, and a
   dated decision record (ADR) next to it. The original text stays as it was, with an errata line if it cites something
   wrong.
3. **Addenda only before the returns.** An addendum that changes a rule, a threshold, a population or a verdict
   criterion is valid only if it is committed before the returns it would affect. A change made after seeing returns is
   labelled **post hoc**: it can be reported as descriptive, it never replaces the registered verdict, and replacing
   it is an explicit decision of the person who owns the study.
4. **Declare what is already known.** Any result already seen (an earlier report, a replication elsewhere, an
   exploratory table) is listed with its numbers in a section of its own: the test is not blind to it, and the reader
   must know.
5. **Freeze the data too.** Inputs that live outside git are fingerprinted (sha256 of each file, or of the ordered list
   of `name + sha256` for a directory) in the pre-registration.
6. **One verdict cell per question.** Each question has exactly one cell (entry rule × horizon × comparison) that
   decides the verdict. Every other cell is descriptive and says so.
7. **Everything listed is computed, and nothing else.** The pre-registration lists every table that will be produced,
   "even if the numbers are unwelcome", and lists what will *not* be computed.

## 2. Template

Copy the sections below into `backtest/<study>/<date>_preregistration.md` and fill them in.

```markdown
# Pre-registration — <study>

Written on <date>, before computing or looking at any post-event return.
Code at commit <sha>; the commit containing this file freezes it. Decisions: DECISIONS.md, ADR-<n> onwards.
A change after the first computed return is a new dated file, never a rewrite.

## 0. Data fingerprints
| input | sha256 | size / last bar |

## 1. Questions and verdicts
The questions, in the words of the directive.
For each question: the verdict cell, its placebo, and the verdict criteria (§3 of the method).
The order in which the criteria are applied, written out, with the edge cases read literally.

## 2. What is already known, and therefore not blind
Earlier results with their numbers and sources.

## 3. Event definition
Universe, event, date of knowledge (filing date, never transaction or period date), exclusions, entry rule
(first bar strictly after publication), exit rule, return definition, artefact rules, delisting treatment.
Where the event is reproduced from existing code: file and line of every element.

## 4. Controls
Peer universe; matching variables and distance; ties (deterministic, no seed); reuse of peers; placebo windows and
why each is valid for each matching; the calendar the legs are measured on.

## 5. Population, coverage and survival
Funnel counts (no returns). Coverage of the verdict cell. What happens to cases whose series ends inside the window,
and the survival scenarios reported next to the verdict.

## 6. Power
MDE = (1.96 + 0.84) · sd/√n · √DEFF, with the sd taken from earlier reports, not from this test.
What a "does not hold" or "inconclusive" can and cannot say at this power.

## 7. Stops
Stop 1: counts, coverage, cases per cell; no return computed. Decisions required from the study owner, listed.
Validation gates with their thresholds (see §4 of the method). Reproduction gate, if the study re-runs earlier code.
Stop 2: returns, controls, verdict, report.

## 8. Everything that will be computed
Numbered list. Then: what will not be computed.

## 9. Deviations from the directive, declared before the results
| point of the directive | what is done | why |

## 10. What this test cannot do, known in advance

## 11. Budget
External calls (with the cap enforced in code), disk space, LLM calls (usually zero).
```

## 3. Verdict rules

Two families of criteria are used in the published studies. Both are fixed in the pre-registration, together with
the order in which their conditions are checked.

### 3.1 Event-level mean with clustered inference (insider re-test)

For the verdict cell, excess return against the primary matched control:

- **Holds** if the mean is > 0 **and** the 95% confidence interval excludes 0 **and** the placebo is ≈ 0.
- **Does not hold** if the mean is ≤ 0, **or** the interval includes 0 **and** the placebo is not ≈ 0.
- **Inconclusive** in the cases the two rules above do not cover, named in advance: mean > 0 with the interval
  excluding 0 but a failed placebo (*biased matching*), and mean > 0 with the interval including 0 and a clean placebo
  (*under-powered*).

Operational definitions, fixed in advance:

- **Interval.** Mean ± t(G−1; 0.975) · SE_CR1, with standard errors clustered by issuer:
  V = G/(G−1) · Σ_g (Σ_{i∈g} (x_i − x̄))² / N². A cluster bootstrap by issuer is reported next to it; a disagreement on
  zero is reported but does not change the verdict.
- **Placebo ≈ 0** ⟺ the CR1 interval of the placebo includes 0 **and** |mean| < 1.5 percentage points. A wide,
  non-significant placebo with a large mean is not ≈ 0.
- **Placebo windows** must be valid for the matching they judge: a placebo window that falls inside a matching
  variable (for example a past-return window used for momentum matching) tends to zero by construction and cannot
  judge that matching.
- **Ordered verdict table.** When several matchings, placebos and survival scenarios interact, the verdict is an
  ordered table of rules (R0, R1, …) applied top to bottom; the placebo selects the reference matching only among
  matchings whose placebo is ≈ 0, and a stricter matching (for example size + momentum) can veto a "holds".
- **Survival.** Cases that stop trading inside the window are carried at their last price; named scenarios (for
  example −100%, 0 excess, +15%) are applied to the cases that cannot be observed. If the sign of the result changes
  between scenarios the pre-registration says in advance what that means (in the re-test: inconclusive).
- **Coverage.** A secondary criterion can make the verdict inconclusive on coverage alone (in the Swedish replication
  criterion copied as secondary: coverage < 60% → inconclusive), and that is computed and written before any return.

### 3.2 Cohort-year means (Russell 2000 exits, IPO study)

For the verdict cell (entry rule × 252 sessions against a peer average):

- **Holds** if all are true:
  1. at least *N* cases and at least *Y* cohort years with cases (100 and 9 in the Russell study, 80 and 8 in the IPO
     study);
  2. median excess return > 0;
  3. mean of the yearly means > 0, with the t statistic across years ≥ 2 (degrees of freedom = years − 1);
  4. mean > 0 in both pre-declared sub-periods;
  5. placebo with |t| < 2 and a mean lower than the verdict cell.
- **Inconclusive** if condition 2 holds and the mean of the yearly means is > 0, but the t across years is between 1
  and 2, or condition 1 is not reached.
- **Does not hold** in every other case.

Checked in this order: holds (1-5 all true), else inconclusive, else does not hold. Read literally: with t ≥ 2 but
condition 4 or 5 false, the result is *does not hold*.

The per-year table is always reported. When two questions are designed to be opposite (as in the IPO study), both
holding is treated as a sign of a design problem, to be discussed before any conclusion.

## 4. Gates and stops

- **Stop 1, counts only.** Funnel, coverage, cases per cell and per year, entry-day distributions: no excess return
  is computed. The study owner confirms or takes the open decisions; the decisions go into a dated addendum; from there
  rules and thresholds do not move.
- **Validation gates before use.** A classifier, a document parser or a data correction is validated on a seeded random
  sample with labels read from the documents and committed *before* the tool's output is opened. Below the
  pre-registered threshold (90% in the published studies) the tool is not used, and the fall-back is the one written
  in advance. A failed validation is not fixed by tuning on the validation sample: that needs a new addendum and a new
  sample.
- **Reproduction gate.** When a study re-tests an earlier result, step 1 re-runs the original code unchanged and must
  reproduce the printed numbers exactly; otherwise the study stops until the difference is explained.
- **Manual check of extracted fields.** For fields read from documents with fixed rules, a manual check on a random
  sample (30 documents in the IPO study); below 90% precision on a field, the study stops.
- **Budgets enforced in code.** External calls have a persistent counter with a cap; a call beyond the cap does not
  start, and the missing document sends the case to a declared fall-back with a flag. Disk space is checked before and
  during bulk downloads.
- **Sensitivity only after a "holds".** Threshold sensitivities are computed only if the primary verdict holds; if the
  sign changes with the threshold, the result is the threshold.

## 5. Point-in-time and lookahead

- Every fact is taken with its **filing date** ≤ the decision date, never the period end date.
- Entry is the first bar strictly after publication; no leg ever uses a price that precedes publication.
- Entry rules that look at prices and volumes get a mandatory test: no price or volume after the entry session may
  change the entry.
- Peers are chosen without looking at their future prices; conditions on the future (for example "no insider purchase
  in the next 12 months") are lookahead and may only appear as a declared sensitivity.

## 6. The report

The verdict report quotes the pre-registered criteria verbatim and applies only those. It gives the verdict first,
then the numbers, then the declared limits. Negative and inconclusive results are published with the same structure
as positive ones.
