import pandas as pd
import numpy as np
import os
import webbrowser
import xgboost as xgb
from collections import deque
from pathlib import Path
from datetime import datetime, timedelta
from src.core import Candle, NQ, THRESHOLDS
from src.swings import SwingRegistry
from src.liquidity import LiquidityLevel, SweepEvent
from src.execution import (
    TradeSetup, Direction, ModelType, StopType,
    SignalGrade, SimulationConfig, TradeResult, SizingMode
)
from src.vectorized import (
    compute_swings_vectorized,
    FastSwingLookup,
    compute_fvgs_vectorized,
    evaluate_setup_fast,
    VectorizedSweepDetector,
)
from tqdm import tqdm
from src.plotting import build_setup_chart
from src.metrics import get_performance_summary
from src.dashboard import generate_dashboard
from src.gamma import SyntheticGammaEngine
from src.ml_features import FeatureExtractor, nearest_cluster_distance
from src.ml_pipeline import MLPipeline

# ── Simulation Runner ───────────────────────────────────────────

def calculate_contracts(setup: TradeSetup, config: SimulationConfig, current_capital: float) -> int:
    if config.sizing_mode == SizingMode.FIXED:
        return config.fixed_contracts

    risk_points = abs(setup.entry_price - setup.stop_price)
    if risk_points <= 0:
        return config.min_contracts

    risk_dollars   = current_capital * config.risk_per_trade_pct
    contract_risk  = risk_points * config.point_value

    if contract_risk <= 0:
        return config.min_contracts

    contracts = int(risk_dollars // contract_risk)
    return max(config.min_contracts, min(contracts, config.max_contracts))

def calculate_contracts(setup: TradeSetup, config: SimulationConfig, current_capital: float) -> int:
    if config.sizing_mode == SizingMode.FIXED:
        return config.fixed_contracts
    
    # Risk-based sizing
    risk_points = abs(setup.entry_price - setup.stop_price)
    if risk_points <= 0:
        return config.min_contracts
        
    risk_dollars = current_capital * config.risk_per_trade_pct
    contract_risk = risk_points * config.point_value
    
    if contract_risk <= 0:
        return config.min_contracts
        
    contracts = int(risk_dollars // contract_risk)
    return max(config.min_contracts, min(contracts, config.max_contracts))

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
    comm  = config.commission_per_rt * contracts
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


def passes_research_filter(setup: TradeSetup, filter_mode: str = "none",
                           cluster_max_dist: float = 150.67,
                           nearest_cluster_dist_val: float = 999.0) -> bool:
    """Optional simple rule-based filters discovered in walk-forward research."""
    if filter_mode == "none":
        return True

    session = _classify_session(setup.created_at)

    if filter_mode == "cluster_near":
        return float(nearest_cluster_dist_val) <= cluster_max_dist

    if filter_mode == "pre_market_power_hour":
        return session in {"pre_market", "power_hour"}

    if filter_mode == "pre_market_long":
        return session == "pre_market" and setup.direction == Direction.LONG

    return True


def build_rule_filter_context(setup: TradeSetup, rule_filter: str, gamma_context) -> float:
    """Return the only extra value current rule filters need beyond the setup."""
    if rule_filter == "cluster_near":
        return nearest_cluster_distance(setup.entry_price, gamma_context)
    return 999.0


# ── Main Loop ───────────────────────────────────────────────────

def run_backtest(data_path: str, start_date=None, end_date=None, output_root=None, save_charts=False, extract_features=False, ml_config=None, use_ml=False, model_path=None, ml_threshold=0.5, optimized=False, rule_filter="cluster_near", cluster_max_dist=150.67):

    # Initialize Gamma Engine (year-level cache: parquet loaded once per year)
    try:
        gamma_engine = SyntheticGammaEngine(
            options_dir="data/DownloadedOptions/qqq",
            underlying_path="data/DownloadedOptions/qqq/underlying.parquet"
        )
    except Exception as e:
        print(f"Warning: Gamma Engine disabled ({e})")
        gamma_engine = None
    feature_extractor = FeatureExtractor()
    trade_features = []

    # ML Model Loading
    ml_model = None
    if use_ml or optimized:
        actual_path = model_path if model_path else "models/latest/xgboost_model.json"
        if os.path.exists(actual_path):
            print(f"RUNNING OPTIMIZED: {actual_path} (Threshold: {ml_threshold})")
            ml_model = xgb.Booster()
            ml_model.load_model(actual_path)
        else:
            print(f"Warning: Optimized model not found at {actual_path}. Running naked backtest.")

    if str(data_path).endswith('.parquet'):
        df = pd.read_parquet(data_path)
    else:
        print(f"Loading CSV data from {data_path}...")
        # Institutional format: Semicolon delimited, Comma decimal
        df = pd.read_csv(data_path, sep=';', decimal=',')
        # Map institutional columns to our internal format
        col_map = {
            'Date': 'timestamp',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }
        df = df.rename(columns=col_map)
        
    # Use specified format for institutional NQ CSV if not parquet
    dt_format = None if str(data_path).endswith('.parquet') else "%m/%d/%Y %I:%M %p"
    df['timestamp'] = pd.to_datetime(df['timestamp'], format=dt_format, errors='coerce')
    df = df.dropna(subset=['timestamp']).reset_index(drop=True)

    if start_date:
        df = df[df['timestamp'] >= start_date].reset_index(drop=True)
    if end_date:
        df = df[df['timestamp'] < end_date].reset_index(drop=True)

    print(f"Loading {len(df):,} candles into memory...")
    timestamps = df['timestamp'].tolist()
    opens      = df['open'].values
    highs      = df['high'].values
    lows       = df['low'].values
    closes     = df['close'].values
    n_bars     = len(timestamps)

    # Precompute normalized day keys once so the day-change check stays on
    # compact numpy values instead of creating Python date objects per bar.
    ts_days = df['timestamp'].to_numpy(dtype='datetime64[D]')

    # ── ATR Scaling Engine ──────────────────────────────────────────────
    atr_array = None
    if getattr(THRESHOLDS, 'use_atr_scaling', False):
        print("Calculating Dynamic ATR threshold arrays...")
        c_prev = np.zeros_like(closes)
        if n_bars > 0:
            c_prev[1:] = closes[:-1]
            c_prev[0]  = opens[0]
            
        tr1 = highs - lows
        tr2 = np.abs(highs - c_prev)
        tr3 = np.abs(lows - c_prev)
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        atr_array = pd.Series(tr).rolling(window=THRESHOLDS.atr_period, min_periods=1).mean().values
        
        # Inject dynamic arrays to THRESHOLDS for vectorized pre-evaluation
        THRESHOLDS.min_swing_size_points_arr = atr_array * getattr(THRESHOLDS, 'atr_min_swing_mult', 0.5)
        THRESHOLDS.min_fvg_size_points_arr = atr_array * getattr(THRESHOLDS, 'atr_min_fvg_mult', 0.3)
        THRESHOLDS.min_impulse_size_points_arr = atr_array * getattr(THRESHOLDS, 'atr_min_impulse_mult', 0.4)

    # ── Pre-calculate 1H HTF Swings ─────────────────────────────
    print(f"Calculating {THRESHOLDS.htf_timeframe} HTF liquidity levels...")
    df_htf = df.set_index('timestamp').resample(THRESHOLDS.htf_timeframe).agg(
        {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
    ).dropna().reset_index()

    htf_candles = [
        Candle(row.timestamp, row.open, row.high, row.low, row.close)
        for row in df_htf.itertuples()
    ]
    htf_registry = SwingRegistry(lookback=THRESHOLDS.htf_swing_lookback, prune_enabled=False)
    for h_candle in htf_candles:
        htf_registry.update(h_candle)

    htf_levels = []
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

    # ── Precompute ALL 1m swings vectorized ──────────────────────
    print("Precomputing 1m swings (vectorized)...")
    confirmed_highs, confirmed_lows = compute_swings_vectorized(
        highs, lows, timestamps,
        lookback=THRESHOLDS.swing_lookback,
        min_size=getattr(THRESHOLDS, 'min_swing_size_points_arr', THRESHOLDS.min_swing_size_points),
    )
    swing_lookup = FastSwingLookup(confirmed_highs, confirmed_lows, THRESHOLDS.swing_lookback)
    print(f"  {len(confirmed_highs):,} swing highs, {len(confirmed_lows):,} swing lows found.")

    # ── Precompute ALL FVGs vectorized ──────────────────────────
    print("Precomputing FVGs (vectorized)...")
    all_fvgs_precomputed = compute_fvgs_vectorized(opens, highs, lows, closes, timestamps)
    n_fvgs = len(all_fvgs_precomputed)
    print(f"  {n_fvgs:,} FVGs detected.")

    # ── Simulation state ─────────────────────────────────────────
    # VectorizedSweepDetector keeps parallel numpy arrays of level prices so
    # each bar does 2 numpy batch checks instead of an O(n_levels) Python loop.
    sweep_detector  = VectorizedSweepDetector(htf_levels, THRESHOLDS)
    active_fvgs     = deque(maxlen=100)
    fvg_ptr         = 0                  # pointer into all_fvgs_precomputed
    current_sweep   = None
    all_results     = []
    config = SimulationConfig(
        save_charts=save_charts,
        sizing_mode=ml_config.get('sizing_mode', SizingMode.FIXED),
        fixed_contracts=ml_config.get('contracts', 1),
        risk_per_trade_pct=ml_config.get('risk_pct', 0.01),
        slippage_ticks=ml_config.get('slippage_ticks', 0)
    )
    current_equity = config.starting_capital
    current_day      = None
    daily_gex_profile = None

    run_id      = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_base = Path(output_root or r"D:\Algorithms\Dodgy Backtest Results") / f"run_{run_id}"
    output_base.mkdir(exist_ok=True, parents=True)

    if save_charts:
        setups_dir = output_base / "setups"
        setups_dir.mkdir(exist_ok=True, parents=True)

    print(f"Simulation Start: {n_bars:,} candles. Saving to {output_base}")
    if rule_filter != "none":
        print(f"Research filter active: {rule_filter} (cluster_max_dist={cluster_max_dist})")

    # ── Thresholds cached as locals (avoids attribute lookup in tight loop) ─
    sweep_max_bars = THRESHOLDS.sweep_context_max_bars

    pbar = tqdm(range(n_bars), desc="Backtesting", unit="candle", mininterval=1.0)
    for i in pbar:
        # ── Day-change: compute GEX profile and add new levels ─────────────
        day_i = ts_days[i]
        if current_day != day_i:
            current_day = day_i
            daily_gex_profile = gamma_engine.compute_daily_gex_profile(timestamps[i], closes[i])

            if daily_gex_profile:
                formed_at = timestamps[i] - timedelta(days=1)
                new_levels = [
                    LiquidityLevel(daily_gex_profile['gex_flip'], "BSL", "GEX_FLIP",      2, formed_at, True),
                    LiquidityLevel(daily_gex_profile['gex_flip'], "SSL", "GEX_FLIP",      2, formed_at, True),
                    *[LiquidityLevel(px, "BSL", "GAMMA_CLUSTER", 2, formed_at, True) for px in daily_gex_profile['gamma_clusters']],
                    *[LiquidityLevel(px, "SSL", "GAMMA_CLUSTER", 2, formed_at, True) for px in daily_gex_profile['gamma_clusters']],
                ]
                sweep_detector.flush_gamma_levels()
                sweep_detector.add_levels(new_levels)

        # ── Advance FVG pointer: make newly confirmed FVGs visible ──────────
        # (replaces: detect_fvg(swings.candle_buffer, i) + candle_buffer append)
        while fvg_ptr < n_fvgs and all_fvgs_precomputed[fvg_ptr].c3_index <= i:
            active_fvgs.append(all_fvgs_precomputed[fvg_ptr])
            fvg_ptr += 1

        # ── Sweep detection (inline, no Candle allocation on the hot path) ──
        # The formed_at < candle.timestamp filter from the original is always
        # satisfied here because:
        #   - HTF levels are formed before the first bar in the scan window
        #   - GEX levels use formed_at = timestamps[day_start] - 1 day,
        #     which is always < any subsequent candle's timestamp
        # So we skip that filter and just check is_intact.
        h_i = highs[i]
        l_i = lows[i]
        c_i = closes[i]
        ts_i = timestamps[i]

        curr_atr = atr_array[i] if atr_array is not None else None
        sweep = sweep_detector.detect(opens[i], h_i, l_i, c_i, ts_i, i, atr_value=curr_atr)
        if sweep:
            current_sweep = sweep
        elif current_sweep:
            current_sweep.bars_since_sweep += 1
            if current_sweep.bars_since_sweep > sweep_max_bars:
                current_sweep = None

        # ── IFVG Inversion signal check ─────────────────────────────────────
        if current_sweep:
            bias_direction = "BULLISH" if current_sweep.direction == "SSL_SWEPT" else "BEARISH"
            target_fvg_dir = "BEARISH" if bias_direction == "BULLISH" else "BULLISH"

            for fvg in list(active_fvgs)[-10:]:
                if fvg.direction == target_fvg_dir and fvg.is_intact:
                    if bias_direction == "BULLISH":
                        # Body close above FVG top (IFVG bullish inversion trigger)
                        if c_i > fvg.fvg_top and opens[i] < fvg.fvg_top:
                            ih   = swing_lookup.get_nearest_high_above(i, c_i)
                            
                            if atr_array is not None and getattr(THRESHOLDS, 'use_atr_scaling', False):
                                targ_dist = curr_atr * THRESHOLDS.atr_min_target_mult
                            else:
                                targ_dist = THRESHOLDS.min_target_distance_points
                            
                            targ_px = ih.price if ih else c_i + targ_dist
                            # Use max function so our minimum target distance is preserved even if IH is too close
                            targ = max(targ_px, c_i + targ_dist)
                            
                            entry = fvg.fvg_top
                            stop  = current_sweep.sweep_candle.low - 2.0
                            risk  = entry - stop
                            if risk <= 0:
                                continue

                            setup = TradeSetup(
                                setup_id=f"L-REV-{ts_i.strftime('%Y%m%d%H%M')}",
                                created_at=ts_i,
                                symbol="NQ", timeframe="1m", direction=Direction.LONG,
                                model_type=ModelType.REVERSAL,
                                grade=SignalGrade.MECHANICAL if (not ih or h_i < ih.price) else SignalGrade.ADVANCED,
                                entry_price=entry,
                                stop_type=StopType.SWING_STOP,
                                stop_price=stop,
                                target_price=targ,
                                break_even_trigger=entry + risk,
                                invalidation_price=current_sweep.sweep_candle.low,
                                expiry_time=None,
                                internal_level=ih.price if ih else 0.0,
                                risk_reward=(targ - entry) / risk,
                                momentum_score=(abs(c_i - opens[i]) / (h_i - l_i)) if (h_i - l_i) > 0 else 0.0,
                                reasoning=f"HTF Sweep ({current_sweep.swept_level.quality}) + IFVG Bullish Inversion"
                            )

                            if setup.risk_reward >= 1.5:
                                context = {"gamma": daily_gex_profile}
                                rule_cluster_dist = build_rule_filter_context(setup, rule_filter, daily_gex_profile)
                                if not passes_research_filter(
                                    setup,
                                    rule_filter,
                                    cluster_max_dist,
                                    nearest_cluster_dist_val=rule_cluster_dist,
                                ):
                                    continue

                                feats = None
                                if ml_model:
                                    feats = feature_extractor.get_features(setup, context)
                                    f_df  = pd.DataFrame([feats]).drop(columns=['setup_id', 'timestamp'], errors='ignore')
                                    prob  = ml_model.predict(xgb.DMatrix(f_df))[0]
                                    if prob < ml_threshold:
                                        continue

                                result    = evaluate_setup_fast(setup, timestamps, highs, lows, closes, i, config)
                                contracts = calculate_contracts(setup, config, current_equity)
                                result.net_pnl = calculate_net_pnl(result, contracts, config)
                                current_equity += result.net_pnl
                                all_results.append(result)

                                if extract_features:
                                    if feats is None:
                                        feats = feature_extractor.get_features(setup, context)
                                    feats_out = dict(feats)
                                    feats_out['setup_id']  = setup.setup_id
                                    feats_out['timestamp'] = setup.created_at.strftime('%Y-%m-%d %H:%M:%S')
                                    feats_out['label']     = 1
                                    trade_features.append(feats_out)

                                if save_charts:
                                    chart = build_setup_chart(result, df)
                                    chart.write_html(str(setups_dir / f"{setup.setup_id}.html"))
                                current_sweep = None
                                break

                    else:  # BEARISH bias
                        if c_i < fvg.fvg_bottom and opens[i] > fvg.fvg_bottom:
                            il   = swing_lookup.get_nearest_low_below(i, c_i)
                            
                            if atr_array is not None and getattr(THRESHOLDS, 'use_atr_scaling', False):
                                targ_dist = curr_atr * THRESHOLDS.atr_min_target_mult
                            else:
                                targ_dist = THRESHOLDS.min_target_distance_points
                            
                            targ_px = il.price if il else c_i - targ_dist
                            targ = min(targ_px, c_i - targ_dist)
                            
                            entry = fvg.fvg_bottom
                            stop  = current_sweep.sweep_candle.high + 2.0
                            risk  = stop - entry
                            if risk <= 0:
                                continue

                            setup = TradeSetup(
                                setup_id=f"S-REV-{ts_i.strftime('%Y%m%d%H%M')}",
                                created_at=ts_i,
                                symbol="NQ", timeframe="1m", direction=Direction.SHORT,
                                model_type=ModelType.REVERSAL,
                                grade=SignalGrade.MECHANICAL if (not il or l_i > il.price) else SignalGrade.ADVANCED,
                                entry_price=entry,
                                stop_type=StopType.SWING_STOP,
                                stop_price=stop,
                                target_price=targ,
                                break_even_trigger=entry - risk,
                                invalidation_price=current_sweep.sweep_candle.high,
                                expiry_time=None,
                                internal_level=il.price if il else 0.0,
                                risk_reward=(entry - targ) / risk,
                                momentum_score=(abs(c_i - opens[i]) / (h_i - l_i)) if (h_i - l_i) > 0 else 0.0,
                                reasoning=f"HTF Sweep ({current_sweep.swept_level.quality}) + IFVG Bearish Inversion"
                            )

                            if setup.risk_reward >= 1.5:
                                context = {"gamma": daily_gex_profile}
                                rule_cluster_dist = build_rule_filter_context(setup, rule_filter, daily_gex_profile)
                                if not passes_research_filter(
                                    setup,
                                    rule_filter,
                                    cluster_max_dist,
                                    nearest_cluster_dist_val=rule_cluster_dist,
                                ):
                                    continue

                                feats = None
                                if ml_model:
                                    feats = feature_extractor.get_features(setup, context)
                                    f_df  = pd.DataFrame([feats]).drop(columns=['setup_id', 'timestamp'], errors='ignore')
                                    prob  = ml_model.predict(xgb.DMatrix(f_df))[0]
                                    if prob < ml_threshold:
                                        continue

                                result    = evaluate_setup_fast(setup, timestamps, highs, lows, closes, i, config)
                                contracts = calculate_contracts(setup, config, current_equity)
                                result.net_pnl = calculate_net_pnl(result, contracts, config)
                                current_equity += result.net_pnl
                                all_results.append(result)

                                if extract_features:
                                    if feats is None:
                                        feats = feature_extractor.get_features(setup, context)
                                    feats_out = dict(feats)
                                    feats_out['setup_id']  = setup.setup_id
                                    feats_out['timestamp'] = setup.created_at.strftime('%Y-%m-%d %H:%M:%S')
                                    feats_out['label']     = 1
                                    trade_features.append(feats_out)

                                if save_charts:
                                    chart = build_setup_chart(result, df)
                                    chart.write_html(str(setups_dir / f"{setup.setup_id}.html"))
                                current_sweep = None
                                break

        # ── Periodic housekeeping ────────────────────────────────────────────
        if i % 1000 == 0:
            # Prune levels that have been invalidated – prevents the list from
            # growing to 30K+ entries over a 10-year run, which would make the
            # sweep loop O(n_levels × n_bars) in Python.
            sweep_detector.prune()
            pbar.set_postfix(trades=len(all_results))

    print(f"Simulation Finished: {n_bars:,} / {n_bars:,} candles. Total Trades: {len(all_results)}")

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
        stop  = r.setup.stop_price
        risk  = abs(entry - stop)
        if r.setup.direction == Direction.LONG:
            pnl_pts = r.exit_price - entry
        else:
            pnl_pts = entry - r.exit_price

        trade_rows.append({
            "date"        : r.setup.created_at.strftime('%Y-%m-%d'),
            "setup_id"    : r.setup.setup_id,
            "direction"   : r.setup.direction.value,
            "session"     : _classify_session(r.setup.created_at),
            "entry_time"  : r.setup.created_at.strftime('%Y-%m-%dT%H:%M:%S'),
            "exit_time"   : r.exit_candle_time.strftime('%Y-%m-%dT%H:%M:%S'),
            "hold_minutes": round((r.exit_candle_time - r.setup.created_at).total_seconds() / 60.0, 2),
            "entry_price" : round(entry, 2),
            "stop_price"  : round(stop, 2),
            "target_price": round(r.setup.target_price, 2),
            "risk_points" : round(risk, 2),
            "exit_price"  : round(r.exit_price, 2),
            "exit_type"   : r.exit_type,
            "pnl_points"  : round(pnl_pts, 2),
            "pnl_usd"     : round(r.net_pnl, 2),
            "r_multiple"  : round(pnl_pts / risk, 2) if risk > 0 else 0.0,
            "risk_reward" : round(r.setup.risk_reward, 2),
            "reasoning"   : r.setup.reasoning
        })

    pd.DataFrame(trade_rows).to_csv(output_base / "trades.csv", index=False)
    print(f"Trade log saved: {output_base / 'trades.csv'} ({len(trade_rows)} trades)")

    # ── Save ML Features ────────────────────────────────────────
    if extract_features and trade_features:
        results_map = {r.setup.setup_id: r for r in all_results}
        for f in trade_features:
            res = results_map.get(f['setup_id'])
            if res:
                f['label'] = 1 if res.exit_type == "TARGET_HIT" else 0

        pd.DataFrame(trade_features).to_csv(output_base / "features.csv", index=False)
        print(f"ML Features saved: {output_base / 'features.csv'}")

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
    webbrowser.open(f"file:///{Path(dashboard_path).resolve().as_posix()}")
    return all_results, config
    return all_results, config

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
    parser.add_argument("--contracts", type=int, default=1, help="Fixed contracts (if mode is fixed)")
    parser.add_argument("--risk-pct", type=float, default=0.01, help="Risk percentage (e.g. 0.01 for 1%%)")
    parser.add_argument("--sizing", type=str, choices=["fixed", "risk"], default="fixed", help="Sizing mode")
    parser.add_argument("--run-ml", action="store_true", help="Run ML pipeline immediately after backtest")
    parser.add_argument("--train-start", type=str, help="ML Train Start (YYYY-MM-DD)")
    parser.add_argument("--train-end", type=str, help="ML Train End (YYYY-MM-DD)")
    parser.add_argument("--test-start", type=str, help="ML Test Start (YYYY-MM-DD)")
    parser.add_argument("--test-end", type=str, help="ML Test End (YYYY-MM-DD)")
    parser.add_argument("--out", type=str, help="Custom output directory for ML models")

    parser.add_argument("--use-ml", action="store_true", help="Apply ML model to filter trades in backtest")
    parser.add_argument("--model-path", type=str, help="Path to trained xgboost_model.json")
    parser.add_argument("--ml-threshold", type=float, default=0.20, help="Minimum probability to take trade")
    parser.add_argument("--rule-filter", type=str, choices=["none", "cluster_near", "pre_market_power_hour", "pre_market_long"],
                        default="cluster_near", help="Apply a simple non-ML research filter during backtest")
    parser.add_argument("--cluster-max-dist", type=float, default=150.67,
                        help="Max nearest gamma-cluster distance for cluster_near filter")

    parser.add_argument("--auto-optimize", action="store_true", help="One-click full training with safe defaults")
    parser.add_argument("--optimized", action="store_true", help="Run backtest using the latest trained model")

    args = parser.parse_args()

    train_start = args.train_start
    train_end   = args.train_end
    if args.auto_optimize:
        if not train_start: train_start = "2020-01-01"
        if not train_end:   train_end   = "2024-12-31"

    backtest_start = args.start
    backtest_end   = args.end
    if args.auto_optimize:
        if not backtest_start: backtest_start = train_start
        if not backtest_end:
            if args.test_end:    backtest_end = args.test_end
            elif args.test_start: backtest_end = None
            else:                backtest_end = train_end

    ml_config = {
        'run_ml'      : args.run_ml or args.auto_optimize,
        'auto_optimize': args.auto_optimize,
        'train_start' : train_start,
        'train_end'   : train_end,
        'test_start'  : args.test_start,
        'test_end'    : args.test_end,
        'out_dir'     : args.out,
        'sizing_mode' : SizingMode.RISK_PCT if args.sizing == "risk" else SizingMode.FIXED,
        'contracts'   : args.contracts,
        'risk_pct'    : args.risk_pct
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
        optimized=args.optimized,
        rule_filter=args.rule_filter,
        cluster_max_dist=args.cluster_max_dist
    )
