# Phase 4: Risk & Execution - Discussion Log

**Date:** 2026-04-02
**Phase:** Phase 4: Risk & Execution (Execution Simulator)

## Q1: Execution Matrix Model
**User context provided:**
Row-by-row simultaneous linear simulation generates unpredictable margin bounds and position dependency.

**User selection:** 
- Implement **Setup-by-Setup chronological processing**. Each `TradeSetup` gets taken iteratively using a localized evaluation of raw data stretching from `entry_candle` to whichever resolves the exit limits.
- Evaluates Exit priority rigorously. Resolves OHLC limitations assuming extreme risk (Stop hit over Target).

## Q2: Fail Stop Logic (Close Prices)
**User context provided:**
Fail Stops occur exactly on candle closes back over the threshold IFVG gap lines.

**User selection:**
- Fill execution runs natively against the `candle.close`. Because a simulated Market Order runs after, structural slippage adjusts exactly against the Close rather than creating hypothetical fill metrics intra-bar.

## Q3/Q4: Sizing Model & Slippage Math
**User context provided:**
Fixed sizing generates poor P&L representations for actual testing. Trading NQ is fundamentally scaled in multiples depending on the stop spacing.

**User selection:** 
- Apply strict 1% dynamic risk metrics against standard 100k account bounds per trade.
- Limit output sizing physically between exactly 1 to 10 contracts max per trade.
- $20 p/pt multiplier math mapping against standard $4.00 round trip commissioning. 
- Apply strictly 1 tick raw directional spread adjustments matching 0.25 point loss increments per open/close sequence. 
- All entry sequences explicitly restricted only inside regular RTH sessions `09:30 - 16:00 ET` where tick liquidity justifies boundaries above.
