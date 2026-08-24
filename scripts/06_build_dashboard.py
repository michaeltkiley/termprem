"""
Build the yield-curve tracker HTML (3 tabs: yield curve evolution, term
premium, long-run implied level) from the latest (or a specified) run in
term_premium.duckdb, plus the raw yield snapshot and the SEP long-run fed
funds rate. Self-contained static page (see dashboard_template.html) --
open it directly in a browser, or publish it manually when a shareable
link is wanted.

Usage:
    python3 06_build_dashboard.py [--run-date YYYYMMDD] [--db PATH] [--out-dir DIR]
"""
import argparse
import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

from lib_data import build_merged, last_value_resample

TP_START = "1991-12-01"  # term-premium series start (matches the VAR's initial estimation window)
YC_START = TP_START  # same sample as the term-premium tab, for direct comparability across tabs
RSTAR_START = "2001-01-01"


def latest_snapshot_date(data_dir: Path) -> str:
    import glob
    import re
    dates = set()
    for kind in ["treasury_yields", "kim_wright", "acm"]:
        for f in glob.glob(str(data_dir / f"*_{kind}.csv")):
            m = re.match(r"(\d{8})_" + kind, Path(f).name)
            if m:
                dates.add(m.group(1))
    return max(dates)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-date", default=None, help="defaults to latest run in the database")
    ap.add_argument("--db", default="../data/term_premium.duckdb")
    ap.add_argument("--data-dir", default="../data")
    ap.add_argument("--out-dir", default="../output")
    ap.add_argument("--template", default="dashboard_template.html")
    ap.add_argument("--pages-out", default="../docs/index.html",
                     help="also write a stable copy here for GitHub Pages (fixed URL, not date-stamped)")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(args.db)
    run_date = args.run_date or con.execute("SELECT MAX(run_date) FROM term_premium_monthly").fetchone()[0]

    # --- term premium tab ---
    m = con.execute(f"""
        SELECT date, y10tp, dgs10, kw_tp10, acm_tp10
        FROM term_premium_monthly WHERE run_date = ? AND date >= '{TP_START}' ORDER BY date
    """, [run_date]).fetchdf()
    rec = con.execute("SELECT date, y10tp AS rec_tp, yend AS rec_yend FROM term_premium_recursive WHERE run_date = ? ORDER BY date", [run_date]).fetchdf()
    disc = con.execute("SELECT date, y10tp AS disc_tp, yend AS disc_yend FROM term_premium_discounted WHERE run_date = ? ORDER BY date", [run_date]).fetchdf()
    con.close()

    df = m.merge(rec, on="date", how="left").merge(disc, on="date", how="left")
    df["date"] = df["date"].astype(str)

    # --- yield curve tab: reload the raw merged/resampled monthly yields ---
    snapshot_date = run_date
    merged = build_merged(
        data_dir / f"{snapshot_date}_treasury_yields.csv",
        data_dir / f"{snapshot_date}_kim_wright.csv",
        data_dir / f"{snapshot_date}_acm.csv",
    )
    monthly_yields = last_value_resample(merged, "M")
    yc = monthly_yields.loc[monthly_yields.index >= YC_START, ["DGS3MO", "DGS2", "DGS5", "DGS10"]].dropna()
    yc_dates = yc.index.astype(str).tolist()

    # --- long-run implied level tab: SEP series, forward-filled onto the term-premium date grid ---
    sep_path = data_dir / f"{snapshot_date}_fedtarmdlr.csv"
    sep_on_grid = [None] * len(df)
    if sep_path.exists():
        sep = pd.read_csv(sep_path, parse_dates=["observation_date"]).set_index("observation_date")["FEDTARMDLR"]
        sep = sep.reindex(pd.DatetimeIndex(pd.to_datetime(df["date"])), method="ffill")
        sep_on_grid = [None if pd.isna(x) else round(float(x), 4) for x in sep]
    else:
        print(f"WARNING: {sep_path} not found -- run 04_fetch_fedtarmdlr.py. SEP series will be omitted.")

    payload = {
        "run_date": run_date,
        "as_of": df["date"].iloc[-1],
        "dates": df["date"].tolist(),
        "dgs10": [round(x, 4) for x in df["dgs10"]],
        "rec_tp": [round(x, 4) for x in df["rec_tp"]],
        "disc_tp": [round(x, 4) for x in df["disc_tp"]],
        "kw_tp": [round(x, 4) for x in df["kw_tp10"]],
        "acm_tp": [round(x, 4) for x in df["acm_tp10"]],
        "rec_yend": [round(x, 4) for x in df["rec_yend"]],
        "disc_yend": [round(x, 4) for x in df["disc_yend"]],
        "sep_fedtarmdlr": sep_on_grid,
        "rstar_start": RSTAR_START,
        "yc_dates": yc_dates,
        "yc_3mo": [round(x, 4) for x in yc["DGS3MO"]],
        "yc_2yr": [round(x, 4) for x in yc["DGS2"]],
        "yc_5yr": [round(x, 4) for x in yc["DGS5"]],
        "yc_10yr": [round(x, 4) for x in yc["DGS10"]],
    }

    template = Path(args.template).read_text()
    if "__DATA_JSON__" not in template:
        raise ValueError(f"{args.template} is missing the __DATA_JSON__ placeholder")
    html = template.replace("__DATA_JSON__", json.dumps(payload, separators=(",", ":")))

    out_path = out_dir / f"{run_date}_dashboard.html"
    out_path.write_text(html)
    print(f"Wrote {out_path} ({len(html)} bytes, {len(df)} tp rows, {len(yc_dates)} yc rows, as of {payload['as_of']})")

    if args.pages_out:
        pages_path = Path(args.pages_out)
        pages_path.parent.mkdir(parents=True, exist_ok=True)
        pages_path.write_text(html)
        print(f"Wrote {pages_path} (stable Pages copy)")


if __name__ == "__main__":
    main()
