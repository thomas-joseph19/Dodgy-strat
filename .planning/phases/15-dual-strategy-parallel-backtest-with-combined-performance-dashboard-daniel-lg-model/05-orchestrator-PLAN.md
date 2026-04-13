---
phase: 15
plan_id: "05"
title: "Dual-Strategy Orchestrator"
wave: 3
depends_on: ["01", "02", "03", "04"]
autonomous: true
files_modified:
  - run_dual_backtest.py
---

# Plan 05: Dual-Strategy Orchestrator

## Objective
Create the top-level script `run_dual_backtest.py` that orchestrates the entire dual-strategy backtest. It handles parquet conversion (if needed), runs both the Daniel and LG models independently, merges the trade streams, calculates combined metrics, and generates the final tabbed dashboard.

## Tasks

<task id="1" title="Create run_dual_backtest.py">
<read_first>
- main.py — to see how `run_backtest` is implemented and what arguments it expects (specifically lines 480-552 for the CLI pattern). We need to import `run_backtest` from `main`.
- src/lg_runner.py — from Plan 02, for `run_lg_backtest`.
- src/trade_merger.py — from Plan 03, for normalisation and merge logic.
- src/combined_dashboard.py — from Plan 04, for `generate_combined_dashboard`.
- scripts/convert_parquet_to_lg_csv.py — from Plan 01, to invoke via subprocess.
</read_first>

<action>
Create `run_dual_backtest.py` in the repository root.

