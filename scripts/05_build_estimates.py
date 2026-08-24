"""
Build VAR-implied term premium estimates from the latest fetched data and
store them in DuckDB, alongside the Kim-Wright and ACM series for
comparison. Methodology (lag lengths, horizons, window lengths) matches
../replication_scripts, which was numerically validated against the
original MATLAB replication package.

Idempotent per run_date: rerunning with the same --date is a no-op unless
--force is passed (existing rows for that run_date are replaced).

Usage:
    python3 05_build_estimates.py [--date YYYYMMDD] [--data-dir DIR]
                                   [--db PATH] [--force]
                                   [--check-against-replication]
"""
import argparse
import glob
import re
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from lib_data import build_merged, last_value_resample
from lib_var import estim_boot, horizon_forecast_row0, window_tp_endpoint
from lib_discounted import window_tp_endpoint_weighted, RHO as DISCOUNT_RHO

WEEKLY_VLAG = 12
MONTHLY_VLAG = 3
WEEKLY_HORIZONS = [53, 105, 157, 52 * 4 + 1, 52 * 5 + 1, 52 * 6 + 1, 52 * 7 + 1, 52 * 8 + 1, 52 * 9 + 1]
MONTHLY_HORIZONS = [13, 25, 37, 49, 61, 73, 85, 97, 109]
YIELD_COLS = ["DGS1", "DGS3", "DGS5", "DGS7", "DGS10"]
SAMPLE_START = "1962-01-01"
ROLL_WINDOW_START, ROLL_WINDOW_END = "1962-01-01", "1991-12-31"


def latest_snapshot_date(data_dir: Path) -> str:
    dates = set()
    for kind in ["treasury_yields", "kim_wright", "acm"]:
        for f in glob.glob(str(data_dir / f"*_{kind}.csv")):
            m = re.match(r"(\d{8})_" + kind, Path(f).name)
            if m:
                dates.add(m.group(1))
    if not dates:
        raise FileNotFoundError(f"No fetched snapshots found in {data_dir}")
    return max(dates)


def build_Y(X: np.ndarray) -> np.ndarray:
    Y = np.empty((X.shape[0], 4))
    Y[:, 0] = X[:, 0]
    Y[:, 1] = X[:, [0, 1, 2, 4]].mean(axis=1)
    Y[:, 2] = X[:, 4] - X[:, 0]
    Y[:, 3] = X[:, 2] - 0.5 * (X[:, 0] + X[:, 4])
    return Y


def run_full_sample(df: pd.DataFrame, vlag: int, horizons) -> pd.DataFrame:
    X = df[YIELD_COLS].to_numpy(dtype=float)
    dates = df.index
    Y = build_Y(X)
    Ymean = Y.mean(axis=0)
    Yd = Y - Ymean

    Bcomp, Xmat = estim_boot(Yd, vlag)
    forecasts = horizon_forecast_row0(Bcomp, Xmat, horizons)

    y10proj = Yd[vlag:, 0].copy()
    for h in horizons:
        y10proj = y10proj + forecasts[h]
    y10proj = y10proj / 10 + Ymean[0]
    y10tp = X[vlag:, 4] - y10proj

    out = pd.DataFrame({"DATE": dates[vlag:], "y10proj": y10proj, "y10tp": y10tp}).set_index("DATE")
    return out.join(df[["THREEFYTP1000_B", "ACMTP10", "DGS10"]])


def run_windowed(df: pd.DataFrame, vlag: int, horizons, expanding: bool) -> pd.DataFrame:
    X = df[YIELD_COLS].to_numpy(dtype=float)
    dates = df.index
    window_len = ((df.index >= ROLL_WINDOW_START) & (df.index <= ROLL_WINDOW_END)).sum()

    records = []
    for end_idx in range(window_len - 1, len(X)):
        Xw = X[: end_idx + 1, :] if expanding else X[end_idx - window_len + 1 : end_idx + 1, :]
        y10proj, y10tp, yend = window_tp_endpoint(Xw, vlag, horizons)
        records.append((dates[end_idx], y10proj, y10tp, yend))
    return pd.DataFrame(records, columns=["DATE", "y10proj", "y10tp", "yend"]).set_index("DATE")


def run_discounted(df: pd.DataFrame, vlag: int, horizons) -> pd.DataFrame:
    """Recursive (expanding-window), geometrically discounted least squares
    -- rho = DISCOUNT_RHO fixed to a 30-year effective window. See
    lib_discounted.py and ../research/ for how rho was chosen."""
    X = df[YIELD_COLS].to_numpy(dtype=float)
    dates = df.index
    window_len = ((df.index >= ROLL_WINDOW_START) & (df.index <= ROLL_WINDOW_END)).sum()

    records = []
    for end_idx in range(window_len - 1, len(X)):
        Xw = X[: end_idx + 1, :]
        y10proj, y10tp, yend = window_tp_endpoint_weighted(Xw, vlag, horizons, DISCOUNT_RHO)
        records.append((dates[end_idx], y10proj, y10tp, yend))
    return pd.DataFrame(records, columns=["DATE", "y10proj", "y10tp", "yend"]).set_index("DATE")


