# Fama-French factors

The monthly factors used by
`reports/cmp_calendar_time_long.md` / `reports/table3-regression-2026-09-01.md` come from the
**Kenneth R. French Data Library** (Tuck School of Business at Dartmouth):
<https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html>.

They are **not redistributed here**. Download them on demand:

```
python data/ff/fetch.py
```

This writes `ff3.zip` (Fama/French 3 Factors, monthly) and `mom.zip` (Momentum Factor, monthly)
next to the script. Both are ignored by git (`data/ff/.gitignore`). The copies used for the
reports in this repo were downloaded on 2026-08-03; the library revises its history from time to
time, so a fresh download can move the last decimals of the regressions.

Credit: Eugene F. Fama and Kenneth R. French, data provided by Kenneth R. French.
