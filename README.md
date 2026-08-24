# termprem — Yield Curve Tracker

Live at [michaeltkiley.github.io/termprem](https://michaeltkiley.github.io/termprem/),
linked from [michaeltkiley.github.io](https://michaeltkiley.github.io/).

Tracks Treasury par yields, the 10-year term premium (four methods: a
recursive real-time VAR, a discounted-least-squares VAR, Kim-Wright, and
ACM), and each VAR method's implied long-run short-rate level, updated
automatically on weekday mornings via GitHub Actions (see
`.github/workflows/update.yml`).

Term premium and long-run-level methodology follows Kiley, M. T. (2024),
"Why Have Long-Term Treasury Yields Fallen since the 1980s? Expected Short
Rates and Term Premiums in (Quasi-) Real Time," *The Journal of Fixed
Income*, 34(2), 5–21.

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
