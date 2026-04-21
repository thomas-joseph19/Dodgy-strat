# Phase 17 Plan: Mechanical Live Strategy Integration

## Goal
Implement the core trading logic ("The Brain") for both the Daniel and ORB strategies in a live execution environment using the **NinjaTrader TCP Bridge** (`live/ninja_bridge.py`). This version is **strictly mechanical**, bypassing the XGBoost/ML filters.

## Architecture
The live runner uses an async event loop via `NinjaBridge`:
1.  **Ingest**: Receive BAR JSON updates from NinjaTrader via TCP on `127.0.0.1:6789`.
2.  **State**: Update local price buffers (OHLC construction from bars).
3.  **Signal**: Check mechanical conditions via `OrbProcessor` and `DodgyProcessor`.
4.  **Action**: Dispatch SIGNAL JSON commands back to NinjaTrader for order execution.

---

## Tasks

### Wave 1: Daniel Mechanical Engine [DONE]
- [x] **T17.1: Port Mechanical Logic to Live Emitter**
  - Created `live/dodgy_processor.py`.
  - Implements real-time FVG detection (1min timeframe).
  - Implements HTF level monitoring (1hr Liquidity Sweeps).
  - Logic: IF price sweeps 1H level AND 1min FVG forms, THEN emit Signal.

### Wave 2: ORB Mechanical Engine [DONE]
- [x] **T17.2: Implement Live Opening Range Breakout**
  - Created `live/orb_processor.py`.
  - Monitors NY Open zone (8:00-8:10 AM ET).
  - Captures bias from 9:30 AM, limit fill at zone midpoint.
  - Logic: IF breakout bias established AND retrace to midpoint, THEN emit Signal.

### Wave 3: Safety & Lifecycle [DONE via Phase 19]
- [x] **T17.3: Position Tracking & SL/TP Management**
  - `live/engine.py` tracks active trade state with break-even logic.
  - SL/TP attached to NinjaTrader bracket orders via managed approach.
- [x] **T17.4: Prop Firm Safety Guard** (moved to Phase 19)
  - `MAX_DAILY_LOSS` enforcement in `ninja_bridge.py`.

---

## Verification Criteria (UAT)
1.  **Signal Validity**: Python script triggers an order *exactly* when a mechanical setup forms on the chart.
2.  **Order Execution**: NinjaTrader SIM shows the order with correct Qty and bracket (SL/TP).
3.  **Independence**: ORB and Dodgy signals are processed by the same engine — whichever fires first owns the trade slot.
4.  **No ML**: Verified that no XGBoost models are loaded or queried during the decision process.
