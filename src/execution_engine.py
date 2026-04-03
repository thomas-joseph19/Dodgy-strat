import pandas as pd
from typing import Optional
from datetime import time
from src.models import TradeSetup, Direction, StopType, SetupRegistry
from src.simulator_models import (
    TradeState, TradeResult, SimulationConfig, 
    AccountState, calculate_trade_pnl, calculate_position_size
)

class ExecutionEngine:
    def evaluate_setup(self, setup: TradeSetup, ohlc_df: pd.DataFrame) -> TradeResult:
        # Slice from entry candle onward
        forward_df = ohlc_df[ohlc_df.index >= setup.created_at].copy()
        
        state = TradeState(
            entry_filled=False,
            break_even_active=False,
            current_stop=setup.stop_price,
            fail_stop_level=setup.fail_stop_level
        )
        
        for idx, candle in forward_df.iterrows():
            
            # ── Check invalidation before entry ──────────────────
            if not state.entry_filled:
                if setup.direction == Direction.LONG:
                    if candle.low <= setup.invalidation_price:
                        return TradeResult.invalidated(setup, idx)
                elif setup.direction == Direction.SHORT:
                    if candle.high >= setup.invalidation_price:
                        return TradeResult.invalidated(setup, idx)
                        
                if setup.expiry_time and idx >= setup.expiry_time:
                    return TradeResult.expired(setup, idx)
                
                # Entry assumed at signal candle close (already closed)
                # so mark filled on first iteration
                state.entry_filled = True
                state.entry_candle = idx
                pass # Still evaluate same candle for exits just in case it gapped/moved
            
            # ── Break-even trigger ───────────────────────────────
            if not state.break_even_active:
                if setup.direction == Direction.LONG:
                    if pd.notna(setup.break_even_trigger) and candle.high >= setup.break_even_trigger:
                        state.current_stop = setup.entry_price
                        state.break_even_active = True
                else:
                    if pd.notna(setup.break_even_trigger) and candle.low <= setup.break_even_trigger:
                        state.current_stop = setup.entry_price
                        state.break_even_active = True
            
            # ── Exit checks (order matters) ─────
            exit_result = self.check_exits(candle, setup, state)
            if exit_result:
                return exit_result
        
        return TradeResult.open_at_end(setup)
        
    def check_exits(self, candle: pd.Series, setup: TradeSetup, state: TradeState) -> Optional[TradeResult]:
        if setup.direction == Direction.LONG:
            # 1. Catastrophic hard stop
            if candle.low <= state.current_stop:
                return TradeResult.stopped_out(
                    setup, candle, 
                    exit_price=state.current_stop,
                    exit_type="HARD_STOP"
                )
            
            # 2. Fail stop
            if setup.stop_type == StopType.FAIL_STOP:
                if pd.notna(setup.fail_stop_level) and candle.close < setup.fail_stop_level:
                    return TradeResult.stopped_out(
                        setup, candle,
                        exit_price=candle.close,
                        exit_type="FAIL_STOP"
                    )
            
            # 3. Target hit
            if pd.notna(setup.target_price) and candle.high >= setup.target_price:
                return TradeResult.target_hit(
                    setup, candle,
                    exit_price=setup.target_price
                )
                
        elif setup.direction == Direction.SHORT:
            # 1. Catastrophic hard stop
            if candle.high >= state.current_stop:
                return TradeResult.stopped_out(
                    setup, candle, 
                    exit_price=state.current_stop,
                    exit_type="HARD_STOP"
                )
            
            # 2. Fail stop
            if setup.stop_type == StopType.FAIL_STOP:
                if pd.notna(setup.fail_stop_level) and candle.close > setup.fail_stop_level:
                    return TradeResult.stopped_out(
                        setup, candle,
                        exit_price=candle.close,
                        exit_type="FAIL_STOP"
                    )
            
            # 3. Target hit
            if pd.notna(setup.target_price) and candle.low <= setup.target_price:
                return TradeResult.target_hit(
                    setup, candle,
                    exit_price=setup.target_price
                )
        return None

    def run_backtest(self, registry: SetupRegistry, df: pd.DataFrame, config: SimulationConfig) -> AccountState:
        account = AccountState(config.starting_capital)
        
        # Sort pending and closed setups chronologically by creation time
        setups = sorted(registry.pending + registry.closed, key=lambda s: s.created_at)
        
        rth_start = time(9, 30)
        rth_end = time(16, 0)
        
        for setup in setups:
            setup_time = setup.created_at.time()
            if not (rth_start <= setup_time <= rth_end):
                continue
                
            result = self.evaluate_setup(setup, df)
            
            if result.status == "closed":
                contracts = calculate_position_size(setup, account.equity, config)
                result.contracts = contracts
                
                net_pnl = calculate_trade_pnl(result, contracts, config)
                account.apply_result(result, net_pnl)
                
        return account
