# NinjaTrader Live Bridge - Launch Guide

This document outlines the exact steps to launch the live trading engine.

## 1. NinjaTrader 8 Setup (One-time or Update)
1.  **Copy Strategy**: Copy `live/NinjaScript/PythonSignalStrategy.cs` to:
    `Documents\NinjaTrader 8\bin\Custom\Strategies\`
2.  **Compile**: Open the NinjaScript Editor in NinjaTrader 8 and press **F5** to compile.
3.  **Attach**: Open an NQ 1-minute chart and attach the `PythonSignalStrategy`.
    *   Set `Host` to `127.0.0.1`
    *   Set `Port` to `6789`
    *   Ensure **Simulation** or **Live** account is selected.

## 2. Environment Configuration
Check your `.env` file in the root directory:
```
NINJA_HOST=127.0.0.1
NINJA_PORT=6789
RITHMIC_CONTRACTS=1
MAX_DAILY_LOSS=-2000
```
*   `MAX_DAILY_LOSS`: The bridge will stop all trading if daily P&L drops below this amount (USD).

## 3. Running the Engine
1.  **Open Terminal**: Open a terminal in the project root.
2.  **Start Python Server**:
    ```bash
    python -m live.run_live
    ```
3.  **Activate Strategy**: In NinjaTrader, ensure the strategy is "Enabled" on the chart.
4.  **Verify Connection**: The Python terminal should log:
    `"NinjaTrader Client connected from ..."`

## 4. Operational Flow
- **ORB Strategy**: Active from 8:00 AM ET (Zone formation) to 4:15 PM ET (Flat out).
- **Dodgy Strategy**: Active throughout the session, monitoring 1H sweeps and 1m FVG displacements.
- **Safety**: The `NinjaBridge` manages your daily drawdown automatically via the `MAX_DAILY_LOSS` guard.
