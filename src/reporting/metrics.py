from dataclasses import dataclass
from typing import List, Dict
import pandas as pd
import numpy as np

from src.models import TradeSetup, SetupRegistry, ModelType, SignalGrade
from src.simulator_models import TradeResult, AccountState, SimulationConfig

@dataclass 
class BacktestMetrics:
    # ── Volume ───────────────────────────────────────────────────
    total_setups_generated: int
    total_setups_taken: int
    total_setups_invalidated: int
    total_setups_expired: int
    
    # ── Win/Loss ─────────────────────────────────────────────────
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # ── P&L ──────────────────────────────────────────────────────
    gross_profit: float
    gross_loss: float
    net_profit: float
    profit_factor: float
    
    avg_win: float
    avg_loss: float
    avg_rr_realized: float
    
    largest_win: float
    largest_loss: float
    
    # ── Drawdown ─────────────────────────────────────────────────
    max_drawdown_dollars: float
    max_drawdown_pct: float
    max_drawdown_duration: int
    
    # ── Risk-Adjusted ────────────────────────────────────────────
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    
    # ── Exit Type Breakdown ──────────────────────────────────────
    target_hit_count: int
    hard_stop_count: int
    fail_stop_count: int
    break_even_stop_count: int
    
    # ── By Model Type ────────────────────────────────────────────
    reversal_win_rate: float
    continuation_win_rate: float
    
    # ── By Signal Grade ──────────────────────────────────────────
    mechanical_win_rate: float
    advanced_win_rate: float

def calculate_sharpe(daily_returns: pd.Series, rfr_annual: float) -> float:
    if len(daily_returns) < 2:
        return 0.0
    rfr_daily = rfr_annual / 252
    excess_returns = daily_returns - rfr_daily
    
    if excess_returns.std() == 0:
        return 0.0
    
    sharpe_daily = excess_returns.mean() / excess_returns.std()
    return sharpe_daily * np.sqrt(252)

def calculate_sortino(daily_returns: pd.Series, rfr_annual: float) -> float:
    if len(daily_returns) < 2:
        return 0.0
    rfr_daily = rfr_annual / 252
    excess_returns = daily_returns - rfr_daily
    downside = excess_returns[excess_returns < 0]
    
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    
    sortino_daily = excess_returns.mean() / downside.std()
    return sortino_daily * np.sqrt(252)

