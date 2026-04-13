---
phase: 15
plan_id: "01"
title: "Git Submodule Setup and Parquet → LG CSV Conversion"
wave: 1
depends_on: []
autonomous: true
files_modified:
  - scripts/convert_parquet_to_lg_csv.py
  - .gitignore
  - .gitmodules
  - requirements.txt
---

# Plan 01: Git Submodule Setup and Parquet → LG CSV Conversion

## Objective
Add the LG Model as a git submodule and build a Python script that converts the existing NQ parquet file into the two semicolon-delimited CSV files that the LG Model's Node.js backtest CLI requires.

## Tasks

<task id="1" title="Add LG Model as git submodule">
<read_first>
- .gitignore — to understand what is already ignored
- .gitmodules — check if already exists before adding
</read_first>

<action>
Run the following git command to add the LG model as a submodule:

  git submodule add https://github.com/cuzohh/lg-model.git strategies/lg_model

This creates:
- `strategies/lg_model/` directory with the cloned repo
- `.gitmodules` file tracking the submodule

If `.gitmodules` already exists and contains this entry, skip this step.

After adding, verify the submodule is in `.gitmodules`:
  [submodule "strategies/lg_model"]
    path = strategies/lg_model
    url = https://github.com/cuzohh/lg-model.git
</action>

<acceptance_criteria>
- `.gitmodules` file exists at repo root
- `.gitmodules` contains `strategies/lg_model`
- `strategies/lg_model/src/cli/backtest.js` exists
- `strategies/lg_model/package.json` exists
</acceptance_criteria>
</task>

<task id="2" title="Add data/lg_format/ to .gitignore">
<read_first>
- .gitignore — current contents
</read_first>

<action>
Append the following lines to `.gitignore` if not already present:

  # LG Model converted data files (large, regenerated from parquet)
  data/lg_format/
  strategies/lg_model/node_modules/
</action>

<acceptance_criteria>
- `.gitignore` contains `data/lg_format/`
- `.gitignore` contains `strategies/lg_model/node_modules/`
</acceptance_criteria>
</task>

<task id="3" title="Create scripts/convert_parquet_to_lg_csv.py">
<read_first>
- data/nq_1min_10y.parquet — check columns and timestamp dtype before writing conversion
- .planning/phases/15-dual-strategy-parallel-backtest-with-combined-performance-dashboard-daniel-lg-model/15-RESEARCH.md — LG CSV format specification
- strategies/lg_model/src/data/load-csv-bars.js — LG's CSV parsing logic
</read_first>

<action>
Create `scripts/convert_parquet_to_lg_csv.py` with the following implementation:

