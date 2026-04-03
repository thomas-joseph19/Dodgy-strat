from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from src.core import Candle, THRESHOLDS

@dataclass
class FairValueGap:
    fvg_top:    float
    fvg_bottom: float
    direction:  str        # "BULLISH" or "BEARISH"
    formed_at:  datetime
    c1_index:   int
    c2_index:   int
    c3_index:   int
    is_intact:  bool = True
    
    @property
    def size(self) -> float:
        return self.fvg_top - self.fvg_bottom
    
    @property
    def midpoint(self) -> float:
        return (self.fvg_top + self.fvg_bottom) / 2

def detect_fvg(candles: List[Candle], c3_index: int, thresholds=THRESHOLDS) -> Optional[FairValueGap]:
    if c3_index < 2:
        return None
    c1 = candles[c3_index - 2]
    c2 = candles[c3_index - 1]
    c3 = candles[c3_index]
    
    if (c3.low > c1.high and 
        c3.low - c1.high >= thresholds.min_fvg_size_points and 
        c2.is_bullish and 
        c2.body_ratio >= thresholds.min_impulse_body_ratio and 
        c2.body_size >= thresholds.min_impulse_size_points):
        return FairValueGap(fvg_top=c3.low, fvg_bottom=c1.high, direction="BULLISH", formed_at=c3.timestamp, c1_index=c3_index-2, c2_index=c3_index-1, c3_index=c3_index)
        
    if (c3.high < c1.low and 
        c1.low - c3.high >= thresholds.min_fvg_size_points and 
        c2.is_bearish and 
        c2.body_ratio >= thresholds.min_impulse_body_ratio and 
        c2.body_size >= thresholds.min_impulse_size_points):
        return FairValueGap(fvg_top=c1.low, fvg_bottom=c3.high, direction="BEARISH", formed_at=c3.timestamp, c1_index=c3_index-2, c2_index=c3_index-1, c3_index=c3_index)
    
    return None

def combine_fvg_group(group: List[FairValueGap]) -> FairValueGap:
    return FairValueGap(
        fvg_top    = max(f.fvg_top for f in group),
        fvg_bottom = min(f.fvg_bottom for f in group),
        direction  = group[0].direction,
        formed_at  = group[-1].formed_at,
        c1_index   = group[0].c1_index,
        c2_index   = group[0].c2_index,
        c3_index   = group[-1].c3_index,
        is_intact  = True
    )

def merge_fvg_series(fvgs: List[FairValueGap], direction: str, max_gap=THRESHOLDS.max_gap_between_series_points) -> List[FairValueGap]:
    same_dir = [f for f in fvgs if f.direction == direction and f.is_intact]
    same_dir.sort(key=lambda f: f.c3_index)
    if len(same_dir) <= 1:
        return same_dir
    merged = []
    current_group = [same_dir[0]]
    for i in range(1, len(same_dir)):
        prev = current_group[-1]
        curr = same_dir[i]
        gap_between = prev.fvg_bottom - curr.fvg_top if direction == "BEARISH" else curr.fvg_bottom - prev.fvg_top
        if 0 <= gap_between <= max_gap:
            current_group.append(curr)
        else:
            merged.append(combine_fvg_group(current_group))
            current_group = [curr]
    merged.append(combine_fvg_group(current_group))
    return merged
