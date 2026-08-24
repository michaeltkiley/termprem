"""
Fetch the Kim-Wright three-factor nominal term structure model data from the
Federal Reserve Board.

Usage:
    python3 02_fetch_kim_wright.py [--date YYYYMMDD] [--force]
"""
import argparse
from datetime import date
from pathlib import Path

from lib_fetch import fetch_if_missing

URL = "https://www.federalreserve.gov/data/yield-curve-tables/feds200533.csv"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    ap.add_argument("--data-dir", default="../data")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out_path = Path(args.data_dir) / f"{args.date}_kim_wright.csv"
    fetch_if_missing(URL, out_path, args.force)


if __name__ == "__main__":
    main()
