from dataclasses import dataclass
from datetime import datetime, time
from typing import List, Optional

@dataclass(frozen=True)
class InstrumentConfig:
    symbol:          str   = "NQ"
    tick_size:       float = 0.25
    point_value:     float = 20.00
    tick_value:      float = 5.00
    rth_open:        time  = time(9, 30)
    rth_close:       time  = time(16, 0)
    slippage_ticks:  int   = 1
    commission_rt:   float = 4.00

NQ = InstrumentConfig()

@dataclass
class StrategyThresholds:
    swing_lookback:        int   = 5
    min_swing_size_points: float = 3.0
    level_equality_tolerance_pct: float = 0.0005
    min_level_separation_bars: int = 10
    min_sweep_extension_points: float = 1.0
    max_sweep_body_violation_points: float = 15.0
    sweep_context_max_bars: int = 50
    min_fvg_size_points: float = 1.5
    min_impulse_body_ratio: float = 0.50
    min_impulse_size_points: float = 2.0
    max_gap_between_series_points: float = 2.0
    min_inversion_body_points: float = 1.0
    min_rr_ratio: float = 1.5
    min_clearance_to_internal_points: float = 2.0
    min_target_distance_points: float = 15.0
    min_internal_high_clearance: float = 2.0
    htf_timeframe: str = "1h"
    htf_swing_lookback: int = 5

THRESHOLDS = StrategyThresholds()

@dataclass
class Candle:
    timestamp: datetime
    open:  float
    high:  float
    low:   float
    close: float
    
    @property
    def body_top(self) -> float:
        return max(self.open, self.close)
    
    @property
    def body_bottom(self) -> float:
        return min(self.open, self.close)
    
    @property
    def body_size(self) -> float:
        return abs(self.close - self.open)
    
    @property
    def total_range(self) -> float:
        return self.high - self.low
    
    @property
    def body_ratio(self) -> float:
        if self.total_range == 0:
            return 0
        return self.body_size / self.total_range
    
    @property
    def is_bullish(self) -> bool:
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        return self.close < self.open
    
    @property
    def upper_wick(self) -> float:
        return self.high - self.body_top
    
    @property
    def lower_wick(self) -> float:
        return self.body_bottom - self.low
