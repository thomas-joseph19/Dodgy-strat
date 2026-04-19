"""
Fetch QQQ EOD close prices via yfinance and write to the parquet format
expected by SyntheticGammaEngine (columns: date, close).

Usage:
    python dodgy/scripts/fetch_qqq_underlying.py
    python dodgy/scripts/fetch_qqq_underlying.py --start 2018-01-01 --out path/to/underlying.parquet
"""

import argparse
import os
import pandas as pd
import yfinance as yf

DEFAULT_OUT = os.path.join(
    os.path.dirname(__file__), "../../data/DownloadedOptions/qqq/underlying.parquet"
)
DEFAULT_START = "2010-01-01"


def fetch(start: str, out: str) -> None:
    print(f"Fetching QQQ from {start} …")
    raw = yf.download("QQQ", start=start, progress=False, auto_adjust=True)
    if raw.empty:
        raise RuntimeError("yfinance returned no data — check ticker or network.")

    df = raw[["Close"]].copy()
    df.index = pd.to_datetime(df.index)
    df = df.reset_index().rename(columns={"Date": "date", "Close": "close"})
    df["date"] = pd.to_datetime(df["date"]).dt.date

    # Flatten MultiIndex columns yfinance sometimes produces
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in df.columns]

    df = df[["date", "close"]].dropna()
    df["close"] = df["close"].astype(float)

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"Wrote {len(df)} rows → {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=DEFAULT_START, help="Start date YYYY-MM-DD")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output parquet path")
    args = parser.parse_args()
    fetch(args.start, args.out)
