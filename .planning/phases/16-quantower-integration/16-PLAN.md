# Phase 16 Plan: Quantower API Integration & Live Bridge

## Status: PLANNING

## Goal
Build a robust, reusable C# Bridge for Quantower that exposes a WebSocket/JSON interface, allowing Python (Daniel Model) and Node.js (LG/ORB Models) to execute live trades on Prop Firm accounts.

## Architecture & Schema
This implementation uses the **Sidecar Bridge Pattern**. The Trading Platform (Quantower) acts as the execution server, and the Strategies act as clients.

### Unified JSON Schema
All communication between Strategies and the Bridge must follow this structure:

```json
{
  "client_id": "DANIEL_PYTHON_01",
  "action": "ORDER_SEND",
  "params": {
    "symbol": "NQ H4",
    "side": "Buy",
    "type": "Market",
    "qty": 1,
    "sl_ticks": 40,
    "tp_ticks": 80,
    "comment": "IFVG Entry"
  }
}
```

---

## Tasks

### Wave 1: C# Bridge Foundation (Zero-Dependency) - [DONE]
- [x] **T16.1: TCP Bridge Script** (`BridgeScript.cs`)
  - Exposes standard TCP socket on port 8081.
  - Streams bi-directional data (Quotes Out / Orders In).
- [x] **T16.2: Python & Node Client Libraries**
  - `quantower_live.py` (Python)
  - `bridge-client.js` (Node.js)

### Wave 2: Live Integration (NEXT)
- [ ] **T16.3: Daniel Live Runner**
  - Use `QuantowerLive` class to ingest real-time bid/ask.
  - Pipe data into existing feature engineering (`vectorized.py`).
  - Trigger `send_order` based on XGBoost predictions.
- [ ] **T16.4: LG/ORB Live Runner**
  - Integrate `bridge-client.js` into the existing Node.js signal logic.

### Wave 3: Safety & VPS
- [ ] **T16.5: Prop Firm Guard**
  - Add "Max Daily Loss" hard-check directly inside `BridgeScript.cs`.
- [ ] **T16.6: VPS Final Setup**
  - Ensure Quantower starts on Windows boot.

---

## Technical Handoff: How it works
1. **Bridge**: `BridgeScript.cs` runs *inside* Quantower as a Strategy. It listens on `127.0.0.1:8081`.
2. **Data**: Every price tick, the Bridge sends: `QUOTE,SYMBOL,BID,ASK,LAST\n`.
3. **Execution**: Clients send: `ORDER_SEND,SYMBOL,SIDE,QTY,COMMENT\n`.
4. **Compatibility**: No external DLLs or NuGet packages are needed in Quantower. Standard `System.Net.Sockets` only.

---

## Verification Criteria (UAT)
1.  **Connection Persistence**: Bridge automatically recovers if the Python script is restarted.
2.  **Order Integrity**: Stop Loss and Take Profit levels are correctly attached to Market orders on Rithmic/Tradovate.
3.  **Concurrency**: Bridge handles simultaneous signals from Daniel (Python) and LG (Node) without dropping messages.
4.  **Prop Firm Safety**: Hard-limit inside the C# Bridge successfully prevents any trade if the daily loss threshold is hit in Quantower.

## Handover Context for Other Agents
> [!IMPORTANT]
> This Bridge is designed to be **Strategy Agnostic**. Any future strategy (Javascript, Python, or even C++) can connect to `ws://127.0.0.1:8080` and send the standard JSON payload to execute trades.
> 
> Key Quantower SDK Namespaces for development:
> - `TradingPlatform.BusinessLayer.Core` - Global access
> - `TradingPlatform.BusinessLayer.OrderRequestParameters` - Entry parameters
> - `TradingPlatform.BusinessLayer.Symbol` - Instrument data
