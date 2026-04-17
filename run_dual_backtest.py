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
import shutil
import csv
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
from tqdm import tqdm

# Import Daniel engine
from main import run_backtest
from src.execution import SizingMode

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

# Constants
DEFAULT_OUTPUT_ROOT = Path(r"D:\Algorithms\Dodgy Backtest Results")
PARQUET_PATH = Path("data/nq_1min_10y.parquet")
LG_M1_PATH = Path("data/lg_format/1Min_NQ.csv")
LG_H1_PATH = Path("data/lg_format/1H_NQ.csv")
SUBMODULE_DIR = Path("strategies/lg_model")


def run_micro_mc(
    merged_trades: list,
    out_dir: Path,
    n_paths: int = 5000,
    batch_size: int = 10,
    seed: int | None = None,
) -> dict:
    """Bootstrap Monte Carlo over merged trade PnL and write outputs."""
    if not merged_trades:
        raise ValueError("Cannot run Monte Carlo with no merged trades.")

    trade_pnls = np.array([float(t["pnl_usd"]) for t in merged_trades], dtype=float)
    if trade_pnls.size == 0:
        raise ValueError("Cannot run Monte Carlo with empty pnl series.")

    rng = np.random.default_rng(seed)
    n_trades = trade_pnls.size
    out_dir.mkdir(parents=True, exist_ok=True)

    final_equity = np.empty(n_paths, dtype=float)
    starting_capital = 100_000.0

    for start_idx in range(0, n_paths, batch_size):
        end_idx = min(start_idx + batch_size, n_paths)
        this_batch = end_idx - start_idx
        sampled = rng.choice(trade_pnls, size=(this_batch, n_trades), replace=True)
        final_equity[start_idx:end_idx] = starting_capital + sampled.sum(axis=1)

    percentiles = np.percentile(final_equity, [5, 25, 50, 75, 95])
    summary = {
        "paths": int(n_paths),
        "trades_per_path": int(n_trades),
        "seed": seed if seed is not None else "random",
        "mean_final_equity": round(float(final_equity.mean()), 2),
        "p05_final_equity": round(float(percentiles[0]), 2),
        "p25_final_equity": round(float(percentiles[1]), 2),
        "p50_final_equity": round(float(percentiles[2]), 2),
        "p75_final_equity": round(float(percentiles[3]), 2),
        "p95_final_equity": round(float(percentiles[4]), 2),
    }

    summary_csv = out_dir / "mc_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
        writer.writeheader()
        writer.writerow(summary)

    dist_csv = out_dir / "mc_final_equity.csv"
    with dist_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["path_id", "final_equity"])
        for i, val in enumerate(final_equity, start=1):
            writer.writerow([i, round(float(val), 2)])

    return {
        "summary_path": summary_csv,
        "distribution_path": dist_csv,
        "summary": summary,
    }


