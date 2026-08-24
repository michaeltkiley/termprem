"""
Fetch the SEP longer-run federal funds rate median (FEDTARMDLR) from FRED
-- used on the "Long-Run Implied Level" tab as a benchmark for the VAR
methods' implied long-run short-rate level.

Usage:
    python3 04b_fetch_fedtarmdlr.py [--date YYYYMMDD] [--force]
"""
import argparse
from datetime import date
from pathlib import Path

from lib_fetch import fetch_if_missing

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDTARMDLR"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    ap.add_argument("--data-dir", default="../data")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out_path = Path(args.data_dir) / f"{args.date}_fedtarmdlr.csv"
    fetch_if_missing(URL, out_path, args.force)


if __name__ == "__main__":
    main()
