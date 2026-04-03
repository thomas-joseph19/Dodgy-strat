# Phase 5: Reports & Visuals - Discussion Log

**Date:** 2026-04-02
**Phase:** Phase 5: Reports & Visuals

## Q1: Plotting Library
**User selection:**
- Plotly HTML. Static images fail for visual debugging tick-level 1M overlaps.
- Enforce strict layer rendering maps (e.g. Sweep Markers, FVGs, Triggers) alongside strict color mappings ("#26a69a" for bullish, "#ef5350" for bearish, deep transparency shaded logic).

## Q2: Chart Context Bounds
**User selection:** 
- `bars_before_sweep`: 50 bars. Extensively covers large EQH or LTF structure setups ensuring context is visible naturally.
- `bars_after_exit`: 20 bars. Validates subsequent retraces trailing simulated logic natively without clogging screens.

## Q3: Metrics Math Boundaries
**User selection:**
- Yes to strict Institutional metrics. Focus heavily on Sharpe and Sortino ratios mathematically indexed to specific BOD equity updates daily avoiding P&L scalar issues. Assume 4.5% RFR standard.

## Q4: Output Architecture
**User selection:**
- Backtest engine silences major system dumps structurally routing output natively into `.planning/backtest_results/[run_id]/`.
- Required layout: `metrics.md`, `trade_log.csv` (heavily robust array matching 30 standard metric values), `.png` & `.html` overarching equity traces alongside localized folder mapped `setups/` containing granular HTML evaluations explicitly named per setup ID.