def store(con, table: str, df: pd.DataFrame, run_date: str, force: bool):
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            run_date VARCHAR, date DATE, y10proj DOUBLE, y10tp DOUBLE,
            dgs10 DOUBLE, kw_tp10 DOUBLE, acm_tp10 DOUBLE, yend DOUBLE
        )
    """)
    existing = con.execute(f"SELECT COUNT(*) FROM {table} WHERE run_date = ?", [run_date]).fetchone()[0]
    if existing and not force:
        print(f"{table}: run_date {run_date} already present ({existing} rows), skipping (use --force)")
        return
    con.execute(f"DELETE FROM {table} WHERE run_date = ?", [run_date])

    frame = df.reset_index().rename(columns={
        "DATE": "date", "THREEFYTP1000_B": "kw_tp10", "ACMTP10": "acm_tp10", "DGS10": "dgs10",
    })
    frame["run_date"] = run_date
    for col in ["y10proj", "y10tp", "dgs10", "kw_tp10", "acm_tp10", "yend"]:
        if col not in frame.columns:
            frame[col] = np.nan
    con.execute(f"INSERT INTO {table} SELECT run_date, date, y10proj, y10tp, dgs10, kw_tp10, acm_tp10, yend FROM frame")
    print(f"{table}: wrote {len(frame)} rows for run_date {run_date}")


def check_against_replication(estimates: dict, repl_dir: Path):
    """Roll/recursive windows never see data beyond their own endpoint, so
    historical values should be exactly reproducible regardless of how much
    later data has since been appended -> tight tolerance. Monthly/weekly
    are full-sample estimates, so appending new data legitimately shifts
    the OLS coefficients and nudges every historical value by a small,
    expected amount -> report drift, not a pass/fail tolerance."""
    print("\n--- consistency check vs. validated replication_output (overlap period) ---")
    exact = [("roll", "var_tp_roll_results.parquet", 1e-6),
             ("recursive", "var_tp_recursive_results.parquet", 1e-6)]
    drifting = [("monthly", "var_tp_m_results.parquet"), ("weekly", "var_tp_w_results.parquet")]

    for label, fname, tol in exact:
        ref_path = repl_dir / fname
        if not ref_path.exists():
            print(f"{label}: {ref_path} not found, skipping")
            continue
        ref = pd.read_parquet(ref_path)
        mine = estimates[label]
        common = mine.index.intersection(ref.index)
        diff = (mine.loc[common, "y10tp"] - ref.loc[common, "y10tp"]).abs()
        status = "OK (exact, as expected)" if diff.max() < tol else "MISMATCH -- investigate"
        print(f"{label}: {len(common)} overlapping dates, max |diff| = {diff.max():.2e} -> {status}")

    for label, fname in drifting:
        ref_path = repl_dir / fname
        if not ref_path.exists():
            print(f"{label}: {ref_path} not found, skipping")
            continue
        ref = pd.read_parquet(ref_path)
        mine = estimates[label]
        common = mine.index.intersection(ref.index)
        diff = (mine.loc[common, "y10tp"] - ref.loc[common, "y10tp"]).abs()
        note = "OK" if diff.max() < 0.05 else "LARGER THAN EXPECTED -- investigate"
        print(f"{label} (full-sample, expected to drift as new data is appended): "
              f"{len(common)} overlapping dates, max |diff| = {diff.max():.4f} -> {note}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="snapshot date YYYYMMDD; defaults to latest fetched")
    ap.add_argument("--data-dir", default="../data")
    ap.add_argument("--db", default="../data/term_premium.duckdb")
    ap.add_argument("--out-dir", default="../output")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check-against-replication", action="store_true")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    run_date = args.date or latest_snapshot_date(data_dir)
    print(f"Building estimates for run_date {run_date}")

    merged = build_merged(
        data_dir / f"{run_date}_treasury_yields.csv",
        data_dir / f"{run_date}_kim_wright.csv",
        data_dir / f"{run_date}_acm.csv",
    )
    monthly_data = last_value_resample(merged, "M")
    weekly_data = last_value_resample(merged, "W-WED")

    m = monthly_data.loc[monthly_data.index >= SAMPLE_START]
    w = weekly_data.loc[weekly_data.index >= SAMPLE_START]

    monthly_est = run_full_sample(m, MONTHLY_VLAG, MONTHLY_HORIZONS)
    weekly_est = run_full_sample(w, WEEKLY_VLAG, WEEKLY_HORIZONS)
    roll_est = run_windowed(m, MONTHLY_VLAG, MONTHLY_HORIZONS, expanding=False)
    recursive_est = run_windowed(m, MONTHLY_VLAG, MONTHLY_HORIZONS, expanding=True)
    discounted_est = run_discounted(m, MONTHLY_VLAG, MONTHLY_HORIZONS)

    con = duckdb.connect(args.db)
    store(con, "term_premium_monthly", monthly_est, run_date, args.force)
    store(con, "term_premium_weekly", weekly_est, run_date, args.force)
    store(con, "term_premium_roll", roll_est, run_date, args.force)
    store(con, "term_premium_recursive", recursive_est, run_date, args.force)
    store(con, "term_premium_discounted", discounted_est, run_date, args.force)
    con.close()

    monthly_est.to_csv(out_dir / f"{run_date}_term_premium_monthly.csv")
    weekly_est.to_csv(out_dir / f"{run_date}_term_premium_weekly.csv")
    roll_est.to_csv(out_dir / f"{run_date}_term_premium_roll.csv")
    recursive_est.to_csv(out_dir / f"{run_date}_term_premium_recursive.csv")
    discounted_est.to_csv(out_dir / f"{run_date}_term_premium_discounted.csv")

    print("\nLatest monthly estimate:")
    print(monthly_est.tail(3))

    if args.check_against_replication:
        estimates = {"monthly": monthly_est, "weekly": weekly_est, "roll": roll_est, "recursive": recursive_est}
        check_against_replication(estimates, Path("../replication_output"))


if __name__ == "__main__":
    main()
