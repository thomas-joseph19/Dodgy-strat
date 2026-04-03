# Roadmap

## Phase 1: Data Infrastructure & Basic Pricing Math [COMPLETED]
- **Goal:** Set up the basic project structure, load the 1-min NQ parquet data, and define the foundational `Candle` and instrument configurations.
- **Scope:** Define `Candle`, `InstrumentConfig` (NQ parameters), and `StrategyThresholds`. Data loader for parquet.
- **Success:** Can reliably iterate over the dataset generating `Candle` objects point-by-point.

## Phase 2: Swing Detection & Zero-Bias Engine [COMPLETED]
- **Goal:** Build the strict swing high/low detector and registry that explicitly prevents hindsight bias.
- **Scope:** Implementation of `SwingHigh`, `SwingLow`, `detect_swing_high`, `detect_swing_low`, and the `SwingRegistry` class that caches confirmed swings.
- **Success:** The engine maintains rolling highs/lows correctly delayed by `swing_lookback` candles.

## Phase 3: Liquidity Levels & Sweeps [COMPLETED]
- **Goal:** Track liquidity pools (BSL/SSL) and detect sweeps.
- **Scope:** Combine swings into `LiquidityLevel`s (EQH, EQL, etc.). Build the `detect_sweep` function (verifying extension and recovery).
- **Success:** Accurate detection of sweeps that return a `SweepEvent` and properly invalidate broken levels.

## Phase 4: FVG & IFVG Generation [COMPLETED]
- **Goal:** Model Fair Value Gaps and detect entry-triggering Inverted FVGs.
- **Scope:** Implement `FairValueGap` detector, FVG fusion/stacking (`merge_fvg_series`), and IFVG inversion trigger detection. Connect to the `TradeSetup` generator.
- **Success:** Generator emits properly formatted `TradeSetup` objects with all required entry, stop, and targets mathematically defined.

## Phase 5: Trade Execution Engine & Reporting [COMPLETED]
- **Goal:** Create the setup-by-setup evaluation loop, apply commissions/slippage, size position, and output metrics/Plotly charts.
- **Scope:** The `evaluate_setup` function, dynamic contract sizing algorithm, Sharpe/Sortino calculations, HTML output generation using Plotly, and CSV/Markdown reports.
- **Success:** The entire backtest executes from start to finish, generating `.planning/backtest_results/run_id/` with accurate financial metrics and individual HTML setup charts.

### Phase 6: Institutional Metrics & Portfolio Analysis (Equity Curve, Sharpe, Sortino, CSV Logs) [PENDING]

**Goal:** Provide advanced analysis of multiple runs and ensemble performance.
**Requirements**: TBD
**Depends on:** Phase 5
**Plans:** 0 plans

### Phase 7: Trade Logic Audit & Calculation Verification [COMPLETED]

**Goal:** Mathematically verify and refine the entry, TP, and SL calculations to ensure alignment with the DodgysDD strategy and fix current simulation anomalies.
**Scope:** Review `main.py` entry/exit logic, fix Short RR divide-by-zero, audit drawdown math in `src/metrics.py`, and verify SL placement logic. HTF Level Fix (1h) implementation.
**Success:** Backtest results show realistic drawdown and PnL, with no runtime warnings.
