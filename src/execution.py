from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from src.core import Candle, THRESHOLDS

from enum import Enum

class Direction(Enum):
    LONG = "long"
    SHORT = "short"

class ModelType(Enum):
    REVERSAL = "reversal"
    CONTINUATION = "continuation"

class StopType(Enum):
    SWING_STOP = "swing_stop"
    NARROW_STOP = "narrow_stop"

class SignalGrade(Enum):
    MECHANICAL = "mechanical"
    ADVANCED = "advanced"
    DISCRETIONARY = "discretionary"

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
    target_price: float
    break_even_trigger: float
    invalidation_price: float
    expiry_time: Optional[datetime]
    internal_level: float
    risk_reward: float
    momentum_score: float
    reasoning: str = ""

@dataclass
class TradeResult:
    setup: TradeSetup
    exit_candle_time: datetime
    exit_price: float
    exit_type: str
    net_pnl: float

    @staticmethod
    def stopped_out(setup, candle, exit_price, exit_type):
        return TradeResult(setup, candle.timestamp, exit_price, exit_type, 0.0)
    
    @staticmethod
    def target_hit(setup, candle, exit_price):
        return TradeResult(setup, candle.timestamp, exit_price, "TARGET_HIT", 0.0)

class TradeState:
    def __init__(self, entry_filled=False, break_even_active=False, current_stop=0.0):
        self.entry_filled = entry_filled
        self.break_even_active = break_even_active
        self.current_stop = current_stop
        self.entry_candle = None

@dataclass
class SimulationConfig:
    starting_capital: float = 100_000.00
    risk_per_trade_pct: float = 0.01
    commission_per_rt: float = 4.00
    slippage_ticks: int = 1
    tick_size: float = 0.25
    point_value: float = 20.00
    min_contracts: int = 1
    max_contracts: int = 10
    save_charts: bool = False
