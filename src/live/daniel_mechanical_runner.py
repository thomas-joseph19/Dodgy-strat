import sys
import os
import time
import asyncio
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass

# Add parent dir to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.live.quantower_live import QuantowerLive
from src.core import Candle, THRESHOLDS
from src.fvg import detect_fvg, FairValueGap
from src.liquidity import LiquidityLevel, SweepEvent, detect_sweep

@dataclass
class LocalState:
    candles: deque  # 1min candles
    levels: list    # LiquidityLevel objects
    active_sweep: SweepEvent = None
    last_processed_timestamp: datetime = None
    current_candle: Candle = None

class DanielMechanicalRunner:
    def __init__(self, symbol="NQ", account="SIM123", qty=1):
        self.symbol = symbol
        self.account = account
        self.qty = qty
        self.state = LocalState(candles=deque(maxlen=100), levels=[])
        self.bridge = QuantowerLive(port=8081)
        
        # Start with some hardcoded levels or logic to build them
        # In a real scenario, we'd fetch the last 1H high/low from a CSV or API
        # For now, we'll initialize with basic levels if provided or detected
    
    def on_tick(self, quote):
        # quote format: {'symbol': 'NQ', 'bid': 18000.25, 'ask': 18000.50, 'last': 18000.25}
        price = quote['last']
        ts = datetime.now()
        
        # 1. Update 1min candle logic
        # For simplicity in this runner, we 'close' a candle every 60 seconds
        if self.state.current_candle is None:
            self.state.current_candle = Candle(ts, price, price, price, price)
        
        if ts >= self.state.current_candle.timestamp + timedelta(minutes=1):
            # Close current candle
            completed_candle = self.state.current_candle
            self.state.candles.append(completed_candle)
            
            # Reset for new candle
            self.state.current_candle = Candle(ts, price, price, price, price)
            
            # 2. Process Mechanical Logic on Close
            self.evaluate_logic(completed_candle)
        else:
            # Update current candle
            self.state.current_candle.high = max(self.state.current_candle.high, price)
            self.state.current_candle.low = min(self.state.current_candle.low, price)
            self.state.current_candle.close = price

    def evaluate_logic(self, candle):
        print(f"[{datetime.now()}] Candle Closed: {candle.close} | Levels: {len(self.state.levels)}")
        
        # A. Detect Sweeps
        if not self.state.active_sweep:
            sweep = detect_sweep(candle, len(self.state.candles), self.state.levels)
            if sweep:
                print(f"!!! SWEEP DETECTED: {sweep.direction} at {sweep.swept_level.price}")
                self.state.active_sweep = sweep
        else:
            self.state.active_sweep.bars_since_sweep += 1
            if self.state.active_sweep.bars_since_sweep > 10: # Expire sweep after 10 mins
                print("Sweep Expired.")
                self.state.active_sweep = None

        # B. If Sweep Active, look for FVG Displacement
        if self.state.active_sweep:
            fvg = detect_fvg(list(self.state.candles), len(self.state.candles)-1)
            if fvg:
                # Check direction match
                if self.state.active_sweep.direction == "SSL_SWEPT" and fvg.direction == "BULLISH":
                    self.execute_trade("Buy", fvg)
                elif self.state.active_sweep.direction == "BSL_SWEPT" and fvg.direction == "BEARISH":
                    self.execute_trade("Sell", fvg)

    def execute_trade(self, side, fvg):
        print(f">>> EXECUTING {side} TRADE | FVG at {fvg.fvg_top}/{fvg.fvg_bottom}")
        # Send order to bridge
        self.bridge.send_order(self.symbol, side, self.qty, f"Daniel-Mechanical-{self.symbol}")
        # Reset sweep to avoid double-entry
        self.state.active_sweep = None

    async def run(self):
        print(f"Starting Daniel Mechanical Runner for {self.symbol}...")
        
        # Hardcode some session levels for testing (would ideally be dynamic)
        # Suggesting user provides these or we add a level-detector task
        self.state.levels = [
            LiquidityLevel(18050.0, "BSL", "SESSION_HIGH", 1, datetime.now()),
            LiquidityLevel(17950.0, "SSL", "SESSION_LOW", 1, datetime.now())
        ]
        
        # Run the TCP loop
        await self.bridge.start_streaming(self.on_tick)

if __name__ == "__main__":
    runner = DanielMechanicalRunner(symbol="NQ", account="SIM123", qty=1)
    try:
        asyncio.run(runner.run())
    except KeyboardInterrupt:
        print("Stopping runner.")
