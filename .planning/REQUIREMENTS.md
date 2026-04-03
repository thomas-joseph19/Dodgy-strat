# Requirements: DodgysDD IFVG Strategy Automation

**Defined:** 2026-04-02
**Core Value:** Mechanize the DodgysDD IFVG strategy into fully rule-based logic for deterministic backtesting.

## v1 Requirements

### Data Management
- [ ] **DATA-01**: Data Loader imports 1-minute NQ OHLCV historical data.
- [ ] **DATA-02**: System parameters (thresholds, indicators, stop distances) are fully configurable and exposed.

### Core Mechanics
- [ ] **CORE-01**: System algorithmically identifies internal swing highs (BSL) and swing lows (SSL).
- [ ] **CORE-02**: System algorithmically detects liquidity sweeps (price poking above/below a tracked BSL/SSL pool).
- [ ] **CORE-03**: System detects Bearish and Bullish Fair Value Gaps (FVG) based on 3-candle mechanics.
- [ ] **CORE-04**: System detects valid FVG Inversions (IFVG) where a candle body closes definitively across the FVG boundary.
- [ ] **CORE-05**: System merges consecutive stacked FVGs into a single tradable zone.

### Signal Generation
- [ ] **SIG-01**: Signal Generator defines Reversal Model entry logic (Liquidity Sweep -> Opposite FVG forms -> IFVG confirmed).
- [ ] **SIG-02**: Signal Generator defines Continuation Model entry logic (≥50% retracement of displacement leg -> New IFVG confirmed).
- [ ] **SIG-03**: Signal Generator enforces the Mechanical Validity Check (entry invalid if the next internal high/low is hit before or during the IFVG trigger).
- [ ] **SIG-04**: Signal Generator continues to track a directional bias for secondary entry setups even if the primary valid entry is invalidated.

### Risk & Execution Details
- [ ] **EXEC-01**: Backtest engine places trade entries at the exact close of the confirmed inversion IFVG candle.
- [ ] **EXEC-02**: System automatically calculates proper Break-Even (BE) points (at internal highs/lows or intervening FVGs) and moves the stop appropriately.
- [ ] **EXEC-03**: System calculates "Fail Stop" (soft exit on reverse IFVG close, plus catastrophic swing stop).
- [ ] **EXEC-04**: System calculates situational "Swing Stope" and "Narrow Stop" (based on inversion candle momentum and RR thresholds).
- [ ] **EXEC-05**: Backtest engine targets the designated draw on liquidity (DOL) for each trade.
- [ ] **EXEC-06**: Backtesting math successfully calculates standard slippage and commissions per futures contract metrics.

### Reporting & Visuals
- [ ] **REP-01**: System produces a comprehensive tabular Trade List (entry, exit, stop, pnl, direction).
- [ ] **REP-02**: System tracks portfolio balance and computes Sharpe, Max Drawdown, Win Rate, and Profit Factor metrics.
- [ ] **REP-03**: System plots visual equity and drawdown performance curves over time.
- [ ] **REP-04**: System provides a plotting function to visually inspect a generated trade setup on a candlestick chart (showing FVG, entry, target).

## v2 Requirements

### Analytics & ML
- **ML-01**: Export engineered strategy setup states (features, DOLs, sweeps) to CSV/Parquet for ML training.
- **ML-02**: Abstract the Signal Generator component so an ML inference model can drop-in and replace it.

### Alternative Data (Future)
- **ALT-01**: Integrate 1-second BBO (Best Bid Offer) tick data for execution precision.
- **ALT-02**: Combine Options Flow with liquidity sweep logic to filter high-probability sweeps.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Machine Learning inference in Phase 1 | Focus is on getting the mechanical logic exactly right first to measure baseline performance. |
| Alt-Data execution fills | Overcomplicates V1 debugging. 1-minute OHLC is sufficient to validate core pattern logic. |
| Multi-asset support concurrently | Only focus on NQ. Keeps data requirements and behavior scoping completely deterministic. |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | | Pending |
| DATA-02 | | Pending |
| CORE-01 | | Pending |
| CORE-02 | | Pending |
| CORE-03 | | Pending |
| CORE-04 | | Pending |
| CORE-05 | | Pending |
| SIG-01 | | Pending |
| SIG-02 | | Pending |
| SIG-03 | | Pending |
| SIG-04 | | Pending |
| EXEC-01 | | Pending |
| EXEC-02 | | Pending |
| EXEC-03 | | Pending |
| EXEC-04 | | Pending |
| EXEC-05 | | Pending |
| EXEC-06 | | Pending |
| REP-01 | | Pending |
| REP-02 | | Pending |
| REP-03 | | Pending |
| REP-04 | | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 0
- Unmapped: 21 ⚠️

---
*Requirements defined: 2026-04-02*
*Last updated: 2026-04-02 after initial definition*