```python
"""
Convert NQ 1-min parquet → LG Model semicolon-delimited CSVs.

LG Model expects:
  - 1-min CSV: header line 1, data from line 2
    Columns: Date;Symbol;Open;High;Low;Close;Volume
    Timestamps: Chicago local (America/Chicago), format MM/DD/YYYY HH:MM:SS
  - 1H CSV: preamble line 1, header line 2, data from line 3
    Same columns and timestamp format

Usage:
  python scripts/convert_parquet_to_lg_csv.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]
"""

import argparse
import pandas as pd
from pathlib import Path
from tqdm import tqdm

PARQUET_PATH = Path("data/nq_1min_10y.parquet")
OUTPUT_DIR = Path("data/lg_format")
SYMBOL = "NQ_CONT"
CHICAGO_TZ = "America/Chicago"


def parse_args():
    p = argparse.ArgumentParser(description="Convert NQ parquet to LG Model CSV format")
    p.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD (Chicago local)")
    p.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD (Chicago local)")
    p.add_argument("--parquet", type=str, default=str(PARQUET_PATH), help="Path to parquet file")
    p.add_argument("--out-dir", type=str, default=str(OUTPUT_DIR), help="Output directory")
    return p.parse_args()


def load_and_normalise(parquet_path: Path, tz: str = CHICAGO_TZ) -> pd.DataFrame:
    """Load parquet, ensure timestamps are Chicago-local, return sorted DataFrame."""
    print(f"Loading {parquet_path} ...")
    df = pd.read_parquet(parquet_path)

    # Normalise timestamp column
    ts_col = "timestamp" if "timestamp" in df.columns else df.columns[0]
    df = df.rename(columns={ts_col: "timestamp"})
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Handle timezone: if UTC-aware, convert; if naive, assume UTC then convert
    if df["timestamp"].dt.tz is None:
        print("Timestamps appear timezone-naive — assuming UTC, converting to Chicago.")
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC").dt.tz_convert(tz)
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert(tz)

    # Add Volume col if missing
    if "volume" not in df.columns and "Volume" not in df.columns:
        df["Volume"] = 0
    elif "volume" in df.columns:
        df = df.rename(columns={"volume": "Volume"})

    # Standardise OHLC column names
    col_map = {"open": "Open", "high": "High", "low": "Low", "close": "Close"}
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def apply_date_filter(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    if start:
        df = df[df["timestamp"].dt.date >= pd.to_datetime(start).date()]
    if end:
        df = df[df["timestamp"].dt.date <= pd.to_datetime(end).date()]
    return df.reset_index(drop=True)


def to_lg_date_str(ts_series: pd.Series) -> pd.Series:
    """Convert timestamps to LG expected format: MM/DD/YYYY HH:MM:SS."""
    return ts_series.dt.strftime("%m/%d/%Y %H:%M:%S")


def write_1min_csv(df: pd.DataFrame, out_path: Path, symbol: str = SYMBOL):
    """Write 1-minute CSV in LG format (standard header on line 1)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_out = pd.DataFrame({
        "Date": to_lg_date_str(df["timestamp"]),
        "Symbol": symbol,
        "Open": df["Open"],
        "High": df["High"],
        "Low": df["Low"],
        "Close": df["Close"],
        "Volume": df.get("Volume", 0),
    })
    print(f"Writing 1-min CSV ({len(df_out):,} rows) → {out_path}")
    with tqdm(total=1, desc="Writing 1Min CSV", unit="file") as pbar:
        df_out.to_csv(out_path, sep=";", index=False)
        pbar.update(1)
    print(f"Done: {out_path}")


def write_1h_csv(df: pd.DataFrame, out_path: Path, symbol: str = SYMBOL):
    """
    Write 1-hour resampled CSV in LG format.
    LG's load1HBars uses from_line: 2, so line 1 must be a preamble.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df_indexed = df.set_index("timestamp")
    df_1h = df_indexed.resample("1h").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna(subset=["Open"]).reset_index()

    df_out = pd.DataFrame({
        "Date": to_lg_date_str(df_1h["timestamp"]),
        "Symbol": symbol,
        "Open": df_1h["Open"],
        "High": df_1h["High"],
        "Low": df_1h["Low"],
        "Close": df_1h["Close"],
        "Volume": df_1h["Volume"],
    })

    print(f"Writing 1H CSV ({len(df_out):,} rows) → {out_path}")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        f.write("Time Series (NQ 1H)\n")  # Preamble line — required by load1HBars (from_line: 2)
        df_out.to_csv(f, sep=";", index=False)
    print(f"Done: {out_path}")


def main():
    args = parse_args()
    parquet_path = Path(args.parquet)
    out_dir = Path(args.out_dir)

    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet not found: {parquet_path}")

    df = load_and_normalise(parquet_path)
    df = apply_date_filter(df, args.start, args.end)

    if df.empty:
        print("ERROR: No data after date filtering. Check --start/--end.")
        return

    print(f"Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")
    print(f"Total 1-minute bars: {len(df):,}")

    write_1min_csv(df, out_dir / "1Min_NQ.csv")
    write_1h_csv(df, out_dir / "1H_NQ.csv")

    print("\n✅ Conversion complete.")
    print(f"  1Min: {out_dir / '1Min_NQ.csv'}")
    print(f"  1H:   {out_dir / '1H_NQ.csv'}")


if __name__ == "__main__":
    main()
```
</action>

<acceptance_criteria>
- `scripts/convert_parquet_to_lg_csv.py` exists
- File contains `def write_1min_csv(`
- File contains `def write_1h_csv(`
- File contains `from_line: 2` comment reference or preamble line write logic
- File contains `tz_localize` and `tz_convert` for timezone handling
- File contains `argparse` with `--start` and `--end` flags
</acceptance_criteria>
</task>

<task id="4" title="Update requirements.txt">
<read_first>
- requirements.txt — current contents
</read_first>

<action>
Ensure `requirements.txt` contains these dependencies (add any that are missing):
  tqdm           (already present — used for progress bars)
  pyarrow        (needed for pd.read_parquet)
  pandas         (already present)

No new pip packages are needed beyond what is already in requirements.txt.
Verify pyarrow is listed; add it if absent.
</action>

<acceptance_criteria>
- `requirements.txt` contains `pyarrow` or `pyarrow>=`
- `requirements.txt` contains `tqdm` or `tqdm>=`
</acceptance_criteria>
</task>

## Verification
Run: `python scripts/convert_parquet_to_lg_csv.py --start 2024-01-01 --end 2024-01-31`
Verify:
- `data/lg_format/1Min_NQ.csv` is created and has a header `Date;Symbol;Open;High;Low;Close;Volume`
- `data/lg_format/1H_NQ.csv` is created and its first line is `Time Series (NQ 1H)` and second line is `Date;Symbol;Open;High;Low;Close;Volume`

## must_haves
- LG submodule exists at `strategies/lg_model/`
- `scripts/convert_parquet_to_lg_csv.py` converts parquet to correct semicolon CSV format
- 1H CSV has preamble line (LG will silently fail to load any data without it)
- Timezone conversion from UTC parquet to Chicago local is handled
- `data/lg_format/` is gitignored
