from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass
from src.core import Candle, THRESHOLDS

@dataclass
class LiquidityLevel:
    price: float
    level_type: str      # "BSL" or "SSL"
    quality: str         # "EQH", "EQL", "REQH", "REQL", "ITH", "ITL", "SWING"
    quality_rank: int    # 1=best, 5=lowest
    formed_at: datetime
    is_intact: bool = True

@dataclass
class SweepEvent:
    swept_level: LiquidityLevel
    sweep_candle: Candle
    sweep_candle_index: int
    direction: str          # "SSL_SWEPT" -> look for long
    sweep_strength: str     # "STRONG" or "MODERATE"
    is_active: bool = True
    bars_since_sweep: int = 0

def detect_sweep(current_candle: Candle, current_index: int, intact_levels: List[LiquidityLevel], thresholds=THRESHOLDS) -> Optional[SweepEvent]:
    for level in intact_levels:
        if not level.is_intact:
            continue
        if level.level_type == "SSL":
            extension = level.price - current_candle.low
            if extension < thresholds.min_sweep_extension_points:
                continue
            body_violation = level.price - current_candle.close
            if body_violation > thresholds.max_sweep_body_violation_points:
                level.is_intact = False
                continue
            strength = "STRONG" if current_candle.close > level.price else "MODERATE"
            return SweepEvent(level, current_candle, current_index, "SSL_SWEPT", strength)
        elif level.level_type == "BSL":
            extension = current_candle.high - level.price
            if extension < thresholds.min_sweep_extension_points:
                continue
            body_violation = current_candle.close - level.price
            if body_violation > thresholds.max_sweep_body_violation_points:
                level.is_intact = False
                continue
            strength = "STRONG" if current_candle.close < level.price else "MODERATE"
            return SweepEvent(level, current_candle, current_index, "BSL_SWEPT", strength)
    return None
