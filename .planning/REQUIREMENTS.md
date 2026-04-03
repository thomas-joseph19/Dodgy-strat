# Requirements

## Validated
(None yet — ship to validate)

## Active
- [ ] Read 1-minute NQ OHLCV data from the provided `.parquet` file.
- [ ] Implement `Candle` dataclass and pure functions for basic structural math without lookahead bias.
- [ ] Implement strict `detect_swing_high` and `detect_swing_low` functions (must wait `lookback` bars before confirming).
- [ ] Implement Liquidity Level logic: classify EQH, EQL, etc. based on specific tolerances (0.05%).
- [ ] Implement Liquidity Sweep logic: require extension > 1 pt and body recovery < 2 pt.
- [ ] Detect Bullish/Bearish Fair Value Gaps (FVG) and stacked series merging.
- [ ] Implement Inverted FVG (IFVG) triggers. Requires body to cross boundaries by at least 1 point.
- [ ] Define the Execution Engine with setup-by-setup evaluation.
- [ ] Implement Fail Stop, Swing Stop, and Narrow Stop management.
- [ ] Output backtesting metrics (Net profit, win rate, Sharpe, Sortino ratios).
- [ ] Generate Plotly HTML charts for each individual trade setup for deep inspection.

## Out of Scope
- Real-time/live trading execution (this is currently for backtesting and historical signal generation).
- Parallel running of overlapping trades impacting account margin linearly (running setup-by-setup independently as instructed).
