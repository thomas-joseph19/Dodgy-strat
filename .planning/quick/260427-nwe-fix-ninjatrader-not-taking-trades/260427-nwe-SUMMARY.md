# Quick Task 260427-nwe: Fix NinjaTrader not taking trades - Summary

## Work Completed
- Switched entry order types in `PythonSignalStrategy.cs` from `EnterLongLimit`/`EnterShortLimit` to `EnterLong`/`EnterShort` market orders.
- This resolves the issue where NinjaTrader was missing limit fills because Python generates signals intrinsically post-bar, meaning the limit order was placed in NinjaTrader after the market had already moved. By executing at market, NinjaTrader will stay synchronized with the Python server's trade state.

## Outcomes
NinjaTrader should now take actual trades upon receiving `SIGNAL` commands from Python.
