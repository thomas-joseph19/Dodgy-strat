---
phase: 5
wave: 1
depends_on: []
files_modified:
  - "src/reporting/metrics.py"
autonomous: true
requirements_addressed:
  - "REP-02"
---

# Phase 5: Reports & Visuals - Wave 1

<objective>
To establish the core institutional math calculations simulating daily index returns for rigorous Sharpe and Sortino analyses.
</objective>

<must_haves>
- Define `BacktestMetrics` dataclass mirroring structure requested in context.
- Implement strictly annualized (`252` days) Sharpe and Sortino ratios measuring against `4.5%` hardcoded Risk-Free-Rate over daily net percentage changes in equity BOD.
</must_haves>

<tasks>

<task>
<description>Create Metrics Computation Engine</description>
<action>
Create directory `src/reporting/` and file `src/reporting/metrics.py`. Define `BacktestMetrics` dataclass (tracking volume, win/loss, P&L, drawdown, risk-adjusted ratios, and signal grade breakdowns). Implement `calculate_metrics(trade_results, account, config)` function that:
1. Calculates raw counting stats.
2. Formats P&L arrays into daily summation series indexed historically.
3. Derives `daily_returns` divided by cumulative start-of-day balances.
4. Uses numpy standard deviation arrays to process Sharpe/Sortino logic mapped accurately.
</action>
<read_first>
- .planning/phases/05-reports-visuals/DISCUSSION-LOG.md
- src/simulator_models.py
</read_first>
<acceptance_criteria>
- File syntax passes.
- Metrics accurately calculate 252-day multiples.
- Returns comprehensive math metrics without plotting overhead.
</acceptance_criteria>
</task>

</tasks>

## Verification
- Code passes syntax check.
