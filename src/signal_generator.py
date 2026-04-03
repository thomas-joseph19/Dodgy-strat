import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional
from src.models import (
    TradeSetup, SetupRegistry, Direction, ModelType, StopType, 
    SignalGrade, SweepEvent, FVGZone
)

class SignalGenerator:
    def __init__(self):
        pass

    def generate_signals(self, df: pd.DataFrame, registry: SetupRegistry):
        df = df.copy()
        
        active_sweep_long: Optional[SweepEvent] = None
        active_sweep_short: Optional[SweepEvent] = None
        
        # Track the highest/lowest points since sweep down/up to current bar
        max_high_since_sweep = None
        min_low_since_sweep = None
        
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
            
            # --- Tracker Logic ---
            # LONG Context (Sweep of SSL)
            if ssl_wick_sweeps[i] or ssl_body_sweeps[i]:
                # If we sweep SSL, we are tracking for a LONG reversal
                # Invalidate if new extreme is lower
                if active_sweep_long is None or lows[i] < active_sweep_long.price:
                    active_sweep_long = SweepEvent(
                        price=active_ssl_levels[i], # The level swept
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
                
            # Expiry logic: New extremes break the structure
            if active_sweep_long and lows[i] < active_sweep_long.price:
                # Need a fresh sweep since it went lower
                # Wait, if it just goes lower, it is STILL sweeping if it's below the level.
                pass 
                
            if active_sweep_long:
                if max_high_since_sweep is not None:
                    max_high_since_sweep = max(max_high_since_sweep, highs[i])
                    
            if active_sweep_short:
                if min_low_since_sweep is not None:
                    min_low_since_sweep = min(min_low_since_sweep, lows[i])
                
            # --- Trigger Logic (Reversal Models) ---
            # If IFVG Bull Trigger (Bearish gap inverted up)
            if ifvg_bull_triggers[i] and active_sweep_long:
                # We need the past zone top/bottom
                zone_top = bear_tops[i-1] if i > 0 else np.nan
                zone_bottom = bear_bottoms[i-1] if i > 0 else np.nan
                
                fvg = FVGZone(top=zone_top, bottom=zone_bottom, is_series=False, component_count=1, formed_at=dt)
                dol = active_bsl_levels[i]
                entry = closes[i]
                stop = active_ssl_levels[i]
                
                # Check nearest internal high since sweep
                nearest_internal = max_high_since_sweep if max_high_since_sweep else highs[i]
                
                # Mechanical validity: inversion candle high < nearest internal
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
                        displacement_leg_start=active_sweep_long.price, # the extreme LOW
                        displacement_leg_end=entry
                    )
                    registry.add(setup)
                # Reset for next setup
                active_sweep_long = None
                
            # If IFVG Bear Trigger (Bullish gap inverted down)
            if ifvg_bear_triggers[i] and active_sweep_short:
                zone_top = bull_tops[i-1] if i > 0 else np.nan
                zone_bottom = bull_bottoms[i-1] if i > 0 else np.nan
                
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
                active_sweep_short = None

        return registry