```python
"""
Dual-Strategy Backtest Orchestrator (Phase 15).

Runs both the Daniel strategy (Python) and LG Model (Node.js) independently
on the same NQ data, merges the trade streams, and produces a combined
HTML dashboard.
"""

import argparse
import subprocess
import sys
import webbrowser
from pathlib import Path
from datetime import datetime

# Import Daniel engine
from main import run_backtest

# Import phase 15 modules
from src.lg_runner import run_lg_backtest
from src.trade_merger import (
    normalise_daniel_trades,
    normalise_lg_trades,
    merge_and_sort,
    build_equity_curves,
    compute_combined_summary,
)
from src.combined_dashboard import generate_combined_dashboard

# We can reuse Daniel's metrics generator for the strategy-specific stats
from src.metrics import get_performance_summary

# Constants
DEFAULT_OUTPUT_ROOT = Path(r"D:\Algorithms\Dodgy Backtest Results")
PARQUET_PATH = Path("data/nq_1min_10y.parquet")
LG_M1_PATH = Path("data/lg_format/1Min_NQ.csv")
LG_H1_PATH = Path("data/lg_format/1H_NQ.csv")
SUBMODULE_DIR = Path("strategies/lg_model")


def convert_data_if_needed(force: bool, start: str = None, end: str = None) -> None:
    """Run the parquet to CSV conversion script if CSVs are missing or forced."""
    if force or not LG_M1_PATH.exists() or not LG_H1_PATH.exists():
        print("🔄 Converting parquet data to LG CSV format...")
        cmd = [sys.executable, "scripts/convert_parquet_to_lg_csv.py"]
        if start:
            cmd.extend(["--start", start])
        if end:
            cmd.extend(["--end", end])
        
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise RuntimeError("Parquet conversion failed. See output above.")
    else:
        print("⏭️ LG CSV files already exist. Skipping conversion (use --force-convert to override).")


def run_dual(
    start_date: str = None,
    end_date: str = None,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    skip_conversion: bool = False,
    force_conversion: bool = False,
) -> None:
    """Orchestrate the dual backtest."""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / f"dual_run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"===========================================================")
    print(f" DUAL-STRATEGY BACKTEST: DANIEL + LG")
    print(f"===========================================================")
    print(f"Output directory: {run_dir}")
    if start_date or end_date:
        print(f"Date range: {start_date or 'start'} to {end_date or 'end'}")
    
    # 1. Parquet Conversion
    if not skip_conversion:
        convert_data_if_needed(force=force_conversion, start=start_date, end=end_date)
    else:
        print("⏭️ Skipping Parquet conversion (--no-convert active).")

    # 2. Run Daniel Backtest
    print("\n-----------------------------------------------------------")
    print("▶️ RUNNING DANIEL ENGINE (Python)...")
    # We call run_backtest but we need to tell it to use the new run_dir.
    # We also disable its HTML output and ML to keep it baseline mechanical.
    run_backtest(
        data_path=str(PARQUET_PATH),
        start_date=start_date,
        end_date=end_date,
        output_root=str(run_dir.parent), # run_backtest creates its own subfolder, we will find it
        save_charts=False,
        extract_features=False,
        use_ml=False,
        optimized=False,
        # We inject a specific folder name prefix by overriding output_root behavior cautiously, 
        # but the safest way to find Daniel's output is to look into the highest timestamped dir.
    )
    
    # Locate Daniel's trades.csv in the last created output directory
    daniel_dirs = sorted([d for d in run_dir.parent.iterdir() if d.is_dir() and d.name.startswith("run_")])
    if not daniel_dirs:
        raise FileNotFoundError("Could not locate Daniel output directory.")
    daniel_out_dir = daniel_dirs[-1]
    daniel_csv = daniel_out_dir / "trades.csv"
    if not daniel_csv.exists():
        raise FileNotFoundError(f"Daniel trades.csv not found in {daniel_out_dir}")
    print(f"✅ Daniel complete. Logs in {daniel_out_dir}")
    
    # 3. Run LG Backtest (in our dual run_dir)
    print("\n-----------------------------------------------------------")
    print("▶️ RUNNING LG MODEL (Node.js)...")
    lg_csv = run_lg_backtest(
        submodule_dir=SUBMODULE_DIR,
        m1_path=LG_M1_PATH,
        h1_path=LG_H1_PATH,
        out_dir=run_dir,
        from_date=start_date,
        to_date=end_date,
    )
    
    # 4. Normalise & Merge Trades
    print("\n-----------------------------------------------------------")
    print("▶️ MERGING TRADE STREAMS...")
    daniel_trades = normalise_daniel_trades(daniel_csv)
    lg_trades = normalise_lg_trades(lg_csv)
    
    merged_trades = merge_and_sort(daniel_trades, lg_trades)
    print(f"Total Combined Trades: {len(merged_trades)} (Daniel: {len(daniel_trades)}, LG: {len(lg_trades)})")
    
    # 5. Build Equity Curves and Metrics
    print("▶️ CALCULATING PERFORMANCE METRICS...")
    equity_curves = build_equity_curves(merged_trades, initial_capital=100_000.0)
    
    combined_summary = compute_combined_summary(merged_trades)
    
    # Use existing metrics calculator for strategy isolation
    # Reconstruct the TradeResult objects or simple dicts that get_performance_summary expects?
    # get_performance_summary expects TradeResult objects. Since we parsed from CSV, we just 
    # run compute_combined_summary on the individual lists as well.
    daniel_summary = compute_combined_summary(daniel_trades)
    lg_summary = compute_combined_summary(lg_trades)
    
    # 6. Generate Dashboard
    print("▶️ GENERATING DASHBOARD...")
    dashboard_html = run_dir / "combined_dashboard.html"
    generate_combined_dashboard(
        daniel_trades=daniel_trades,
        lg_trades=lg_trades,
        equity_curves=equity_curves,
        output_path=dashboard_html,
        daniel_summary=daniel_summary,
        lg_summary=lg_summary,
        combined_summary=combined_summary,
    )
    
    print(f"\n✅ DUAL BACKTEST COMPLETE.")
    print(f"Dashboard generated: {dashboard_html}")
    webbrowser.open(f"file://{dashboard_html.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dual-Strategy Backtest Orchestrator")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)", default=None)
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)", default=None)
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_ROOT), help="Root output directory")
    parser.add_argument("--no-convert", action="store_true", help="Skip Parquet to CSV conversion")
    parser.add_argument("--force-convert", action="store_true", help="Force Parquet conversion even if CSV exist")
    
    args = parser.parse_args()
    
    run_dual(
        start_date=args.start,
        end_date=args.end,
        output_root=Path(args.output_dir),
        skip_conversion=args.no_convert,
        force_conversion=args.force_convert,
    )
```

</action>

<acceptance_criteria>
- `run_dual_backtest.py` exists in the repository root.
- The script imports and invokes `main.run_backtest`.
- The script handles finding the Daniel output directory by looking for the latest `run_*` directory.
- The script calls `run_lg_backtest` from `src.lg_runner`.
- The script merges the trades and produces metrics.
- The script generates the combined dashboard and attempts to open it in a web browser.
- The script handles `--start`, `--end`, `--no-convert`, and `--force-convert` arguments.
- **IMPORTANT**: Provides instructions on how to use it but does NOT automatically run the backtest during agent execution.
</acceptance_criteria>
</task>

## Verification
Confirm the script is syntactically valid and imports all necessary dependencies:
`python -m compileall run_dual_backtest.py`

## must_haves
- Orchestrates the full process from conversion to dashboard.
- Maintains separation of concerns: runs Daniel via `main.py`, LG via `lg_runner.py`.
- Computes metrics for Combined, Daniel, and LG.
- Opens the final dashboard.
