import pandas as pd
import numpy as np
import os
import webbrowser
import xgboost as xgb
from pathlib import Path
from typing import List
from datetime import datetime, timedelta
from src.core import Candle, NQ, THRESHOLDS
from src.swings import SwingRegistry, detect_swing_high, detect_swing_low
from src.liquidity import LiquidityLevel, detect_sweep, SweepEvent
from src.fvg import detect_fvg, merge_fvg_series, FairValueGap
from src.execution import (
    TradeSetup, Direction, ModelType, StopType, 
    SignalGrade, SimulationConfig, TradeResult, TradeState
)
from tqdm import tqdm
from src.plotting import build_setup_chart
from src.metrics import get_performance_summary
from src.dashboard import generate_dashboard
from src.gamma import SyntheticGammaEngine
from src.ml_features import FeatureExtractor
from src.ml_pipeline import MLPipeline

# ── Simulation Runner ───────────────────────────────────────────

def evaluate_setup(setup: TradeSetup, timestamps: List[datetime], highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, start_idx: int, config: SimulationConfig) -> TradeResult:
    state = TradeState(
        entry_filled=True,
        break_even_active=False,
        current_stop=setup.stop_price
    )
    
    # Vectorized check for exits if possible, otherwise keep loop but optimize indexing
    for i in range(start_idx + 1, len(closes)):
        candle_high = highs[i]
        candle_low  = lows[i]
        candle_close = closes[i]
        candle_time = timestamps[i]
        
        # Check Break-Even trigger
        if not state.break_even_active:
            if setup.direction == Direction.LONG:
                if candle_high >= setup.break_even_trigger:
                    state.current_stop = setup.entry_price
                    state.break_even_active = True
            else:
                if candle_low <= setup.break_even_trigger:
                    state.current_stop = setup.entry_price
                    state.break_even_active = True
        
        # Check Exits - Priority: Stop -> Target
        if setup.direction == Direction.LONG:
            if candle_low <= state.current_stop:
                return TradeResult(setup, candle_time, state.current_stop, "HARD_STOP", 0.0)
            if candle_high >= setup.target_price:
                return TradeResult(setup, candle_time, setup.target_price, "TARGET_HIT", 0.0)
        else:
            if candle_high >= state.current_stop:
                return TradeResult(setup, candle_time, state.current_stop, "HARD_STOP", 0.0)
            if candle_low <= setup.target_price:
                return TradeResult(setup, candle_time, setup.target_price, "TARGET_HIT", 0.0)
                
    return TradeResult(setup, timestamps[-1], closes[-1], "EXPIRED_OR_STILL_OPEN", 0.0)

def calculate_net_pnl(result: TradeResult, contracts: int, config: SimulationConfig) -> float:
    slippage_per_side = config.slippage_ticks * config.tick_size
    
    if result.setup.direction == Direction.LONG:
        actual_entry = result.setup.entry_price + slippage_per_side
        actual_exit  = result.exit_price - slippage_per_side
        points = actual_exit - actual_entry
    else:
        actual_entry = result.setup.entry_price - slippage_per_side
        actual_exit  = result.exit_price + slippage_per_side
        points = actual_entry - actual_exit
        
    gross = points * config.point_value * contracts
    comm = config.commission_per_rt * contracts
    return gross - comm

def _classify_session(ts: datetime) -> str:
    """Classify a timestamp into a trading session bucket."""
    h, m = ts.hour, ts.minute
    if h < 9 or (h == 9 and m < 30):
        return "pre_market"
    if h < 12:
        return "open_drive"
    if h < 14:
        return "midday"
    if h < 16:
        return "power_hour"
    return "overnight"

# ── Main Loop ───────────────────────────────────────────────────

