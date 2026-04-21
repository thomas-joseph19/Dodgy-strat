# Requirements

## Validated (v1.0 — Institutional Backtest Engine)
- [x] Read 1-minute NQ OHLCV data from the provided `.parquet` file.
- [x] Implement `Candle` dataclass and pure functions for basic structural math without lookahead bias.
- [x] Implement strict `detect_swing_high` and `detect_swing_low` functions (must wait `lookback` bars before confirming).
- [x] Implement Liquidity Level logic: classify EQH, EQL, etc. based on specific tolerances (0.05%).
- [x] Implement Liquidity Sweep logic: require extension > 1 pt and body recovery < 2 pt.
- [x] Detect Bullish/Bearish Fair Value Gaps (FVG) and stacked series merging.
- [x] Implement Inverted FVG (IFVG) triggers. Requires body to cross boundaries by at least 1 point.
- [x] Define the Execution Engine with setup-by-setup evaluation.
- [x] Implement Fail Stop, Swing Stop, and Narrow Stop management.
- [x] Output backtesting metrics (Net profit, win rate, Sharpe, Sortino ratios).
- [x] Generate Plotly HTML charts for each individual trade setup for deep inspection.

## Active (v2.0 — Live Trading)
- [ ] **REQ-SAFETY-01:** Implement daily loss limit guard in live bridge — refuse new signals when cumulative P&L exceeds MAX_DAILY_LOSS. *(Phase 19)*
- [ ] **REQ-LIVE-01:** Remove orphaned Quantower bridge code and migrate `daniel_mechanical_runner.py` references to NinjaTrader path. *(Phase 20)*

## Deferred
- REQ-LIVE-02: Node.js ORB live runner — deferred because ORB runs through Python engine via NinjaTrader bridge.

## Out of Scope
- Parallel running of overlapping trades impacting account margin linearly (running setup-by-setup independently as instructed).

## Traceability

| REQ-ID | Description | Phase | Status |
|--------|-------------|-------|--------|
| REQ-SAFETY-01 | Prop Firm daily loss guard | 19 | Pending |
| REQ-LIVE-01 | Quantower cleanup & runner migration | 20 | Pending |
| REQ-LIVE-02 | Node.js ORB live runner | — | Deferred |
