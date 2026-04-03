import plotly.graph_objects as go
import pandas as pd
from src.execution import TradeSetup, TradeResult, StopType, Direction
from datetime import timedelta

def build_setup_chart(result: TradeResult, ohlc_df: pd.DataFrame, bars_before=50, bars_after=20):
    setup = result.setup
    
    # Slice data
    sweep_time = setup.created_at # In reality, we should use sweep candle time. For simplicity, we use creation time.
    # Actually wait - creation time is entry candle close.
    # We should use the sweep time from the setup object if available.
    
    # We'll slice around the trade window
    start_time = setup.created_at - timedelta(minutes=bars_before)
    end_time = result.exit_candle_time + timedelta(minutes=bars_after)
    
    mask = (ohlc_df['timestamp'] >= start_time) & (ohlc_df['timestamp'] <= end_time)
    df = ohlc_df.loc[mask].copy()
    
    fig = go.Figure(data=[go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='NQ'
    )])
    
    # Add Entry, Stop, Target, FailStop lines
    fig.add_hline(y=setup.entry_price, line_dash="dash", line_color="blue", annotation_text="Entry")
    fig.add_hline(y=setup.stop_price, line_dash="dash", line_color="red", annotation_text="Hard Stop")
    fig.add_hline(y=setup.target_price, line_dash="dash", line_color="green", annotation_text="Target")
    
    
    # Add markers for entry/exit
    fig.add_trace(go.Scatter(
        x=[setup.created_at], y=[setup.entry_price],
        mode="markers", marker_symbol="triangle-up", marker_color="blue", marker_size=15, name="Entry Marker"
    ))
    
    fig.add_trace(go.Scatter(
        x=[result.exit_candle_time], y=[result.exit_price],
        mode="markers", marker_symbol="triangle-down" if result.setup.direction == Direction.LONG else "triangle-up", 
        marker_color="red" if "STOP" in result.exit_type else "green", marker_size=15, name="Exit Marker"
    ))
    
    fig.update_layout(
        title=f"Trade {setup.setup_id} | {result.exit_type} | Net PnL: ${result.net_pnl:,.2f}",
        xaxis_rangeslider_visible=False,
        template="plotly_dark"
    )
    
    return fig
