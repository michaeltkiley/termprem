"""Load and merge the three raw data sources, matching the resampling
conventions validated in ../replication_scripts/01_load_data.py."""
import re

import pandas as pd


def clean_colname(name: str) -> str:
    name = name.strip()
    name = re.sub(r"[^0-9A-Za-z_]", "_", name)
    return name


def _find_header_row(path) -> int:
    """Fed/FRED downloads sometimes prefix the real header with metadata
    lines (notes, mnemonics). Find the first line whose first field looks
    like a date-column name."""
    with open(path, encoding="utf-8-sig") as f:
        for i, line in enumerate(f):
            first_field = line.split(",")[0].strip().strip('"')
            if first_field.lower() in ("date", "observation_date"):
                return i
    return 0


def load_csv(path, date_col_guess=None) -> pd.DataFrame:
    header_row = _find_header_row(path)
    df = pd.read_csv(path, na_values=["NA"], skiprows=header_row)
    df.columns = [clean_colname(c) for c in df.columns]
    date_col = date_col_guess or df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.rename(columns={date_col: "DATE"}).set_index("DATE")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def last_value_resample(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """'lastvalue' aggregation: within each period, each column
    independently takes its last non-missing value; the output row time is
    the last non-fully-missing timestamp present in the period."""
    periods = df.index.to_period(freq)
    grouped = df.groupby(periods, sort=True)
    out_rows, out_index = [], []
    for _, g in grouped:
        g_valid = g.dropna(how="all")
        anchor = g_valid.index[-1] if len(g_valid) else g.index[-1]
        out_rows.append(g.loc[:anchor].ffill().iloc[-1])
        out_index.append(anchor)
    return pd.DataFrame(out_rows, index=pd.DatetimeIndex(out_index, name="DATE"))


def build_merged(treasury_path, kim_wright_path, acm_path) -> pd.DataFrame:
    ts = load_csv(treasury_path)
    kw = load_csv(kim_wright_path)
    acm = load_csv(acm_path)
    return ts.join(kw, how="outer").join(acm, how="outer").sort_index()