def ensure_daniel_parquet_exists() -> None:
    """Build Daniel parquet from LG 1m CSV when parquet source is missing."""
    if PARQUET_PATH.exists():
        return
    if not LG_M1_PATH.exists():
        raise FileNotFoundError(
            f"Required parquet is missing and fallback source not found: {LG_M1_PATH}"
        )

    print(f"[INFO] {PARQUET_PATH} missing. Building from {LG_M1_PATH}...")
    PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(
        LG_M1_PATH,
        sep=";",
        decimal=",",
        usecols=["Date", "Open", "High", "Low", "Close"],
        low_memory=False,
    )
    df.rename(
        columns={
            "Date": "timestamp",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
        },
        inplace=True,
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%m/%d/%Y %I:%M %p", errors="coerce")
    df.dropna(subset=["timestamp", "open", "high", "low", "close"], inplace=True)
    df.to_parquet(PARQUET_PATH, index=False)
    print(f"[INFO] Built Daniel parquet: {PARQUET_PATH}")


def convert_data_if_needed(force: bool, start: str = None, end: str = None) -> None:
    """Run the parquet to CSV conversion script if CSVs are missing or forced."""
    if force or not LG_M1_PATH.exists() or not LG_H1_PATH.exists():
        print("[INFO] Converting parquet data to LG CSV format...")
        cmd = [sys.executable, "scripts/convert_parquet_to_lg_csv.py"]
        if start:
            cmd.extend(["--start", start])
        if end:
            cmd.extend(["--end", end])
        
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise RuntimeError("Parquet conversion failed. See output above.")
    else:
        print("[SKIP] LG CSV files already exist. Skipping conversion (use --force-convert to override).")


def run_dual(
    start_date: str = None,
    end_date: str = None,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    skip_conversion: bool = False,
    force_conversion: bool = False,
    contracts: int = 1,
    risk_pct: float = 0.01,
    sizing: str = "fixed",
    run_mc: bool = False,
    mc_n_paths: int = 5000,
    mc_batch_size: int = 10,
    mc_seed: int | None = None,
    mc_only: bool = False,
    trades_dir: str | None = None,
    slippage_ticks: int = 1,
) -> None:
    """Orchestrate the dual backtest."""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_root / f"dual_run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n" + "="*60)
    print(f" DUAL-STRATEGY ENGINE: DANIEL + ORB MODEL")
    print(f"="*60)
    print(f"Target Directory: {run_dir}")
    if start_date or end_date:
        print(f"Date range: {start_date or 'start'} to {end_date or 'end'}")
    
    # 1. Pipeline Steps with Global Progress
    steps = ["Data Preparation", "Daniel Engine", "ORB Model Engine", "Merge & Metrics", "Dashboard Generation"]
    pbar = tqdm(total=len(steps), desc="Overall Progress", bar_format="{l_bar}{bar:30}{r_bar}")

    try:
        if not mc_only:
            # Step 1: Data Preparation
            pbar.set_description(f"Step 1/5: {steps[0]}")
            if not skip_conversion:
                convert_data_if_needed(force=force_conversion, start=start_date, end=end_date)
            pbar.update(1)

            # Step 2: Daniel Engine
            pbar.set_description(f"Step 2/5: {steps[1]}")
            
            # Use CSV if Parquet is gone
            active_data_path = PARQUET_PATH if PARQUET_PATH.exists() else LG_M1_PATH
            if not active_data_path.exists():
                raise FileNotFoundError(f"No backtest data found at {PARQUET_PATH} or {LG_M1_PATH}")

            run_backtest(
                data_path=str(active_data_path),
                start_date=start_date,
                end_date=end_date,
                output_root=str(run_dir),
                save_charts=False,
                extract_features=False,
                use_ml=False,
                optimized=False,
                rule_filter="none",
                ml_config={
                    'sizing_mode': SizingMode.RISK_PCT if sizing == "risk" else SizingMode.FIXED,
                    'contracts': contracts,
                    'risk_pct': risk_pct,
                    'slippage_ticks': slippage_ticks
                }
            )
            
            # Consolidation: Move Daniel's trades.csv to the root of run_dir
            daniel_dirs = sorted([d for d in run_dir.iterdir() if d.is_dir() and d.name.startswith("run_")])
            if not daniel_dirs:
                raise FileNotFoundError("Could not locate Daniel output directory.")
            daniel_out_dir = daniel_dirs[-1]
            
            daniel_csv = run_dir / "daniel_trades.csv"
            shutil.move(str(daniel_out_dir / "trades.csv"), str(daniel_csv))
            
            # Check for engine log
            if (daniel_out_dir / "engine_log.txt").exists():
                shutil.copy(str(daniel_out_dir / "engine_log.txt"), str(run_dir / "daniel_engine_log.txt"))
                
            pbar.update(1)

            # Step 3: ORB Model Engine
            pbar.set_description(f"Step 3/5: {steps[2]}")
            raw_lg_csv = run_lg_backtest(
                submodule_dir=SUBMODULE_DIR,
                m1_path=LG_M1_PATH,
                h1_path=LG_H1_PATH,
                out_dir=run_dir / "orb_temp",
                from_date=start_date,
                to_date=end_date,
                strategy="orb",
                slippage_ticks=slippage_ticks
            )
            
            # Consolidate ORB trades
            lg_csv = run_dir / "orb_trades.csv"
            shutil.move(str(raw_lg_csv), str(lg_csv))
            shutil.rmtree(run_dir / "orb_temp")
            pbar.update(1)
        else:
            print("[INFO] MC-ONLY mode: Searching for historical trade files...")
            source_dir = Path(trades_dir) if trades_dir else Path(".")
            daniel_csv = run_dir / "daniel_trades.csv"
            lg_csv = run_dir / "orb_trades.csv"
            
            # 1. ORB Trades
            orb_source = source_dir / "orb_trades.csv"
            if orb_source.exists():
                shutil.copy(str(orb_source), str(lg_csv))
                print(f"  [OK] Loaded ORB trades: {orb_source.name}")
            else:
                with lg_csv.open("w") as f: f.write("session_date,side,entry_price,exit_category,pnl_points,pnl_usd,risk_points,entry_time_utc\n")
            
            # 2. Daniel Trades (Combine multiple if found)
            # Match trades.csv, trades2023-2025.csv, daniel_trades.csv, etc.
            daniel_files = list(source_dir.glob("trades*.csv")) + list(source_dir.glob("daniel_trades*.csv"))
            # Filter matches (exclude the orb file we just handled)
            daniel_files = [f for f in daniel_files if f.name != "orb_trades.csv"]
            # Deduplicate (if both globs catch the same file)
            daniel_files = sorted(list(set(daniel_files)))

            if daniel_files:
                print(f"  [OK] Combining {len(daniel_files)} Daniel trade files...")
                with daniel_csv.open("w", newline="") as out_f:
                    writer = None
                    for i, fpath in enumerate(daniel_files):
                        with fpath.open("r", newline="") as in_f:
                            reader = csv.DictReader(in_f)
                            if not writer:
                                writer = csv.DictWriter(out_f, fieldnames=reader.fieldnames)
                                writer.writeheader()
                            for row in reader:
                                writer.writerow(row)
                print(f"      Mapped: {', '.join(f.name for f in daniel_files)}")
            else:
                with daniel_csv.open("w") as f: f.write("date,direction,entry_price,exit_type,pnl_points,pnl_usd,risk_points\n")
            
            pbar.update(3)

        # Step 4: Merge & Metrics
        pbar.set_description(f"Step 4/5: {steps[3]}")
        daniel_trades = normalise_daniel_trades(daniel_csv)
        lg_trades = normalise_lg_trades(lg_csv)
        merged_trades = merge_and_sort(daniel_trades, lg_trades)
        equity_curves = build_equity_curves(merged_trades, initial_capital=100_000.0)
        
        combined_summary = compute_combined_summary(merged_trades)
        daniel_summary = compute_combined_summary(daniel_trades)
        lg_summary = compute_combined_summary(lg_trades)
        
        # Adjust summaries for sizing if needed
        # (The normalised trades already have P&L in USD, but if we want to change it 
        # dynamically in the dashboard, we'll do it in JS)
        pbar.update(1)

        mc_result = None
        if run_mc or mc_only:
            print("[INFO] Running micro Monte Carlo simulation...")
            mc_result = run_micro_mc(
                merged_trades=merged_trades,
                out_dir=run_dir,
                n_paths=mc_n_paths,
                batch_size=mc_batch_size,
                seed=mc_seed,
            )
            print(f"[INFO] MC summary saved: {mc_result['summary_path']}")

        # Step 5: Dashboard Generation
        pbar.set_description(f"Step 5/5: {steps[4]}")
        dashboard_html = run_dir / "combined_performance.html"
        
        # Prepare TRADE_PNLS for the dashboard MC chart
        trade_pnls = [float(t["pnl_usd"]) for t in merged_trades]
        
        generate_combined_dashboard(
            daniel_trades=daniel_trades,
            lg_trades=lg_trades,
            equity_curves=equity_curves,
            output_path=dashboard_html,
            daniel_summary=daniel_summary,
            lg_summary=lg_summary,
            combined_summary=combined_summary,
            mc_summary=mc_result["summary"] if mc_result else None,
            trade_pnls=trade_pnls,
        )
        pbar.update(1)
        pbar.close()

        print(f"\n[SUCCESS] ALL OUTPUTS SAVED TO:")
        print(f"   {run_dir}")
        print(f"   - daniel_trades.csv")
        print(f"   - lg_trades.csv")
        print(f"   - combined_performance.html")
        if mc_result:
            print(f"   - {mc_result['summary_path'].name}")
            print(f"   - {mc_result['distribution_path'].name}")
        
        webbrowser.open(f"file://{dashboard_html.resolve()}")

    except Exception as e:
        if 'pbar' in locals(): pbar.close()
        print(f"\n[ERROR] during dual backtest: {str(e)}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dual-Strategy Backtest Orchestrator")
    parser.add_argument("--start", "--from", type=str, help="Start date (YYYY-MM-DD)", default=None)
    parser.add_argument("--end", "--to", type=str, help="End date (YYYY-MM-DD)", default=None)
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_ROOT), help="Root output directory")
    parser.add_argument("--no-convert", action="store_true", help="Skip Parquet to CSV conversion")
    parser.add_argument("--force-convert", action="store_true", help="Force Parquet conversion even if CSV exist")
    
    # Sizing Arguments
    parser.add_argument("--contracts", type=int, default=1, help="Fixed contracts")
    parser.add_argument("--risk-pct", type=float, default=0.01, help="Risk percentage")
    parser.add_argument("--sizing", type=str, choices=["fixed", "risk"], default="fixed", help="Sizing mode")
    parser.add_argument("--mc", action="store_true", help="Run micro Monte Carlo sim on merged trade stream")
    parser.add_argument("--mc-n-paths", type=int, default=5000, help="Number of Monte Carlo paths")
    parser.add_argument("--mc-batch-size", type=int, default=10, help="Paths per vectorized batch")
    parser.add_argument("--mc-seed", type=int, default=None, help="Random seed for reproducible MC")
    parser.add_argument("--mc-only", action="store_true", help="Skip backtests and run MC on existing trades.csv files")
    parser.add_argument("--trades-dir", type=str, default=None, help="Directory containing existing daniel_trades.csv and orb_trades.csv")
    parser.add_argument("--slippage-ticks", type=int, default=1, help="Adverse slippage per side (ticks). Default=1")
    
    args = parser.parse_args()
    
    run_dual(
        start_date=args.start,
        end_date=args.end,
        output_root=Path(args.output_dir),
        skip_conversion=args.no_convert,
        force_conversion=args.force_convert,
        contracts=args.contracts,
        risk_pct=args.risk_pct,
        sizing=args.sizing,
        run_mc=args.mc,
        mc_n_paths=args.mc_n_paths,
        mc_batch_size=args.mc_batch_size,
        mc_seed=args.mc_seed,
        mc_only=args.mc_only,
        trades_dir=args.trades_dir,
        slippage_ticks=args.slippage_ticks
    )