def run_backtest(data_path: str, start_date=None, end_date=None, output_root=None, save_charts=False, extract_features=False, ml_config=None, use_ml=False, model_path=None, ml_threshold=0.5, optimized=False):


    # Initialize Gamma Engine
    gamma_engine = SyntheticGammaEngine(
        options_dir="ML data/parquet_qqq",
        underlying_path="ML data/parquet_qqq/underlying_prices.parquet"
    )
    feature_extractor = FeatureExtractor()
    trade_features = []
    
    # ML Model Loading
    ml_model = None
    if (use_ml or optimized) and model_path:
        # Default to latest if no specific path provided
        actual_path = model_path if model_path else "models/latest/xgboost_model.json"
        
        if os.path.exists(actual_path):
            print(f"🚀 RUNNING OPTIMIZED: {actual_path} (Threshold: {ml_threshold})")
            ml_model = xgb.Booster()
            ml_model.load_model(actual_path)
        else:
            print(f"⚠️ Warning: Optimized model not found at {actual_path}. Running naked backtest.")

    df = pd.read_parquet(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    if start_date:
        df = df[df['timestamp'] >= start_date].reset_index(drop=True)
    if end_date:
        df = df[df['timestamp'] < end_date].reset_index(drop=True)
    
    # LOAD ARRAYS DIRECTLY - DO NOT PRE-BUILD 4M CANDLE OBJECTS
    print(f"Loading {len(df):,} candles into memory...")
    timestamps = df['timestamp'].tolist()
    opens      = df['open'].values
    highs      = df['high'].values
    lows       = df['low'].values
    closes     = df['close'].values
    
    # We'll keep 'df' in memory for the chart builder.
    
    # Pre-calculate 1H HTF Swings (swing_lookback=5)
    print(f"Calculating {THRESHOLDS.htf_timeframe} HTF liquidity levels...")
    df_htf = df.set_index('timestamp').resample(THRESHOLDS.htf_timeframe).agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna().reset_index()
    
    htf_candles = [
        Candle(row.timestamp, row.open, row.high, row.low, row.close)
        for row in df_htf.itertuples()
    ]
    
    htf_registry = SwingRegistry(lookback=THRESHOLDS.htf_swing_lookback, prune_enabled=False)
    for h_candle in htf_candles:
        htf_registry.update(h_candle)
        
    htf_levels = []
    # Convert HTF swings to LiquidityLevels
    for h in htf_registry.confirmed_highs:
        htf_levels.append(LiquidityLevel(
            price=h.price, level_type="BSL", quality="HTF_SWING", 
            quality_rank=1, formed_at=h.candle_time, is_intact=True
        ))
    for l in htf_registry.confirmed_lows:
        htf_levels.append(LiquidityLevel(
            price=l.price, level_type="SSL", quality="HTF_SWING", 
            quality_rank=1, formed_at=l.candle_time, is_intact=True
        ))
    
    print(f"Found {len(htf_levels)} HTF levels.")

    swings = SwingRegistry()
    intact_levels = htf_levels # Start with HTF levels
    level_prices_bsl = {l.price for l in htf_levels if l.level_type == "BSL"}
    level_prices_ssl = {l.price for l in htf_levels if l.level_type == "SSL"}
    
    active_fvgs = []
    current_sweep = None
    all_results = []
    config = SimulationConfig(save_charts=save_charts)
    
    current_day = None
    daily_gex_profile = None
    
    # Output Configuration: Unique folder for each run
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = Path(output_root or r"D:\Algorithms\Dodgy Backtest Results") / f"run_{run_id}"
    output_base.mkdir(exist_ok=True, parents=True)
    
    if save_charts:
        setups_dir = output_base / "setups"
        setups_dir.mkdir(exist_ok=True, parents=True)
    
    print(f"Simulation Start: {len(timestamps):,} candles. Saving to {output_base}")

    pbar = tqdm(range(len(timestamps)), desc="Backtesting", unit="candle")
    for i in pbar:
        # Detect new day to update Gamma levels
        if current_day != timestamps[i].date():
            current_day = timestamps[i].date()
            daily_gex_profile = gamma_engine.compute_daily_gex_profile(timestamps[i], closes[i])
            
            if daily_gex_profile:
                # Add Flip level and Clusters to intact_levels
                # We mark them as formed 'yesterday' so they are immediately active
                formed_at = timestamps[i] - timedelta(days=1)
                
                # Add GEX Flip
                intact_levels.append(LiquidityLevel(
                    price=daily_gex_profile['gex_flip'], level_type="BSL", # Check both sides for sweep
                    quality="GEX_FLIP", quality_rank=2, formed_at=formed_at, is_intact=True
                ))
                intact_levels.append(LiquidityLevel(
                    price=daily_gex_profile['gex_flip'], level_type="SSL",
                    quality="GEX_FLIP", quality_rank=2, formed_at=formed_at, is_intact=True
                ))
                
                # Add Clusters
                for cluster_px in daily_gex_profile['gamma_clusters']:
                    intact_levels.append(LiquidityLevel(
                        price=cluster_px, level_type="BSL",
                        quality="GAMMA_CLUSTER", quality_rank=2, formed_at=formed_at, is_intact=True
                    ))
                    intact_levels.append(LiquidityLevel(
                        price=cluster_px, level_type="SSL",
                        quality="GAMMA_CLUSTER", quality_rank=2, formed_at=formed_at, is_intact=True
                    ))

        # Lazy create candle for the logic that needs it
        candle = Candle(timestamps[i], opens[i], highs[i], lows[i], closes[i])
        
        swings.update(candle)
        
        # Update intact levels: Only consider HTF levels that were formed BEFORE the current candle
        # We don't need the 100-candle loop for HTF levels since they are static
        
        # Sweep check on HTF levels
        sweep = detect_sweep(candle, i, [l for l in intact_levels if l.formed_at < candle.timestamp])
        if sweep:
            current_sweep = sweep
        elif current_sweep:
            current_sweep.bars_since_sweep += 1
            if current_sweep.bars_since_sweep > THRESHOLDS.sweep_context_max_bars:
                current_sweep = None
        
        # FVG tracking
        new_fvg = detect_fvg(swings.candle_buffer, i)
        if new_fvg:
            active_fvgs.append(new_fvg)
            
        # IFVG Inversion logic
        if current_sweep:
            # Look for inversion of a recent FVG in the opposite direction
            bias_direction = "BULLISH" if current_sweep.direction == "SSL_SWEPT" else "BEARISH"
            target_fvg_dir = "BEARISH" if bias_direction == "BULLISH" else "BULLISH"
            
            # Check the most recent 10 FVGs for inversion
            for fvg in active_fvgs[-10:]:
                if fvg.direction == target_fvg_dir and fvg.is_intact:
                    # Check for inversion by body close
                    if bias_direction == "BULLISH":
                        if candle.close > fvg.fvg_top and candle.open < fvg.fvg_top:
                            # Inversion Triggered!
                            ih = swings.get_nearest_high_above(candle.close)
                            targ = ih.price if ih else candle.close + 40.0
                            
                            # MATH OPTIMIZATION: Limit order at FVG top instead of market at close
                            entry = fvg.fvg_top
                            stop  = current_sweep.sweep_candle.low - 2.0
                            risk  = entry - stop
                            if risk <= 0: continue # Invalid setup
                            
                            setup = TradeSetup(
                                setup_id=f"L-REV-{candle.timestamp.strftime('%Y%m%d%H%M')}",
                                created_at=candle.timestamp,
                                symbol="NQ", timeframe="1m", direction=Direction.LONG,
                                model_type=ModelType.REVERSAL, 
                                grade=SignalGrade.MECHANICAL if (not ih or candle.high < ih.price) else SignalGrade.ADVANCED,
                                entry_price=entry,
                                stop_type=StopType.SWING_STOP,
                                stop_price=stop,
                                target_price=targ,
                                break_even_trigger=entry + risk, # 1:1 RR BE Strategy
                                invalidation_price=current_sweep.sweep_candle.low,
                                expiry_time=None,
                                internal_level=ih.price if ih else 0.0,
                                risk_reward=(targ - entry) / risk,
                                momentum_score=candle.body_ratio,
                                reasoning=f"HTF Sweep ({current_sweep.swept_level.quality}) + IFVG Bullish Inversion"
                            )
                            
                            if setup.risk_reward >= 1.5:
                                # ── ML Filtering Inference ──────────────────────
                                if ml_model:
                                    context = {"gamma": daily_gex_profile}
                                    feats = feature_extractor.get_features(setup, context)
                                    f_df = pd.DataFrame([feats]).drop(columns=['setup_id', 'timestamp'], errors='ignore')
                                    prob = ml_model.predict(xgb.DMatrix(f_df))[0]
                                    if prob < ml_threshold:
                                        continue

                                result = evaluate_setup(setup, timestamps, highs, lows, closes, i, config)
                                result.net_pnl = calculate_net_pnl(result, 1, config)
                                all_results.append(result)

                                # ML Feature Extraction
                                if extract_features:
                                    context = {"gamma": daily_gex_profile}
                                    feats = feature_extractor.get_features(setup, context)
                                    feats['setup_id'] = setup.setup_id
                                    feats['timestamp'] = setup.created_at.strftime('%Y-%m-%d %H:%M:%S')
                                    feats['label'] = 1 # We'll update this if exit_type is STOP
                                    trade_features.append(feats)

                                if save_charts:
                                    chart = build_setup_chart(result, df)
                                    chart.write_html(str(setups_dir / f"{setup.setup_id}.html"))
                                current_sweep = None
                                pbar.set_postfix(trades=len(all_results))
                                break
                    else:
                        # SHORT Logic
                        if candle.close < fvg.fvg_bottom and candle.open > fvg.fvg_bottom:
                            # Inversion Triggered!
                            il = swings.get_nearest_low_below(candle.close)
                            targ = il.price if il else candle.close - 40.0
                            
                            # MATH OPTIMIZATION: Limit order at FVG bottom instead of market at close
                            entry = fvg.fvg_bottom
                            stop  = current_sweep.sweep_candle.high + 2.0
                            risk  = stop - entry
                            if risk <= 0: continue
                            
                            setup = TradeSetup(
                                setup_id=f"S-REV-{candle.timestamp.strftime('%Y%m%d%H%M')}",
                                created_at=candle.timestamp,
                                symbol="NQ", timeframe="1m", direction=Direction.SHORT,
                                model_type=ModelType.REVERSAL,
                                grade=SignalGrade.MECHANICAL if (not il or candle.low > il.price) else SignalGrade.ADVANCED,
                                entry_price=entry,
                                stop_type=StopType.SWING_STOP,
                                stop_price=stop,
                                target_price=targ,
                                break_even_trigger=entry - risk, # 1:1 RR BE Strategy
                                invalidation_price=current_sweep.sweep_candle.high,
                                expiry_time=None,
                                internal_level=il.price if il else 0.0,
                                risk_reward=(entry - targ) / risk,
                                momentum_score=candle.body_ratio,
                                reasoning=f"HTF Sweep ({current_sweep.swept_level.quality}) + IFVG Bearish Inversion"
                            )
                            
                            if setup.risk_reward >= 1.5:
                                # ── ML Filtering Inference ──────────────────────
                                if ml_model:
                                    context = {"gamma": daily_gex_profile}
                                    feats = feature_extractor.get_features(setup, context)
                                    f_df = pd.DataFrame([feats]).drop(columns=['setup_id', 'timestamp'], errors='ignore')
                                    prob = ml_model.predict(xgb.DMatrix(f_df))[0]
                                    if prob < ml_threshold:
                                        continue

                                result = evaluate_setup(setup, timestamps, highs, lows, closes, i, config)
                                result.net_pnl = calculate_net_pnl(result, 1, config)
                                all_results.append(result)

                                # ML Feature Extraction
                                if extract_features:
                                    context = {"gamma": daily_gex_profile}
                                    feats = feature_extractor.get_features(setup, context)
                                    feats['setup_id'] = setup.setup_id
                                    feats['timestamp'] = setup.created_at.strftime('%Y-%m-%d %H:%M:%S')
                                    feats['label'] = 1
                                    trade_features.append(feats)

                                if save_charts:
                                    chart = build_setup_chart(result, df)
                                    chart.write_html(str(setups_dir / f"{setup.setup_id}.html"))
                                current_sweep = None
                                pbar.set_postfix(trades=len(all_results))
                                break

        # Prune old FVGs/Levels and keep list small
        if i % 1000 == 0:
            active_fvgs   = active_fvgs[-100:]
            pbar.set_postfix(trades=len(all_results))
            
    print(f"Simulation Finished: {len(timestamps):,} / {len(timestamps):,} candles. Total Trades: {len(all_results)}")
    
    summary = get_performance_summary(all_results, 100_000.0)
    if summary:
        print("\n" + "="*40)
        print("INSTITUTIONAL PERFORMANCE REPORT")
        print("="*40)
        print(f"Total Net P&L (1 contract): ${summary['total_pnl']:,.2f}")
        print(f"Win Rate:                   {summary['win_rate']:,.1%}")
        print(f"Sharpe Ratio:               {summary['sharpe']:,.2f}")
        print(f"Sortino Ratio:              {summary['sortino']:,.2f}")
        print(f"Max Drawdown:               {summary['max_drawdown']:,.2%}")
        print("="*40)
    
    # ── Generate trades.csv ─────────────────────────────────────
    trade_rows = []
    for r in all_results:
        entry = r.setup.entry_price
        stop = r.setup.stop_price
        risk = abs(entry - stop)
        if r.setup.direction == Direction.LONG:
            pnl_pts = r.exit_price - entry
        else:
            pnl_pts = entry - r.exit_price
        
        trade_rows.append({
            "date": r.setup.created_at.strftime('%Y-%m-%d'),
            "setup_id": r.setup.setup_id,
            "direction": r.setup.direction.value,
            "session": _classify_session(r.setup.created_at),
            "entry_price": round(entry, 2),
            "stop_price": round(stop, 2),
            "target_price": round(r.setup.target_price, 2),
            "risk_points": round(risk, 2),
            "exit_price": round(r.exit_price, 2),
            "exit_type": r.exit_type,
            "pnl_points": round(pnl_pts, 2),
            "pnl_usd": round(r.net_pnl, 2),
            "r_multiple": round(pnl_pts / risk, 2) if risk > 0 else 0.0,
            "risk_reward": round(r.setup.risk_reward, 2),
            "reasoning": r.setup.reasoning
        })
    
    pd.DataFrame(trade_rows).to_csv(output_base / "trades.csv", index=False)
    print(f"Trade log saved: {output_base / 'trades.csv'} ({len(trade_rows)} trades)")

    # ── Save ML Features ────────────────────────────────────────
    if extract_features and trade_features:
        # Update labels based on actual result
        results_map = {r.setup.setup_id: r for r in all_results}
        for f in trade_features:
            res = results_map.get(f['setup_id'])
            if res:
                f['label'] = 1 if res.exit_type == "TARGET_HIT" else 0
        
        pd.DataFrame(trade_features).to_csv(output_base / "features.csv", index=False)
        print(f"ML Features saved: {output_base / 'features.csv'}")

        # ── Automated ML Training ───────────────────────────────
        if (ml_config and ml_config.get('run_ml')) or (ml_config and ml_config.get('auto_optimize')):
            print("\n" + "═"*40)
            print("AUTO-ML OPTIMIZATION STARTING")
            print("═"*40)
            
            output_dir = ml_config.get('out_dir') or str(output_base / "ml_optimization")
            if ml_config.get('auto_optimize'):
                output_dir = "models/latest"
            
            pipeline = MLPipeline(
                data_path=str(output_base / "features.csv"),
                output_dir=output_dir,
                train_start=ml_config.get('train_start'),
                train_end=ml_config.get('train_end'),
                test_start=ml_config.get('test_start'),
                test_end=ml_config.get('test_end')
            )
            pipeline.run()
            
            if ml_config.get('auto_optimize'):
                print(f"✅ Auto-Optimization Complete. Model saved to: {output_dir}")
                print(f"👉 To use this model, run: python main.py --optimized")
    
    # ── Generate HTML Dashboard ─────────────────────────────────
    dashboard_path = generate_dashboard(
        results=all_results,
        output_path=str(output_base / "dashboard.html"),
        initial_capital=100_000.0,
        title="DodgysDD IFVG Mechanical Backtest"
    )
    print(f"Dashboard saved: {dashboard_path}")
    
    # Auto-open dashboard in browser
    webbrowser.open(f"file:///{Path(dashboard_path).resolve().as_posix()}")
    
    return all_results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DodgysDD Backtest Engine")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)", default=None)
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)", default=None)
    parser.add_argument("--data", type=str, help="Path to parquet data", default="data/nq_1min_10y.parquet")
    parser.add_argument("--output-root", type=str, default=r"D:\Algorithms\Dodgy Backtest Results",
                        help="Root output directory")
    parser.add_argument("--no-charts", action="store_true", help="Skip per-trade Plotly HTML charts")
    parser.add_argument("--extract-features", action="store_true", help="Extract ML features for trades")
    
    # ML Chaining Arguments
    parser.add_argument("--run-ml", action="store_true", help="Run ML pipeline immediately after backtest")
    parser.add_argument("--train-start", type=str, help="ML Train Start (YYYY-MM-DD)")
    parser.add_argument("--train-end", type=str, help="ML Train End (YYYY-MM-DD)")
    parser.add_argument("--test-start", type=str, help="ML Test Start (YYYY-MM-DD)")
    parser.add_argument("--test-end", type=str, help="ML Test End (YYYY-MM-DD)")
    parser.add_argument("--out", type=str, help="Custom output directory for ML models")
    
    # Inference Filtering
    parser.add_argument("--use-ml", action="store_true", help="Apply ML model to filter trades in backtest")
    parser.add_argument("--model-path", type=str, help="Path to trained xgboost_model.json")
    parser.add_argument("--ml-threshold", type=float, default=0.5, help="Minimum probability to take trade")
    
    # Simplify Life flags
    parser.add_argument("--auto-optimize", action="store_true", help="One-click full training with safe defaults")
    parser.add_argument("--optimized", action="store_true", help="Run backtest using the latest trained model")

    args = parser.parse_args()
    
    # Sensible defaults for auto-optimize (only if not provided by user)
    train_start = args.train_start
    train_end = args.train_end
    if args.auto_optimize:
        if not train_start: train_start = "2020-01-01"
        if not train_end:   train_end = "2024-12-31"

    # Sync Backtest window with ML window for speed
    backtest_start = args.start
    backtest_end = args.end
    if args.auto_optimize:
        if not backtest_start: backtest_start = train_start
        # If user provided a test window, make sure backtest includes it
        if not backtest_end: 
            if args.test_end: backtest_end = args.test_end
            elif args.test_start: backtest_end = None # Run until actual end
            else: backtest_end = train_end

    ml_config = {
        'run_ml': args.run_ml or args.auto_optimize,
        'auto_optimize': args.auto_optimize,
        'train_start': train_start,
        'train_end': train_end,
        'test_start': args.test_start,
        'test_end': args.test_end,
        'out_dir': args.out
    }

    run_backtest(
        args.data,
        start_date=backtest_start,
        end_date=backtest_end,
        output_root=args.output_root,
        save_charts=not args.no_charts,
        extract_features=args.extract_features or ml_config['run_ml'] or args.optimized,
        ml_config=ml_config,
        use_ml=args.use_ml or args.optimized,
        model_path=args.model_path,
        ml_threshold=args.ml_threshold,
        optimized=args.optimized
    )
