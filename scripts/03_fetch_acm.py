"""
Fetch the Adrian-Crump-Moench term premium data from the NY Fed. Source is
an .xls workbook; we pull the 'ACM Daily' sheet and save it as a flat CSV.

Usage:
    python3 03_fetch_acm.py [--date YYYYMMDD] [--force]
"""
import argparse
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

URL = "https://www.newyorkfed.org/medialibrary/media/research/data_indicators/ACMTermPremium.xls"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    ap.add_argument("--data-dir", default="../data")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out_path = Path(args.data_dir) / f"{args.date}_acm.csv"
    if out_path.exists() and not args.force:
        print(f"{out_path} already exists, skipping (use --force to refetch)")
        return

    resp = requests.get(URL, timeout=60)
    resp.raise_for_status()
    with tempfile.NamedTemporaryFile(suffix=".xls") as tmp:
        tmp.write(resp.content)
        tmp.flush()
        df = pd.read_excel(tmp.name, sheet_name="ACM Daily")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Fetched {URL} ('ACM Daily' sheet) -> {out_path} ({len(df)} rows)")


if __name__ == "__main__":
    main()
