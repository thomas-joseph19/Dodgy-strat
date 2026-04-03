import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional
from src.models import (
    TradeSetup, SetupRegistry, Direction, ModelType, StopType, 
    SignalGrade, SweepEvent, FVGZone
)

from src.config import StrategyConfig

class SignalGenerator:
    def __init__(self, config: StrategyConfig):
        self.config = config

    def generate_setups(self, df: pd.DataFrame) -> SetupRegistry:
        registry = SetupRegistry()
        df = df.copy()
        
        active_sweep_long: Optional[SweepEvent] = None
        active_sweep_short: Optional[SweepEvent] = None
        
        # Track the highest/lowest points since sweep down/up to current bar
        max_high_since_sweep = None
        min_low_since_sweep = None
        
        # Bias Memory Tracking
        active_bias_dir: Optional[Direction] = None
        bias_leg_start = None
        bias_leg_end = None
        bias_dol = None
        bias_lowest_since_end = None
        bias_highest_since_end = None
        
        # Extract columns as arrays for fast access
        dates = df.index if isinstance(df.index, pd.DatetimeIndex) else [datetime.now()] * len(df)
        ssl_wick_sweeps = df.get('ssl_wick_sweep', pd.Series(False, index=df.index)).values
        ssl_body_sweeps = df.get('ssl_body_sweep', pd.Series(False, index=df.index)).values
        bsl_wick_sweeps = df.get('bsl_wick_sweep', pd.Series(False, index=df.index)).values
        bsl_body_sweeps = df.get('bsl_body_sweep', pd.Series(False, index=df.index)).values
        
        active_ssl_levels = df.get('active_ssl_level', pd.Series(np.nan, index=df.index)).values
        active_bsl_levels = df.get('active_bsl_level', pd.Series(np.nan, index=df.index)).values
        
        ifvg_bull_triggers = df.get('ifvg_bull_trigger', pd.Series(False, index=df.index)).values
        ifvg_bear_triggers = df.get('ifvg_bear_trigger', pd.Series(False, index=df.index)).values
        
        # Zones
        bear_tops = df.get('active_bear_zone_top', pd.Series(np.nan, index=df.index)).values
        bear_bottoms = df.get('active_bear_zone_bottom', pd.Series(np.nan, index=df.index)).values
        bull_tops = df.get('active_bull_zone_top', pd.Series(np.nan, index=df.index)).values
        bull_bottoms = df.get('active_bull_zone_bottom', pd.Series(np.nan, index=df.index)).values
        
        highs = df['high'].values
        lows = df['low'].values
        closes = df['close'].values
        
        for i in range(len(df)):
            dt = dates[i]
            
            # --- Bias Tracking Updates ---
            if active_bias_dir == Direction.LONG:
                bias_lowest_since_end = min(bias_lowest_since_end, lows[i]) if bias_lowest_since_end is not None else lows[i]
                if lows[i] < bias_leg_start or highs[i] >= bias_dol:
                    active_bias_dir = None
                    
            if active_bias_dir == Direction.SHORT:
                bias_highest_since_end = max(bias_highest_since_end, highs[i]) if bias_highest_since_end is not None else highs[i]
                if highs[i] > bias_leg_start or lows[i] <= bias_dol:
                    active_bias_dir = None
            
            # --- Tracker Logic ---
            # LONG Context (Sweep of SSL)
            if ssl_wick_sweeps[i] or ssl_body_sweeps[i]:
                if active_sweep_long is None or lows[i] < active_sweep_long.price:
                    active_sweep_long = SweepEvent(
                        price=active_ssl_levels[i],
                        sweep_candle_time=dt,
                        sweep_type="SSL",
                        sweep_method="body" if ssl_body_sweeps[i] else "wick",
                        liquidity_type="SSL"
                    )
                    max_high_since_sweep = highs[i]
            
            # SHORT Context (Sweep of BSL)
            if bsl_wick_sweeps[i] or bsl_body_sweeps[i]:
                if active_sweep_short is None or highs[i] > active_sweep_short.price:
                    active_sweep_short = SweepEvent(
                        price=active_bsl_levels[i],
                        sweep_candle_time=dt,
                        sweep_type="BSL",
                        sweep_method="body" if bsl_body_sweeps[i] else "wick",
                        liquidity_type="BSL"
                    )
                    min_low_since_sweep = lows[i]
                
            # Expiry logic
            if active_sweep_long and lows[i] < active_sweep_long.price:
                # new low beyond the sweep
                pass 
                
            if active_sweep_long:
                if max_high_since_sweep is not None:
                    max_high_since_sweep = max(max_high_since_sweep, highs[i])
                    
            if active_sweep_short:
                if min_low_since_sweep is not None:
                    min_low_since_sweep = min(min_low_since_sweep, lows[i])
                
            # --- Trigger Logic (Reversal & Continuation Models) ---
            # If IFVG Bull Trigger (Bearish gap inverted up)
            if ifvg_bull_triggers[i]:
                zone_top = bear_tops[i-1] if i > 0 else np.nan
                zone_bottom = bear_bottoms[i-1] if i > 0 else np.nan
                
                # Check Reversal
                if active_sweep_long:
                    fvg = FVGZone(top=zone_top, bottom=zone_bottom, is_series=False, component_count=1, formed_at=dt)
                    dol = active_bsl_levels[i]
                    entry = closes[i]
                    stop = active_ssl_levels[i]
                    
                    nearest_internal = max_high_since_sweep if max_high_since_sweep else highs[i]
                    mechanically_valid = highs[i] < nearest_internal
                    dol_intact = dol > closes[i]
                    grade = SignalGrade.MECHANICAL if mechanically_valid and dol_intact else SignalGrade.ADVANCED
                    
                    if pd.notna(dol) and dol_intact:
                        setup = TradeSetup(
                            setup_id=f"REV-LONG-{i}",
                            created_at=dt,
                            symbol="NQ",
                            timeframe="1Min",
                            direction=Direction.LONG,
                            model_type=ModelType.REVERSAL,
                            grade=grade,
                            entry_price=entry,
                            stop_type=StopType.FAIL_STOP,
                            stop_price=stop,
                            fail_stop_level=zone_bottom,
                            target_price=dol,
                            break_even_trigger=nearest_internal,
                            invalidation_price=active_sweep_long.price,
                            expiry_time=None,
                            sweep_event=active_sweep_long,
                            ifvg_zone=fvg,
                            internal_level=nearest_internal,
                            dol_price=dol,
                            dol_type="BSL",
                            dol_priority=1,
                            htf_bias=None,
                            htf_timeframe="1H",
                            risk_reward=(dol - entry) / (entry - stop) if entry != stop else 0,
                            momentum_score=1.0,
                            displacement_leg_start=active_sweep_long.price,
                            displacement_leg_end=entry
                        )
                        registry.add(setup)
                        
                        # Lock in bias
                        active_bias_dir = Direction.LONG
                        bias_leg_start = active_sweep_long.price
                        bias_leg_end = entry
                        bias_dol = dol
                        bias_lowest_since_end = lows[i]
                    active_sweep_long = None
                    
                # Check Continuation
                elif active_bias_dir == Direction.LONG:
                    midpoint = (bias_leg_start + bias_leg_end) / 2
                    if bias_lowest_since_end <= midpoint and pd.notna(bias_dol) and bias_dol > closes[i]:
                        fvg = FVGZone(top=zone_top, bottom=zone_bottom, is_series=False, component_count=1, formed_at=dt)
                        stop = zone_bottom
                        entry = closes[i]
                        
                        setup = TradeSetup(
                            setup_id=f"CONT-LONG-{i}",
                            created_at=dt,
                            symbol="NQ",
                            timeframe="1Min",
                            direction=Direction.LONG,
                            model_type=ModelType.CONTINUATION,
                            grade=SignalGrade.MECHANICAL,
                            entry_price=entry,
                            stop_type=StopType.NARROW_STOP,
                            stop_price=stop,
                            fail_stop_level=zone_bottom,
                            target_price=bias_dol,
                            break_even_trigger=highs[i],
                            invalidation_price=bias_leg_start,
                            expiry_time=None,
                            sweep_event=SweepEvent(price=bias_leg_start, sweep_candle_time=dt, sweep_type="N/A", sweep_method="N/A", liquidity_type="N/A"),
                            ifvg_zone=fvg,
                            internal_level=highs[i],
                            dol_price=bias_dol,
                            dol_type="BSL",
                            dol_priority=1,
                            htf_bias=None,
                            htf_timeframe="1H",
                            risk_reward=(bias_dol - entry) / (entry - stop) if entry != stop else 0,
                            momentum_score=1.0,
                            displacement_leg_start=bias_leg_start,
                            displacement_leg_end=bias_leg_end,
                            retracement_pct=(bias_leg_end - bias_lowest_since_end)/(bias_leg_end - bias_leg_start) if (bias_leg_end - bias_leg_start) != 0 else 0
                        )
                        registry.add(setup)

            # If IFVG Bear Trigger (Bullish gap inverted down)
            if ifvg_bear_triggers[i]:
                zone_top = bull_tops[i-1] if i > 0 else np.nan
                zone_bottom = bull_bottoms[i-1] if i > 0 else np.nan
                
                # Check Reversal
                if active_sweep_short:
                    fvg = FVGZone(top=zone_top, bottom=zone_bottom, is_series=False, component_count=1, formed_at=dt)
                    dol = active_ssl_levels[i]
                    entry = closes[i]
                    stop = active_bsl_levels[i]
                    
                    nearest_internal = min_low_since_sweep if min_low_since_sweep else lows[i]
                    mechanically_valid = lows[i] > nearest_internal
                    dol_intact = dol < closes[i]
                    grade = SignalGrade.MECHANICAL if mechanically_valid and dol_intact else SignalGrade.ADVANCED
                    
                    if pd.notna(dol) and dol_intact:
                        setup = TradeSetup(
                            setup_id=f"REV-SHORT-{i}",
                            created_at=dt,
                            symbol="NQ",
                            timeframe="1Min",
                            direction=Direction.SHORT,
                            model_type=ModelType.REVERSAL,
                            grade=grade,
                            entry_price=entry,
                            stop_type=StopType.FAIL_STOP,
                            stop_price=stop,
                            fail_stop_level=zone_top,
                            target_price=dol,
                            break_even_trigger=nearest_internal,
                            invalidation_price=active_sweep_short.price,
                            expiry_time=None,
                            sweep_event=active_sweep_short,
                            ifvg_zone=fvg,
                            internal_level=nearest_internal,
                            dol_price=dol,
                            dol_type="SSL",
                            dol_priority=1,
                            htf_bias=None,
                            htf_timeframe="1H",
                            risk_reward=(entry - dol) / (stop - entry) if entry != stop else 0,
                            momentum_score=1.0,
                            displacement_leg_start=active_sweep_short.price,
                            displacement_leg_end=entry
                        )
                        registry.add(setup)
                        
                        # Lock in bias
                        active_bias_dir = Direction.SHORT
                        bias_leg_start = active_sweep_short.price
                        bias_leg_end = entry
                        bias_dol = dol
                        bias_highest_since_end = highs[i]
                    active_sweep_short = None
                    
                # Check Continuation
                elif active_bias_dir == Direction.SHORT:
                    midpoint = (bias_leg_start + bias_leg_end) / 2
                    if bias_highest_since_end >= midpoint and pd.notna(bias_dol) and bias_dol < closes[i]:
                        fvg = FVGZone(top=zone_top, bottom=zone_bottom, is_series=False, component_count=1, formed_at=dt)
                        stop = zone_top
                        entry = closes[i]
                        
                        setup = TradeSetup(
                            setup_id=f"CONT-SHORT-{i}",
                            created_at=dt,
                            symbol="NQ",
                            timeframe="1Min",
                            direction=Direction.SHORT,
                            model_type=ModelType.CONTINUATION,
                            grade=SignalGrade.MECHANICAL,
                            entry_price=entry,
                            stop_type=StopType.NARROW_STOP,
                            stop_price=stop,
                            fail_stop_level=zone_top,
                            target_price=bias_dol,
                            break_even_trigger=lows[i],
                            invalidation_price=bias_leg_start,
                            expiry_time=None,
                            sweep_event=SweepEvent(price=bias_leg_start, sweep_candle_time=dt, sweep_type="N/A", sweep_method="N/A", liquidity_type="N/A"),
                            ifvg_zone=fvg,
                            internal_level=lows[i],
                            dol_price=bias_dol,
                            dol_type="SSL",
                            dol_priority=1,
                            htf_bias=None,
                            htf_timeframe="1H",
                            risk_reward=(entry - bias_dol) / (stop - entry) if entry != stop else 0,
                            momentum_score=1.0,
                            displacement_leg_start=bias_leg_start,
                            displacement_leg_end=bias_leg_end,
                            retracement_pct=(bias_highest_since_end - bias_leg_end)/(bias_leg_start - bias_leg_end) if (bias_leg_start - bias_leg_end) != 0 else 0
                        )
                        registry.add(setup)

        return registry
