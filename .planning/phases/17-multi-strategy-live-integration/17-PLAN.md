# Phase 17 Plan: Mechanical Live Strategy Integration

## Goal
Implement the core trading logic ("The Brain") for both the Daniel and ORB strategies in a live execution environment using the Quantower TCP Bridge. This version is **strictly mechanical**, bypassing the XGBoost/ML filters as requested.

## Architecture
The live runner will use an async event loop:
1.  **Ingest**: Receive `QUOTE` updates from `127.0.0.1:8081`.
2.  **State**: Update local price buffers (OHLC construction from ticks).
3.  **Signal**: Check mechanical conditions (e.g., HTF Sweep + LTF FVG).
4.  **Action**: Dispatch `ORDER_SEND` commands to the Bridge.

---

## Tasks

### Wave 1: Daniel Mechanical Engine
- [/] **T17.1: Port Mechanical Logic to Live Emitter**
  - Create `src/live/daniel_mechanical_runner.py`.
  - Implement real-time FVG detection (1min timeframe).
  - Implement HTF level monitoring (1hr Liquidity Sweeps).
  - Logic: IF price sweeps 1H level AND 1min FVG forms, THEN Send Market Order.

### Wave 2: ORB Mechanical Engine
- [/] **T17.2: Implement Live Opening Range Breakout**
  - Create `strategies/lg_model/src/live/orb_live_runner.js`.
  - Monitor NY Open (9:30 AM EST).
  - Capture High/Low at 10:00 AM EST.
  - Logic: IF price breaks High, THEN Buy Market; IF price breaks Low, THEN Sell Market.

### Wave 3: Safety & Lifecycle
- [/] **T17.3: Position Tracking & SL/TP Management**
  - Ensure local runners track state (to avoid over-trading).
  - Implement hard SL/TP attachment to order requests.

---

## Verification Criteria (UAT)
1.  **Signal Validity**: Python script triggers an order *exactly* when a mechanical setup forms on the chart.
2.  **Order Execution**: Quantower SIM shows the order with correct Qty and Comment ("Mechanical Entry").
3.  **Independence**: Daniel (Python) and ORB (Node) can run simultaneously without blocking each other on the TCP port.
4.  **No ML**: Verified that no XGBoost models are loaded or queried during the decision process.
