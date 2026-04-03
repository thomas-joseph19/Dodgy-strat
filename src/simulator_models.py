from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import pandas as pd
import numpy as np

from src.models import TradeSetup, Direction

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

@dataclass
class TradeState:
    entry_filled: bool = False
    break_even_active: bool = False
    current_stop: float = 0.0
    fail_stop_level: float = 0.0
    entry_candle: Optional[datetime] = None

@dataclass
class TradeResult:
    setup: TradeSetup
    status: str
    exit_time: Optional[datetime] = None
    raw_entry_price: float = 0.0
    raw_exit_price: float = 0.0
    exit_type: Optional[str] = None
    net_pnl: float = 0.0
    contracts: int = 0
    
    @classmethod
    def invalidated(cls, setup: TradeSetup, time: datetime):
        return cls(setup=setup, status="invalidated", exit_time=time)
        
    @classmethod
    def expired(cls, setup: TradeSetup, time: datetime):
        return cls(setup=setup, status="expired", exit_time=time)
        
    @classmethod
    def stopped_out(cls, setup: TradeSetup, candle_ser, exit_price: float, exit_type: str):
        return cls(
            setup=setup, 
            status="closed", 
            exit_time=candle_ser.name if hasattr(candle_ser, 'name') else None,
            raw_entry_price=setup.entry_price, 
            raw_exit_price=exit_price, 
            exit_type=exit_type
        )
        
    @classmethod
    def target_hit(cls, setup: TradeSetup, candle_ser, exit_price: float):
        return cls(
            setup=setup, 
            status="closed", 
            exit_time=candle_ser.name if hasattr(candle_ser, 'name') else None,
            raw_entry_price=setup.entry_price, 
            raw_exit_price=exit_price, 
            exit_type="TARGET"
        )
        
    @classmethod
    def open_at_end(cls, setup: TradeSetup):
        return cls(setup=setup, status="open_at_end", raw_entry_price=setup.entry_price)

def calculate_position_size(setup: TradeSetup, account_equity: float, config: SimulationConfig) -> int:
    dollar_risk = account_equity * config.risk_per_trade_pct
    stop_distance = abs(setup.entry_price - setup.stop_price)
    
    if stop_distance == 0:
        return config.min_contracts
        
    risk_per_contract = stop_distance * config.point_value
    total_cost_per_contract = risk_per_contract + config.commission_per_rt
    
    raw_contracts = dollar_risk / total_cost_per_contract
    contracts = int(raw_contracts)
    
    return max(config.min_contracts, min(config.max_contracts, contracts))

def calculate_trade_pnl(result: TradeResult, contracts: int, config: SimulationConfig) -> float:
    slippage_per_side = config.slippage_ticks * config.tick_size
    
    if result.setup.direction == Direction.LONG:
        actual_entry = result.raw_entry_price + slippage_per_side
        actual_exit = result.raw_exit_price - slippage_per_side
        points_gained = actual_exit - actual_entry
    else:
        actual_entry = result.raw_entry_price - slippage_per_side
        actual_exit = result.raw_exit_price + slippage_per_side
        points_gained = actual_entry - actual_exit
        
    gross_pnl = points_gained * config.point_value * contracts
    commission = config.commission_per_rt * contracts
    
    return gross_pnl - commission

class AccountState:
    def __init__(self, starting_capital: float = 100_000.00):
        self.equity = starting_capital
        self.peak_equity = starting_capital
        self.trade_history: List[TradeResult] = []
        
    def apply_result(self, result: TradeResult, pnl: float):
        result.net_pnl = pnl
        self.trade_history.append(result)
        self.equity += pnl
        self.peak_equity = max(self.peak_equity, self.equity)
        
    @property
    def current_drawdown_pct(self):
        return (self.peak_equity - self.equity) / self.peak_equity if self.peak_equity else 0