def calculate_metrics(registry: SetupRegistry, account: AccountState, start_date: str = None, end_date: str = None, rfr_annual: float = 0.045) -> BacktestMetrics:
    closed_trades = [r for r in account.trade_history if r.status == "closed"]
    invalidated = [s for s in registry.closed if next((r for r in account.trade_history if r.setup == s and r.status == "invalidated"), None)]
    expired = [s for s in registry.closed if next((r for r in account.trade_history if r.setup == s and r.status == "expired"), None)]
    
    total_generated = len(registry.pending) + len(registry.closed)
    
    # Group results
    winners = [r for r in closed_trades if r.net_pnl > 0]
    losers = [r for r in closed_trades if r.net_pnl <= 0]
    
    gross_profit = sum([r.net_pnl for r in winners])
    gross_loss = abs(sum([r.net_pnl for r in losers]))
    
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    # Win rates
    win_rate = len(winners) / len(closed_trades) if closed_trades else 0.0
    
    def get_win_rate(condition) -> float:
        subset = [r for r in closed_trades if condition(r.setup)]
        won = [r for r in subset if r.net_pnl > 0]
        return len(won) / len(subset) if subset else 0.0

    rev_wr = get_win_rate(lambda s: s.model_type == ModelType.REVERSAL)
    con_wr = get_win_rate(lambda s: s.model_type == ModelType.CONTINUATION)
    mech_wr = get_win_rate(lambda s: s.grade == SignalGrade.MECHANICAL)
    adv_wr = get_win_rate(lambda s: s.grade == SignalGrade.ADVANCED)
    
    # R Realized (Approximate based on raw risk/reward vs exit diff. Realized RR is net_pnl / risk_amount)
    rr_realized_sum = []
    for r in closed_trades:
        risk_per_contract = abs(r.setup.entry_price - r.setup.stop_price) * 20.0
        tot_risk = risk_per_contract * r.contracts
        if tot_risk > 0:
            rr_realized_sum.append(r.net_pnl / tot_risk)
    avg_rr = np.mean(rr_realized_sum) if rr_realized_sum else 0.0
    
    # Drawdown calculation
    # We want DD from equity curve
    equity_curve = []
    current_eq = account.starting_capital if hasattr(account, 'starting_capital') else 100_000.00
    peak = current_eq
    max_dd_dollars = 0.0
    max_dd_pct = 0.0
    
    pnl_by_date = {}
    
    for r in closed_trades:
        current_eq += r.net_pnl
        if current_eq > peak:
            peak = current_eq
        
        dd_dollars = peak - current_eq
        dd_pct = dd_dollars / peak if peak > 0 else 0.0
        
        if dd_dollars > max_dd_dollars:
            max_dd_dollars = dd_dollars
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct
            
        exit_date = r.exit_time.date() if r.exit_time else None
        if exit_date:
            pnl_by_date[exit_date] = pnl_by_date.get(exit_date, 0.0) + r.net_pnl
            
    # Calculate Sharpe/Sortino using Daily Returns
    unique_dates = sorted(list(pnl_by_date.keys()))
    daily_returns_list = []
    start_eq = account.starting_capital if hasattr(account, 'starting_capital') else 100_000.00
    running_eq = start_eq
    
    for d in unique_dates:
        daily_pnl = pnl_by_date[d]
        d_ret = daily_pnl / running_eq
        daily_returns_list.append(d_ret)
        running_eq += daily_pnl
        
    daily_returns_series = pd.Series(daily_returns_list)
    sharpe = calculate_sharpe(daily_returns_series, rfr_annual)
    sortino = calculate_sortino(daily_returns_series, rfr_annual)
    
    calmar = 0.0
    if len(unique_dates) > 0 and max_dd_pct > 0:
        days = (unique_dates[-1] - unique_dates[0]).days
        years = days / 365.25 if days > 0 else 0
        total_ret = (running_eq - start_eq) / start_eq
        annualized_ret = ((1 + total_ret) ** (1 / years) - 1) if years > 0 else total_ret
        calmar = annualized_ret / max_dd_pct

    return BacktestMetrics(
        total_setups_generated=total_generated,
        total_setups_taken=len(closed_trades),
        total_setups_invalidated=len(invalidated),
        total_setups_expired=len(expired),
        total_trades=len(closed_trades),
        winning_trades=len(winners),
        losing_trades=len(losers),
        win_rate=win_rate,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        net_profit=gross_profit - gross_loss,
        profit_factor=profit_factor,
        avg_win=np.mean([r.net_pnl for r in winners]) if winners else 0.0,
        avg_loss=np.mean([r.net_pnl for r in losers]) if losers else 0.0,
        avg_rr_realized=float(avg_rr),
        largest_win=max([r.net_pnl for r in winners]) if winners else 0.0,
        largest_loss=min([r.net_pnl for r in losers]) if losers else 0.0,
        max_drawdown_dollars=max_dd_dollars,
        max_drawdown_pct=max_dd_pct,
        max_drawdown_duration=0, # Need daily high-water mark matching for duration
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        target_hit_count=len([r for r in closed_trades if r.exit_type == "TARGET"]),
        hard_stop_count=len([r for r in closed_trades if r.exit_type == "HARD_STOP"]),
        fail_stop_count=len([r for r in closed_trades if r.exit_type == "FAIL_STOP"]),
        break_even_stop_count=len([r for r in closed_trades if r.exit_type == "HARD_STOP" and r.net_pnl == 0]), # Approximation
        reversal_win_rate=rev_wr,
        continuation_win_rate=con_wr,
        mechanical_win_rate=mech_wr,
        advanced_win_rate=adv_wr
    )
