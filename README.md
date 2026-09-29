# termprem — Yield Curve Tracker

Live at [michaeltkiley.github.io/termprem](https://michaeltkiley.github.io/termprem/),
linked from [michaeltkiley.github.io](https://michaeltkiley.github.io/).

Tracks Treasury par yields, the 10-year term premium (four methods: a
recursive real-time VAR, a discounted-least-squares VAR, Kim-Wright, and
ACM), and each VAR method's implied long-run short-rate level, updated
automatically Tuesday–Saturday mornings via GitHub Actions (see
`.github/workflows/update.yml`).

Term premium and long-run-level methodology follows Kiley, M. T. (2024),
"Why Have Long-Term Treasury Yields Fallen since the 1980s? Expected Short
Rates and Term Premiums in (Quasi-) Real Time," *The Journal of Fixed
Income*, 34(2), 5–21.

## Data download

The monthly estimates are published as a CSV, refreshed with the dashboard:

<https://michaeltkiley.github.io/termprem/termprem.csv>

For example, in Python: `pd.read_csv("https://michaeltkiley.github.io/termprem/termprem.csv", parse_dates=["date"])`.
In R: `read.csv("https://michaeltkiley.github.io/termprem/termprem.csv")`.

One row per month from December 1991, dated at the last trading day of the
month; the final row is the most recent day available. All values are in
percent.

| Column | Description |
|---|---|
| `yield_10y` | 10-year Treasury par yield (FRED DGS10) |
| `tp10_recursive_var` | 10-year term premium, recursive real-time VAR |
| `tp10_discounted_var` | 10-year term premium, discounted-least-squares VAR |
| `tp10_kim_wright` | Kim-Wright 10-year term premium, Federal Reserve Board |
| `tp10_acm` | ACM 10-year term premium, Federal Reserve Bank of New York |
| `longrun_level_recursive_var` | long-run short-rate level implied by the recursive VAR |
| `longrun_level_discounted_var` | long-run short-rate level implied by the discounted VAR |
| `sep_longrun_fed_funds` | FOMC SEP median longer-run fed funds rate (FRED FEDTARMDLR), held flat between releases |

Kim-Wright and ACM are the publishing institutions' own series, included
for comparison; cite those sources when using them, and check them for
the latest vintage. A blank means that source has not yet published a
value for that date. The file is overwritten on each update, so save a
copy if you need a fixed vintage. Please cite Kiley (2024) when using the
VAR estimates.

## Pipeline

```
scripts/01_fetch_treasury_yields.py   FRED: daily Treasury par yields
scripts/02_fetch_kim_wright.py         Federal Reserve Board: Kim-Wright model
scripts/03_fetch_acm.py                NY Fed: ACM term premium
scripts/04_fetch_fedtarmdlr.py         FRED: SEP long-run fed funds rate
scripts/05_build_estimates.py          builds VAR-based term-premium estimates
scripts/06_build_dashboard.py          builds docs/index.html from the template
```

Every fetch script pulls each source's full history on every run, so the
whole pipeline is stateless — a clean run from scratch reproduces the
current dashboard. `data/` and `output/` are gitignored (regenerated on
every run); `docs/index.html` is the only generated file committed, since
that's what GitHub Pages serves.

To run locally:

```
cd scripts
python3 01_fetch_treasury_yields.py && python3 02_fetch_kim_wright.py && \
  python3 03_fetch_acm.py && python3 04_fetch_fedtarmdlr.py && \
  python3 05_build_estimates.py --force && python3 06_build_dashboard.py
```
