import os
from pathlib import Path
import pandas as pd
from datetime import datetime

# Import local strategy components
from src.config import StrategyConfig
from src.data_loader import DataLoader
from src.core import StrategyLogic
from src.signal_generator import SignalGenerator
from src.execution_engine import ExecutionEngine
from src.simulator_models import SimulationConfig
from src.reporting.metrics import calculate_metrics
from src.reporting.report_generator import generate_report

def run_backtest(data_path: str, run_name: str = None):
    # 1. Initialize Configuration
    print("[DEBUG] Initializing configurations...")
    strat_cfg = StrategyConfig()
    sim_cfg = SimulationConfig(
        starting_capital=100_000.0,
        risk_per_trade_pct=0.01, # 1% Risk
        max_contracts=10
    )
    
    # 2. Load Data
    print(f"[*] Loading data from {data_path}...")
    loader = DataLoader(strat_cfg)
    df = loader.load_ohlcv(data_path)
    print(f"[DEBUG] Data loaded: {len(df)} bars found.")
    
    # 3. Strategy Logic (Enrichment)
    print("[*] Enrichment: Running core strategy logic (Sweeps, FVGs, IFVGs)...")
    logic = StrategyLogic(strat_cfg)
    df = logic.enrich_dataframe(df)
    print(f"[DEBUG] Enrichment complete. DF columns: {list(df.columns)}")
    
    # 4. Signal Generation
    print("[*] Signal Generation: Identifying trade setups...")
    sig_gen = SignalGenerator(strat_cfg)
    registry = sig_gen.generate_setups(df)
    total_setups = len(registry.pending) + len(registry.closed)
    print(f"[DEBUG] Signal generation complete: {total_setups} setups identified.")
    
    # 5. Execution Simulation
    print(f"[*] Simulation: Evaluating {total_setups} setups...")
    engine = ExecutionEngine()
    account = engine.run_backtest(registry, df, sim_cfg)
    print(f"[DEBUG] Simulation complete. History length: {len(account.trade_history)}")
    
    # 6. Reporting
    print("[*] Reporting: Generating performance metrics and visuals...")
    metrics = calculate_metrics(registry, account)
    print(f"[DEBUG] Metrics calculated. Final Equity: ${account.equity:,.2f}")
    
    if run_name is None:
        run_name = f"NQ_Backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    report_path = generate_report(
        run_id=run_name,
        metrics=metrics,
        registry=registry,
        account=account,
        ohlc_df=df,
        config=sim_cfg
    )
    
    print(f"\n[✓] Backtest Complete!")
    print(f"    Results saved to: {report_path}")
    print(f"    Net PnL: ${metrics.net_profit:+,.2f}")
    print(f"    Win Rate: {metrics.win_rate:.1%}")
    print(f"    Sharpe: {metrics.sharpe_ratio:.2f}")

if __name__ == "__main__":
    print("--- Dodgy Strat Backtest Engine ---")
    
    # Ensure data directory exists
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Look for any parquet file in the data folder
    parquet_files = list(data_dir.glob("*.parquet"))
    
    if not parquet_files:
        print("[!] No data found. Please place your NQ 1M OHLCV parquet file in the 'data/' directory.")
        print("    Example: data/nq_1m.parquet")
    else:
        # Use first one found
        target_data = str(parquet_files[0])
        print(f"[DEBUG] Found data file: {target_data}")
        run_backtest(target_data)
