# Roadmap: DodgysDD IFVG Strategy Automation

## Proposed Roadmap

**5 phases** | **21 requirements mapped** | All v1 requirements covered ✓

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Data & Framework | Set up project architecture and OHLCV data pipelines | Complete    | 2026-04-03 |
| 2 | Core Mechanics | 3/3 | Complete    | 2026-04-03 |
| 3 | Signal Engine | 3/3 | Complete    | 2026-04-03 |
| 4 | Execution Simulator | 3/3 | Complete    | 2026-04-03 |
| 5 | Reports & Visuals | 3/3 | Complete    | 2026-04-03 |

### Phase Details

**Phase 1: Data & Framework**
Goal: Set up project architecture and OHLCV data pipelines
Requirements: DATA-01, DATA-02
Success criteria:
1. System can successfully load 1-min NQ OHLCV into pandas DataFrames.
2. Parameter configuration file or class exists, controlling settings independently from the logic.

**Phase 2: Core Mechanics**
Goal: Algorithmically identify sweeps, FVGs, and Inversions
Requirements: CORE-01, CORE-02, CORE-03, CORE-04, CORE-05
Success criteria:
1. Given OHLCV data, system outputs exact timestamps of liquidity sweeps (BSL/SSL).
2. Given OHLCV data, system outputs identified Bullish and Bearish stacked FVGs.
3. System reliably calculates IFVG triggers when a candle body closes across a detected FVG zone.

**Phase 3: Signal Engine**
Goal: Mechanize full Reversal and Continuation models
Requirements: SIG-01, SIG-02, SIG-03, SIG-04
Success criteria:
1. Signal array explicitly pinpoints valid Reversal and Continuation triggering setups.
2. Signals appropriately cancel out if internal highs/lows are hit concurrently.

**Phase 4: Execution Simulator**
Goal: Handle entry, RR profiling, dynamic stops, entries, and target exits
Requirements: EXEC-01, EXEC-02, EXEC-03, EXEC-04, EXEC-05, EXEC-06
Success criteria:
1. Proper "Fail Stops" and Break Even movements are enacted algorithmically in simulation.
2. Slippage and Commission calculations accurately reduce net profit.
3. Simulated execution reaches HTF specified draws on liquidity (DOL) correctly.

**Phase 5: Reports & Visuals**
Goal: Generate performance metrics, equity curves, and setup plots
Requirements: REP-01, REP-02, REP-03, REP-04
Success criteria:
1. Final script outputs Sharpe, Win Rate, and Max DD based on execution backtest log.
2. matplotlib/plotly renders equity+drawdown curve.
3. Users can plot a visual single trade verification chart.
