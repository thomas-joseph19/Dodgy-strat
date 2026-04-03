from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional, List

class Direction(Enum):
    LONG = "long"
    SHORT = "short"

class ModelType(Enum):
    REVERSAL = "reversal"
    CONTINUATION = "continuation"

class StopType(Enum):
    FAIL_STOP = "fail_stop"
    SWING_STOP = "swing_stop"
    NARROW_STOP = "narrow_stop"

class SignalGrade(Enum):
    MECHANICAL = "mechanical"
    ADVANCED = "advanced"
    DISCRETIONARY = "discretionary"

@dataclass
class FVGZone:
    top: float
    bottom: float
    is_series: bool
    component_count: int
    formed_at: datetime

@dataclass
class SweepEvent:
    price: float
    sweep_candle_time: datetime
    sweep_type: str
    sweep_method: str
    liquidity_type: str

@dataclass
class TradeSetup:
    setup_id: str
    created_at: datetime
    symbol: str
    timeframe: str
    
    direction: Direction
    model_type: ModelType
    grade: SignalGrade
    
    entry_price: float
    
    stop_type: StopType
    stop_price: float
    fail_stop_level: float
    
    target_price: float
    break_even_trigger: float
    
    invalidation_price: float
    expiry_time: Optional[datetime]
    
    sweep_event: SweepEvent
    ifvg_zone: FVGZone
    internal_level: float
    
    dol_price: float
    dol_type: str
    dol_priority: int
    
    htf_bias: Optional[Direction]
    htf_timeframe: str
    
    risk_reward: float
    momentum_score: float
    
    displacement_leg_start: Optional[float] = None
    displacement_leg_end: Optional[float] = None
    retracement_pct: Optional[float] = None
    
    is_active: bool = False
    is_expired: bool = False
    break_even_reached: bool = False

class SetupRegistry:
    def __init__(self):
        self.pending: List[TradeSetup] = []
        self.active: List[TradeSetup] = []
        self.closed: List[TradeSetup] = []
        
    def add(self, setup: TradeSetup):
        self.pending.append(setup)
        
    def expire_stale(self, current_time: datetime):
        valid = []
        for s in self.pending:
            if s.expiry_time and current_time >= s.expiry_time:
                s.is_expired = True
                self.closed.append(s)
            else:
                valid.append(s)
        self.pending = valid
        
    def get_active_for_symbol(self, symbol: str) -> List[TradeSetup]:
        return [s for s in self.active if s.symbol == symbol]
        
    def has_active_in_direction(self, symbol: str, direction: Direction) -> bool:
        for s in self.active:
            if s.symbol == symbol and s.direction == direction:
                return True
        return False
