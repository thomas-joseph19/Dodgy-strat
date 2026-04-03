# Phase 5: Reports & Visuals - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Ingesting completed `TradeResult` logs and `AccountState` history to compute institutional-grade backtesting metrics, construct HTML plotting artifacts for granular performance debugging, and serialize all runs explicitly to `.planning/backtest_results/`.

</domain>

<decisions>
## Implementation Decisions

### 1. Plotting Architecture
- **D-01 Interactive Plotting:** Plotly HTML explicitly enforced. Allows deep zooming, specific hover tooltips (OHLC), and toggleable traces exactly per setup.
- **D-02 Chart Visual Envelope:** Charts dynamically slice the overarching OHLC dataframe spanning exactly 50 bars prior to the sweep logic genesis and 20 bars trailing the defined exit string, keeping liquidity pool analysis visible.
- **D-03 Trace Constraints:** Shaded gap boundaries, marker entry points, horizontal fail stop lines, and discrete metadata annotations strictly implemented mimicking standard institutional charting. Color standards locked (red/green fading, gold sweeps).

### 2. Metrics & Math
- **D-04 Returns Math:** `4.5%` annual RFR hardcoded logic mapped backward natively simulating rolling daily return math per explicitly closed account balances BOD.
- **D-05 Institutional Stats:** Calculating Sharpe (annualized vs RFR), Sortino (penalizing explicitly downside returns), and Calmar ratios. Win/Loss metrics subdivided heavily across mechanical signal grading variants and reversal mapping.

### 3. File System
- **D-06 Folder Hierarchy:** Backtests natively bypass console vomiting and exclusively write to the localized `.planning/backtest_results/[run_id]/` tree natively carrying teardown Markdown files, CSVs with 30-bound variables, simplistic preview curves utilizing static `matplotlib` alongside the heavily interactive Plotly versions.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definitions
- `.planning/PROJECT.md` — Core mechanization constraints.
- `.planning/REQUIREMENTS.md` — Focus on REP-01 through REP-04 requirements.
- `.planning/phases/05-reports-visuals/DISCUSSION-LOG.md` — Defines exact dicts and file architectures.
</canonical_refs>
