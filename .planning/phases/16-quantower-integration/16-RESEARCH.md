# Phase 16 Research: Quantower API Integration & Live Bridge

## Overview
The goal is to connect the "Dual Strategy" (Python-based Daniel Model and Node.js-based LG/ORB Models) to the Quantower trading platform for live execution without using the proprietary "Algo" extension.

## Standard Stack
- **Quantower Terminal**: The central trading hub.
- **Quantower SDK**: Managed C# (.NET) libraries for platform interaction (`TradingPlatform.BusinessLayer.dll`).
- **C# Bridge Plugin**: A custom-built plugin running inside Quantower that exposes a local communication layer.
- **Communication Protocol**: WebSocket (WS) or REST over Localhost (JSON format).
- **External Stack**:
  - **Python**: Using `websockets` or `requests` to send signals and receive account/market data.
  - **Node.js**: Using `ws` or `http` to interact with the same bridge.

## Architecture Patterns
Since Quantower does not provide a native REST/WebSocket API for external processes, the **Sidecar Bridge Pattern** is the standard architectural approach:

1.  **Bridge Layer (C#)**:
    *   Initialize a `WebSocketServer` or `HttpListener` on startup.
    *   Map incoming JSON commands to Quantower SDK calls (e.g., `Core.Instance.Trading.PlaceOrder`).
    *   Broadcast platform events (fills, P&L updates, market data) to connected clients.
2.  **Strategy Layer (Python/Node.js)**:
    *   Stay independent of the trading platform.
    *   Connect to the local bridge via a socket.
    *   Send execution requests and receive feedback asynchronously.

## Don't Hand-Roll
- **The Bridge from Scratch**: Use **[NeoNix-Lab/qtpy-dispatch-sharp-core](https://github.com/NeoNix-Lab/qtpy-dispatch-sharp-core)** as a starting point. It is a modern (2025) C# bridge designed specifically to expose Quantower to Python/JS via JSON dispatcher.
- **WebSocket Servers in C#**: Use established libraries like `Fleck` or `SignalR` if building a custom bridge, rather than raw TCP sockets.

## Common Pitfalls
- **Thread Safety**: Quantower SDK methods must often be called on the main UI thread or specific background threads. The bridge must handle this dispatching correctly.
- **Latency**: While local sockets are fast (~1-5ms), excessive JSON serialization/deserialization for high-frequency tick data can add overhead. For the "Dual Strategy" (1-min based), this is negligible.
- **Connection Drops**: The external strategy must handle reconnection logic if the Quantower bridge or terminal restarts.
- **Order Synchronization**: Ensure the bridge assigns unique client IDs to orders so the strategy can track them independently of Quantower's internal IDs.

## Implementation Path
1.  **Install Quantower SDK**: Download the SDK and reference the necessary DLLs in a new C# Class Library project.
2.  **Build the Dispatcher**: Create a plugin that implements `IPlugin` or `IStrategy` in Quantower.
3.  **Local Server Setup**: Integrate a WebSocket server within the plugin that listens on `localhost:8080`.
4.  **JSON Schema Design**: Define a standard schema for `place_order`, `cancel_order`, `get_positions`, and `market_data_update`.
5.  **Python/Node Client**:
    *   In Python: Create a `LiveExecutionClient` class.
    *   In Node.js: Create a similar client for the LG/ORB modules.
6.  **UAT/Paper Trading**: Connect to a Quantower Paper Trading or SIM account first to verify the bridge integrity before going live.

## Code Examples

### C# Bridge Sniper (Pseudo-code)
```csharp
public class TradingBridge : IPlugin {
    private WebSocketServer server;

    public void OnResume() {
        server = new WebSocketServer("ws://127.0.0.1:8080");
        server.Start(socket => {
            socket.OnMessage = msg => {
                var cmd = JsonConvert.DeserializeObject<TradeCommand>(msg);
                ExecuteTrade(cmd);
            };
        });
    }

    private void ExecuteTrade(TradeCommand cmd) {
        var account = Core.Instance.Trading.Accounts.FirstOrDefault();
        Core.Instance.Trading.PlaceOrder(new PlaceOrderRequestParameters() {
            Account = account,
            Symbol = Core.Instance.Symbols.GetSymbol(cmd.Symbol),
            Side = cmd.Side == "Buy" ? Side.Buy : Side.Sell,
            Quantity = cmd.Qty
        });
    }
}
```

### Python Signal Emitter
```python
import asyncio
import websockets
import json

async def send_order(symbol, side, qty):
    uri = "ws://localhost:8080"
    async with websockets.connect(uri) as websocket:
        order = {
            "action": "place_order",
            "symbol": symbol,
            "side": side,
            "qty": qty
        }
        await websocket.send(json.dumps(order))
        response = await websocket.recv()
        print(f"Quantower Response: {response}")
```

## Confidence Levels
- **Technical Feasibility**: High (Standard practice for Quantower power-users).
- **Latency Suitability**: High (1-min strategies are not micro-latency sensitive).
- **Setup Complexity**: Medium (Requires C# compilation and plugin installation).
