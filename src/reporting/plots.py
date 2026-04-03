import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from src.models import TradeSetup, Direction, StopType
from src.simulator_models import TradeResult

class PlottingConfig:
    bars_before_sweep: int = 50
    bars_after_exit: int = 20
    
    # Colors requested in DISCUSSION-LOG.md
    bullish_candle: str = "#26a69a"
    bearish_candle: str = "#ef5350"
    ifvg_zone_long: str = "rgba(38, 166, 154, 0.15)"
    ifvg_zone_short: str = "rgba(239, 83, 80, 0.15)"
    entry: str = "#2196F3"    # Blue
    stop: str = "#F44336"     # Red
    fail_stop: str = "#FF9800" # Orange
    target: str = "#4CAF50"    # Green
    break_even: str = "#9C27B0" # Purple
    sweep_marker: str = "#FFD700" # Gold

def build_setup_chart(result: TradeResult, ohlc_df: pd.DataFrame, config: PlottingConfig = PlottingConfig()) -> str:
    setup = result.setup
    
    # Slice mapping - 50 before sweep, 20 after exit
    # sweep_event stores the time it happened
    sweep_time = setup.sweep_event.sweep_candle_time
    exit_time = result.exit_time if result.exit_time else ohlc_df.index[-1]
    
    # Get indices for slicing
    try:
        sweep_idx = ohlc_df.index.get_loc(sweep_time)
        exit_idx = ohlc_df.index.get_loc(exit_time)
    except KeyError:
        # Fallback if indices are not found exactly
        sweep_idx = ohlc_df.index.get_indexer([sweep_time], method='nearest')[0]
        exit_idx = ohlc_df.index.get_indexer([exit_time], method='nearest')[0]
        
    start_idx = max(0, sweep_idx - config.bars_before_sweep)
    end_idx = min(len(ohlc_df) - 1, exit_idx + config.bars_after_exit)
    
    df_slice = ohlc_df.iloc[start_idx : end_idx + 1]
    
    fig = go.Figure()
    
    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=df_slice.index,
        open=df_slice['open'],
        high=df_slice['high'],
        low=df_slice['low'],
        close=df_slice['close'],
        increasing_line_color=config.bullish_candle,
        decreasing_line_color=config.bearish_candle,
        name='NQ 1M'
    ))
    
    # IFVG Zone
    ifvg_color = config.ifvg_zone_long if setup.direction == Direction.LONG else config.ifvg_zone_short
    fig.add_shape(
        type="rect",
        x0=setup.created_at,
        y0=setup.fvg_top,
        x1=exit_time,
        y1=setup.fvg_bottom,
        fillcolor=ifvg_color,
        opacity=1, # Layer transparency handled by rgba color
        layer="below",
        line_width=0,
    )
    
    # IFVG Boundary line
    fig.add_hline(y=setup.fail_stop_level, line_dash="dash", line_color=config.fail_stop, 
                  annotation_text="Fail Stop Bound", annotation_position="top left")
    
    # Trade Levels
    fig.add_hline(y=setup.entry_price, line_color=config.entry, annotation_text="Entry")
    fig.add_hline(y=setup.stop_price, line_color=config.stop, annotation_text="Stop")
    fig.add_hline(y=setup.target_price, line_color=config.target, annotation_text="Target")
    
    # Indicators/Markers
    # Sweep Marker
    fig.add_vline(x=sweep_time, line_color=config.sweep_marker, line_width=2, 
                  annotation_text="Liquidity Sweep")
    
    # Entry Marker
    fig.add_trace(go.Scatter(
        x=[setup.created_at],
        y=[setup.entry_price],
        mode='markers',
        marker=dict(symbol='triangle-up' if setup.direction == Direction.LONG else 'triangle-down', 
                    size=12, color=config.entry),
        name='Entry'
    ))
    
    # Exit Marker
    if result.exit_time:
        fig.add_trace(go.Scatter(
            x=[result.exit_time],
            y=[result.raw_exit_price],
            mode='markers',
            marker=dict(symbol='x', size=12, color=config.bullish_candle if result.net_pnl > 0 else config.bearish_candle),
            name=f'Exit ({result.exit_type})'
        ))
    
    # Layout and Title
    title = (
        f"{setup.setup_id} | {setup.direction.value.upper()} {setup.model_type.value.upper()} | "
        f"Grade: {setup.grade.value} | RR: {setup.risk_reward:.1f}R | "
        f"Result: {result.exit_type} | Net PnL: ${result.net_pnl:+,.2f}"
    )
    
    fig.update_layout(
        title=title,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        yaxis_title="NQ Price",
        margin=dict(l=50, r=50, t=80, b=50)
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

def build_equity_chart(account: AccountState) -> str:
    # Build equity curve trace
    history = account.trade_history
    equity_values = [account.starting_capital if hasattr(account, 'starting_capital') else 100000.00]
    dates = [history[0].setup.created_at if history else datetime.now()]
    
    curr = equity_values[0]
    for r in history:
        if r.status == "closed":
            curr += r.net_pnl
            equity_values.append(curr)
            dates.append(r.exit_time if r.exit_time else dates[-1])
            
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates,
        y=equity_values,
        mode='lines+markers',
        name='Equity Curve',
        line=dict(color='#26a69a', width=2)
    ))
    
    fig.update_layout(
        title="Backtest Equity Curve",
        template="plotly_dark",
        yaxis_title="Portfolio Value ($)",
        xaxis_title="Time"
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')
