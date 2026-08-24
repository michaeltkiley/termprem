"""
Fetch daily Treasury par yields from FRED.

Usage:
    python3 01_fetch_treasury_yields.py [--date YYYYMMDD] [--force]
"""
import argparse
from datetime import date
from pathlib import Path

from lib_fetch import fetch_if_missing

SERIES = ["DGS1", "DGS10", "DGS1MO", "DGS2", "DGS20", "DGS3", "DGS30", "DGS3MO", "DGS5", "DGS6MO", "DGS7"]
URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + ",".join(SERIES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    ap.add_argument("--data-dir", default="../data")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out_path = Path(args.data_dir) / f"{args.date}_treasury_yields.csv"
    fetch_if_missing(URL, out_path, args.force)


if __name__ == "__main__":
    main()
