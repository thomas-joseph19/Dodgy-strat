import numpy as np
import pandas as pd
from typing import List
from src.execution import TradeResult

def calculate_sharpe(returns: pd.Series, risk_free_rate=0.0) -> float:
    if len(returns) < 2: return 0.0
    excess_returns = returns - (risk_free_rate / 252) # daily
    if excess_returns.std() == 0: return 0.0
    return np.sqrt(252) * (excess_returns.mean() / excess_returns.std())

def calculate_sortino(returns: pd.Series, risk_free_rate=0.0, target_return=0.0) -> float:
    if len(returns) < 2: return 0.0
    excess_returns = returns - (risk_free_rate / 252)
    downside_returns = excess_returns[excess_returns < target_return]
    if len(downside_returns) < 1: return 0.0
    downside_std = np.sqrt(np.mean(downside_returns**2))
    if downside_std == 0: return 0.0
    return np.sqrt(252) * (excess_returns.mean() / downside_std)

def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    peak = equity_curve.expanding().max()
    drawdown = (equity_curve - peak) / peak
    return drawdown.min()

def get_performance_summary(results: List[TradeResult], initial_capital: float):
    # Convert to daily returns for sharpe/sortino
    df = pd.DataFrame([
        {'date': r.exit_candle_time.date(), 'pnl': r.net_pnl} 
        for r in results
    ])
    if df.empty:
        return {}
        
    daily_pnl = df.groupby('date')['pnl'].sum()
    daily_returns = daily_pnl / initial_capital
    
    equity_curve = daily_pnl.cumsum() + initial_capital
    total_net_pnl = daily_pnl.sum()
    win_rate = len([r for r in results if r.net_pnl > 0]) / len(results)
    
    return {
        "total_pnl": total_net_pnl,
        "win_rate": win_rate,
        "sharpe": calculate_sharpe(daily_returns),
        "sortino": calculate_sortino(daily_returns),
        "max_drawdown": calculate_max_drawdown(equity_curve),
        "equity_curve": equity_curve
    }
