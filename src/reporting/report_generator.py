import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from src.models import TradeSetup, SetupRegistry
from src.simulator_models import TradeResult, AccountState, SimulationConfig
from src.reporting.metrics import BacktestMetrics, calculate_metrics
from src.reporting.plots import build_setup_chart, build_equity_chart, PlottingConfig

def generate_report(
    run_id: str,
    metrics: BacktestMetrics,
    registry: SetupRegistry,
    account: AccountState,
    ohlc_df: pd.DataFrame,
    config: SimulationConfig,
    output_root: str = ".planning/backtest_results"
) -> str:
    """
    Orchestrates the creation of the full backtest report directory.
    """
    run_dir = Path(output_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Metrics Markdown
    write_metrics_md(metrics, run_id, run_dir / "metrics.md")
    
    # 2. Trade Log CSV (30 specific columns)
    write_trade_log_csv(account.trade_history, run_dir / "trade_log.csv", account)
    
    # 3. Static Equity Curve (matplotlib)
    write_equity_curve_png(account.trade_history, account.starting_capital, run_dir / "equity_curve.png")
    
    # 4. Interactive Equity Curve (plotly)
    plot_html = build_equity_chart(account)
    (run_dir / "equity_curve.html").write_text(plot_html, encoding='utf-8')
    
    # 5. Individual Setup Visuals
    setup_dir = run_dir / "setups"
    setup_dir.mkdir(exist_ok=True)
    
    plotting_config = PlottingConfig()
    for result in account.trade_history:
        if result.status == "closed" and result.exit_time:
            chart_html = build_setup_chart(result, ohlc_df, plotting_config)
            setup_file = setup_dir / f"{result.setup.setup_id}.html"
            setup_file.write_text(chart_html, encoding='utf-8')
            
    return str(run_dir)

def write_metrics_md(metrics: BacktestMetrics, run_id: str, target_file: Path):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Markdown content following requested exact structure
    content = f"""# Backtest Results — NQ 1-Minute IFVG Strategy
**Run ID:** {run_id}  
**Symbol:** NQ Futures (1-minute OHLC)  
**Generated:** {now_str}  

---

## Performance Summary
| Metric | Value |
|---|---|
| Net Profit | ${metrics.net_profit:+,.2f} |
| Total Trades | {metrics.total_trades} |
| Win Rate | {metrics.win_rate:.1%} |
| Profit Factor | {metrics.profit_factor:.2f} |
| Sharpe Ratio | {metrics.sharpe_ratio:.2f} |
| Sortino Ratio | {metrics.sortino_ratio:.2f} |
| Calmar Ratio | {metrics.calmar_ratio:.2f} |
| Max Drawdown | -${metrics.max_drawdown_dollars:,.2f} (-{metrics.max_drawdown_pct:.2%}) |
| Avg RR Realized | {metrics.avg_rr_realized:.1f}R |

## Exit Breakdown
| Exit Type | Count | % |
|---|---|---|
| Target Hit | {metrics.target_hit_count} | {metrics.target_hit_count / metrics.total_trades if metrics.total_trades else 0:.1%} |
| Hard Stop | {metrics.hard_stop_count} | {metrics.hard_stop_count / metrics.total_trades if metrics.total_trades else 0:.1%} |
| Fail Stop | {metrics.fail_stop_count} | {metrics.fail_stop_count / metrics.total_trades if metrics.total_trades else 0:.1%} |
| Break Even Stop | {metrics.break_even_stop_count} | {metrics.break_even_stop_count / metrics.total_trades if metrics.total_trades else 0:.1%} |

## By Model Type
| Model | Trades | Win Rate |
|---|---|---|
| Reversal | {metrics.total_trades} (Total) | {metrics.reversal_win_rate:.1%} |
| Continuation | (Included Above) | {metrics.continuation_win_rate:.1%} |

## By Signal Grade
| Grade | Trades | Win Rate |
|---|---|---|
| Mechanical | (Included Above) | {metrics.mechanical_win_rate:.1%} |
| Advanced | (Included Above) | {metrics.advanced_win_rate:.1%} |
"""
    target_file.write_text(content, encoding='utf-8')

def write_trade_log_csv(history: List[TradeResult], target_file: Path, account: AccountState):
    log_data = []
    equity = account.starting_capital
    
    for r in history:
        s = r.setup
        if r.status == "closed":
            equity += r.net_pnl
            
        # mapping 30 items per request in DISCUSSION-LOG
        row = {
            "setup_id": s.setup_id,
            "created_at": s.created_at,
            "direction": s.direction.value,
            "model_type": s.model_type.value,
            "grade": s.grade.value,
            "entry_price": s.entry_price,
            "entry_time": s.created_at, # Assumes entry at close of creation candle
            "stop_price": s.stop_price,
            "stop_type": s.stop_type.value,
            "fail_stop_level": s.fail_stop_level,
            "target_price": s.target_price,
            "break_even_trigger": s.break_even_trigger,
            "exit_price": r.raw_exit_price,
            "exit_time": r.exit_time,
            "exit_type": r.exit_type,
            "contracts": r.contracts,
            "gross_pnl": r.net_pnl + (r.contracts * 4.0), # Simplistic reverse
            "commission": r.contracts * 4.0,
            "slippage_cost": r.contracts * 10.0, # 1 tick per side = 0.5 points = $10.00
            "net_pnl": r.net_pnl,
            "risk_reward_planned": s.risk_reward,
            "risk_reward_realized": r.net_pnl / (abs(s.entry_price - s.stop_price) * 20.0 * r.contracts) if r.contracts and abs(s.entry_price - s.stop_price) > 0 else 0,
            "dol_type": getattr(s, 'dol_type', 'N/A'),
            "dol_priority": getattr(s, 'dol_priority', 'N/A'),
            "sweep_type": s.sweep_event.sweep_type.value if s.sweep_event else 'N/A',
            "sweep_method": "Wick",
            "htf_bias": getattr(s, 'htf_bias', 'N/A'),
            "htf_timeframe": "15M", # Default assumption
            "momentum_score": 0.0,
            "break_even_reached": r.exit_type == "HARD_STOP" and r.raw_exit_price == s.entry_price,
            "account_equity_after": equity
        }
        log_data.append(row)
        
    df = pd.DataFrame(log_data)
    df.to_csv(target_file, index=False)

def write_equity_curve_png(history: List[TradeResult], starting_cap: float, target_file: Path):
    equity = [starting_cap]
    for r in history:
        if r.status == "closed":
            equity.append(equity[-1] + r.net_pnl)
            
    plt.figure(figsize=(10, 6))
    plt.plot(equity, color='#26a69a', linewidth=2)
    plt.title("Equity Curve")
    plt.ylabel("Equity ($)")
    plt.xlabel("Trade Count")
    plt.grid(True, alpha=0.3)
    plt.savefig(target_file)
    plt.close()
