# Quick Task 260427-o5n: Reset LiveEngine state on NT connection - Summary

## Work Completed
- Added state-reset logic to `_handle_client` in `live/ninja_bridge.py`.
- Whenever NinjaTrader connects, the bridge now calls `self.__init__(...)` to completely reset the underlying engine.

## Outcomes
- NinjaTrader historical backtests can now be run repeatedly.
- Without this fix, the Python server was carrying "future" historical data (like a future `_last_date` and open trades) into the second and third backtests, causing it to take 0 trades. Now, each connection correctly guarantees a fresh trading simulation environment.
