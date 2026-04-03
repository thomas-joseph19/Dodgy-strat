import pandas as pd
import numpy as np
import os
from pathlib import Path
from datetime import datetime, timedelta
from src.core import Candle, NQ, THRESHOLDS
from src.swings import SwingRegistry, detect_swing_high, detect_swing_low
from src.liquidity import LiquidityLevel, detect_sweep, SweepEvent
from src.fvg import detect_fvg, merge_fvg_series, FairValueGap
from src.execution import (
    TradeSetup, Direction, ModelType, StopType, 
    SignalGrade, SimulationConfig, TradeResult, TradeState
)
from src.plotting import build_setup_chart
from src.metrics import get_performance_summary

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

# ── Main Loop ───────────────────────────────────────────────────

def run_backtest(data_path: str, start_date=None):
    df = pd.read_parquet(data_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    if start_date:
        df = df[df['timestamp'] >= start_date].reset_index(drop=True)
    
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
    config = SimulationConfig(save_charts=True)
    
    # New Output Configuration: Unique folder for each run
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = Path(r"D:\Dodgy Backtest Results") / f"run_{run_id}"
    setups_dir = output_base / "setups"
    setups_dir.mkdir(exist_ok=True, parents=True)
    
    print(f"Simulation Start: {len(timestamps):,} candles. Saving to D:\\")

    for i in range(len(timestamps)):
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
                                result = evaluate_setup(setup, timestamps, highs, lows, closes, i, config)
                                result.net_pnl = calculate_net_pnl(result, 1, config)
                                all_results.append(result)
                                if config.save_charts:
                                    chart = build_setup_chart(result, df)
                                    chart.write_html(str(setups_dir / f"{setup.setup_id}.html"))
                                current_sweep = None
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
                                result = evaluate_setup(setup, timestamps, highs, lows, closes, i, config)
                                result.net_pnl = calculate_net_pnl(result, 1, config)
                                all_results.append(result)
                                if config.save_charts:
                                    chart = build_setup_chart(result, df)
                                    chart.write_html(str(setups_dir / f"{setup.setup_id}.html"))
                                current_sweep = None
                                break

        # Prune old FVGs/Levels and keep list small
        if i % 1000 == 0:
            active_fvgs   = active_fvgs[-100:]
            print(f"Processed {i:,} / {len(timestamps):,} candles... Trades so far: {len(all_results)}")
            
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
        
        # Save CSV inside the run folder
        trade_logs = []
        for r in all_results:
            trade_logs.append({
                "setup_id": r.setup.setup_id,
                "direction": r.setup.direction.value,
                "entry_time": r.setup.created_at.strftime('%Y-%m-%d %H:%M'),
                "exit_time": r.exit_candle_time.strftime('%Y-%m-%d %H:%M'),
                "exit_type": r.exit_type,
                "pnl": r.net_pnl,
                "reasoning": r.setup.reasoning
            })
        audit_path = output_base / "trade_audit.csv"
        pd.DataFrame(trade_logs).to_csv(audit_path, index=False)
        print(f"Full report and {len(all_results)} charts saved to: {output_base}")
        
    return all_results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="DodgysDD Backtest Engine")
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)", default=None)
    parser.add_argument("--data", type=str, help="Path to parquet data", default="data/nq_1min_10y.parquet")
    
    args = parser.parse_args()
    
    run_backtest(args.data, start_date=args.start)
