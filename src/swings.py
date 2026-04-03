from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass
from src.core import Candle, THRESHOLDS

@dataclass
class SwingHigh:
    price: float
    bar_index: int
    confirmed_at_index: int
    candle_time: datetime

@dataclass
class SwingLow:
    price: float
    bar_index: int
    confirmed_at_index: int
    candle_time: datetime

def detect_swing_high(candles: List[Candle], index: int, lookback: int = THRESHOLDS.swing_lookback, min_size: float = THRESHOLDS.min_swing_size_points) -> Optional[SwingHigh]:
    if index < lookback or index > len(candles) - lookback - 1:
        return None
    candidate_high = candles[index].high
    left_highs = [candles[index - j].high for j in range(1, lookback + 1)]
    if not all(candidate_high > h for h in left_highs):
        return None
    right_highs = [candles[index + j].high for j in range(1, lookback + 1)]
    if not all(candidate_high > h for h in right_highs):
        return None
    max_surrounding = max(max(left_highs), max(right_highs))
    if candidate_high - max_surrounding < min_size:
        return None
    return SwingHigh(price=candidate_high, bar_index=index, confirmed_at_index=index + lookback, candle_time=candles[index].timestamp)

def detect_swing_low(candles: List[Candle], index: int, lookback: int = THRESHOLDS.swing_lookback, min_size: float = THRESHOLDS.min_swing_size_points) -> Optional[SwingLow]:
    if index < lookback or index > len(candles) - lookback - 1:
        return None
    candidate_low = candles[index].low
    left_lows = [candles[index - j].low for j in range(1, lookback + 1)]
    if not all(candidate_low < l for l in left_lows):
        return None
    right_lows = [candles[index + j].low for j in range(1, lookback + 1)]
    if not all(candidate_low < l for l in right_lows):
        return None
    min_surrounding = min(min(left_lows), min(right_lows))
    if min_surrounding - candidate_low < min_size:
        return None
    return SwingLow(price=candidate_low, bar_index=index, confirmed_at_index=index + lookback, candle_time=candles[index].timestamp)

class SwingRegistry:
    def __init__(self, lookback: int = THRESHOLDS.swing_lookback, prune_enabled: bool = True):
        self.lookback = lookback
        self.prune_enabled = prune_enabled
        self.confirmed_highs: List[SwingHigh] = []
        self.confirmed_lows:  List[SwingLow]  = []
        self.candle_buffer:   List[Candle]    = []
    
    def update(self, new_candle: Candle) -> None:
        self.candle_buffer.append(new_candle)
        current_index = len(self.candle_buffer) - 1
        check_index = current_index - self.lookback
        if check_index < self.lookback:
            return
        
        sh = detect_swing_high(self.candle_buffer, check_index, self.lookback)
        if sh:
            self.confirmed_highs.append(sh)
        
        sl = detect_swing_low(self.candle_buffer, check_index, self.lookback)
        if sl:
            self.confirmed_lows.append(sl)
            
        # Prune old swings (keep last 200 bars worth) every 1000 bars to save CPU
        if self.prune_enabled and current_index % 1000 == 0:
            self.confirmed_highs = [h for h in self.confirmed_highs if current_index - h.bar_index <= 200]
            self.confirmed_lows  = [l for l in self.confirmed_lows if current_index - l.bar_index <= 200]
        
    def get_nearest_high_above(self, price: float) -> Optional[SwingHigh]:
        candidates = [h for h in self.confirmed_highs if h.price > price]
        return min(candidates, key=lambda h: h.price) if candidates else None
    
    def get_nearest_low_below(self, price: float) -> Optional[SwingLow]:
        candidates = [l for l in self.confirmed_lows if l.price < price]
        return max(candidates, key=lambda l: l.price) if candidates else None

    def get_recent_highs(self, n: int = 10) -> List[SwingHigh]:
        return sorted(self.confirmed_highs, key=lambda h: h.bar_index, reverse=True)[:n]
    
    def get_recent_lows(self, n: int = 10) -> List[SwingLow]:
        return sorted(self.confirmed_lows, key=lambda l: l.bar_index, reverse=True)[:n]
