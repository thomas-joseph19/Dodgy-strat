# Phase 12: 10-Year Mechanical Backtest with Interactive HTML Dashboard - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Run the existing v1.0 mechanical backtest engine over the full 10-year NQ dataset and produce a self-contained interactive HTML dashboard with CSV trade log. No ML — pure mechanical strategy. The backtest engine itself (`main.py`) is NOT being modified for new strategy logic. This phase adds a dashboard output layer and adapts `main.py` for CLI-driven output path control.

</domain>

<decisions>
## Implementation Decisions

### Output Location
- **D-01:** All output goes to `D:\Algorithms\Dodgy Backtest Results` (not the old `D:\Dodgy Backtest Results`)
- **D-02:** Output folder structure: `D:\Algorithms\Dodgy Backtest Results\run_YYYYMMDD_HHMMSS\` containing `dashboard.html`, `trades.csv`, and `setups/` folder for per-trade Plotly charts

### HTML Dashboard
- **D-03:** Single self-contained HTML file with inline CSS/JS. Only external dep: Chart.js via CDN (`https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js`)
- **D-04:** Dark glassmorphic design matching the provided template — `--bg:#0b1220`, `--surface:#121a2b`, accent `#5cd6ff`, win `#4ade80`, loss `#fb7185`
- **D-05:** Dashboard title: adapt from "NQ ORB Best Modes" to "DodgysDD IFVG Mechanical Backtest" (same layout structure)
- **D-06:** Interactive controls: Contract size, Initial equity ($100k default), RT Slippage ($0.75 default), Commission/contract/RT ($2.40 default), Date range presets, From/To date
- **D-07:** Quick range pills: "Full", "Last 5Y", "Last 3Y", "Last 1Y", "YTD"
- **D-08:** Slippage mode toggle: "Raw Fills" vs "With Slippage"
- **D-09:** Session filter pills: "All Sessions", session breakdown by time-of-day if applicable (pre-market, open drive, midday, power hour, overnight) — adapt from the ORB template's Asia/London/NY to the strategy's session classifications

### Dashboard Sections (in order)
- **D-10:** Stats grid: Total Trades, Win Rate, Net P&L, Profit Factor, Sharpe Ratio, Sortino Ratio, Max Drawdown, Avg Trade, Avg R, Calmar Ratio, EV per Trade, P-value (statistical significance)
- **D-11:** Equity curve chart (Chart.js canvas) on left, Session comparison table on right
- **D-12:** Day-of-week breakdown table on left, Calendar-year returns table on right
- **D-13:** Outcome summary table (TARGET_HIT, HARD_STOP, BREAK_EVEN, EXPIRED counts)
- **D-14:** Full scrollable trade log table: Date, Session, Side, Entry, Stop, Risk, P/L pts, P/L USD, R-multiple, Exit type

### Interactive Filtering
- **D-15:** All stats, charts, and tables must recalculate live in JavaScript when user changes contract size, equity, slippage, commission, date range, or session filter
- **D-16:** All trade data embedded as JSON array in the HTML file — no server needed

### CSV Output
- **D-17:** `trades.csv` with columns: date, setup_id, direction, session, entry_price, stop_price, target_price, risk_points, exit_price, exit_type, pnl_points, pnl_usd, r_multiple, risk_reward, reasoning

### Additional Outputs
- **D-18:** Don't generate per-trade Plotly HTML charts for the 10-year run (too many trades). Skip charts.
- **D-19:** Auto-open the dashboard in the default browser when the backtest completes

### CLI Interface
- **D-20:** User should be able to run the backtest with: `python main.py --data data/nq_1min_10y.parquet --output-root "D:\Algorithms\Dodgy Backtest Results"`
- **D-21:** Support `--start YYYY-MM-DD` and `--end YYYY-MM-DD` for custom date ranges
- **D-22:** Support `--no-charts` flag (already implied for 10yr, but keep as explicit option)

### Agent's Discretion
- Exact JavaScript chart configuration (line thickness, tooltips, hover effects)
- P-value calculation method (bootstrap or analytical)
- Calmar ratio period (use full backtest period)
- Session classification boundaries (use existing `classify_session` logic from the pre-revert codebase or define from NQ trading hours)

</decisions>

<specifics>
## Specific Ideas

- "I want this exact dashboard layout" — user provided complete HTML/CSS template modeled on an ORB strategy dashboard
- The HTML template uses CSS custom properties for theming, glassmorphism panels, pill toggles for mode switching
- Session pills should adapt from Asia/London/NY to the strategy's relevant session types
- Portfolio filter checkboxes for including/excluding sessions in composite view
- Calendar-year return table must track beginning/ending equity per year
- The template's "note" blocks should contain strategy-specific commentary

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Strategy Engine
- `main.py` — Current mechanical backtest engine with evaluate_setup, calculate_net_pnl, run_backtest
- `src/core.py` — Candle dataclass, InstrumentConfig (NQ), StrategyThresholds
- `src/execution.py` — TradeSetup, TradeResult, TradeState, SimulationConfig dataclasses
- `src/metrics.py` — Sharpe, Sortino, max drawdown, get_performance_summary

### Design Reference
- User-provided HTML template (embedded in CONTEXT.md decisions) — exact CSS variables, panel structure, table layouts, pill toggles, chart positioning

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `evaluate_setup()` in `main.py` — fully functional trade evaluation loop
- `calculate_net_pnl()` in `main.py` — handles slippage and commissions
- `get_performance_summary()` in `src/metrics.py` — Sharpe, Sortino, max DD, equity curve
- `SimulationConfig` in `src/execution.py` — configurable slippage, commission, position sizing

### Established Patterns
- Output goes to timestamped `run_YYYYMMDD_HHMMSS/` folders
- TradeResult stores setup, exit time, exit price, exit type, net PnL
- Daily returns aggregated for risk metrics

### Integration Points
- `main.py:run_backtest()` currently writes CSV and Plotly charts — needs to also generate dashboard.html
- `src/metrics.py:get_performance_summary()` returns dict with equity_curve — dashboard needs this plus additional metrics (profit factor, calmar, EV, p-value)
- `main.py.__main__` block has argparse — needs `--output-root` and `--end` flags added

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-10-year-mechanical-backtest-with-interactive-html-dashboard*
*Context gathered: 2026-04-12*
