# Quick Task 260427-nwe: Fix NinjaTrader not taking trades

## Context
NinjaTrader is receiving `SIGNAL` messages from Python, but it uses `EnterLongLimit` with the exact entry price provided by Python. Python evaluates fills intrinsically and only sends the signal *after* the bar closes. As a result, the limit order is placed post-bar, and if the price has already bounced or moved away, the limit order never fills.

## Task 1: Convert Limit Orders to Market Orders
- **Files**: `live/NinjaScript/PythonSignalStrategy.cs`
- **Action**: Replace `EnterLongLimit` and `EnterShortLimit` with `EnterLong` and `EnterShort`. Remove the `isLiveUntilCancelled` and `limitPrice` arguments.
- **Verify**: The strategy should call `EnterLong(0, sig.Qty, sig.Id);` and `EnterShort(0, sig.Qty, sig.Id);`.
- **Done**: When the file is updated.
