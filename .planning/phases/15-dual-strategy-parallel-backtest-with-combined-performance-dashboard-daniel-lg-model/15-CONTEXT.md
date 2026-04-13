# Phase 15: Dual-Strategy Parallel Backtest with Combined Performance Dashboard - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Run the Daniel strategy (this repo, Python) and the LG Model (external repo, Node.js) independently
against the same NQ historical data. Merge both trade streams into a single chronological combined
result set. Generate a tabbed HTML dashboard: Combined / Daniel / LG Model.

No changes to either strategy engine's internal logic.

</domain>

<decisions>
## Implementation Decisions

### Integration Approach
- **D-01:** Use `git submodule` to embed `https://github.com/cuzohh/lg-model.git` into this repo
  under `strategies/lg_model/`. This keeps both repos independent and avoids code duplication.
- **D-02:** The LG model runs as a black-box subprocess via `node src/cli/backtest.js` — no Python↔JS bridging required.

### Capital Accounting
- **D-03:** Shared $100,000 starting capital. Both strategies run fully independently (no position
  sizing interaction, no blocking if both fire simultaneously).
- **D-04:** Position sizing: both strategies always take **1 contract** regardless of whether the
  other has an open position. P&L is summed arithmetically — no capital depletion between strategies.
- **D-05:** Combined equity curve = Daniel cumulative P&L + LG cumulative P&L, computed by
  merging both trade lists chronologically and walking forward from $100k shared starting capital.

### Data Format & Conversion
- **D-06:** Daniel reads `data/nq_1min_10y.parquet` (already exists, no changes needed).
- **D-07:** LG Model requires **two semicolon-delimited CSV files**: `1Min_NQ.csv` and `1H_NQ.csv`.
  Format: `Date;Symbol;Open;High;Low;Close;Volume` — timestamps in Chicago timezone.
- **D-08:** A **Python conversion script** (`scripts/convert_parquet_to_lg_csv.py`) will be written
  to export the existing parquet file into the two LG-compatible CSVs (1-minute and 1-hour aggregated).
  These CSVs go into `data/lg_format/` which is gitignored (large files).
- **D-09:** The LG Model's `node_modules` are NOT committed — `npm install` is run as part of setup.

### Orchestration
- **D-10:** A single Python orchestrator script (`run_dual_backtest.py`) handles the full pipeline:
  1. Convert parquet → LG CSVs (if not already done / `--force-convert` flag)
  2. Run Daniel backtest → `daniel_trades.csv`
  3. Run LG backtest via subprocess `node` → `lg_trades.csv`
  4. Normalize both CSVs to a common trade schema
  5. Merge chronologically → compute combined metrics
  6. Generate tabbed dashboard HTML
- **D-11:** Orchestrator CLI accepts `--start` / `--end` date bounds (passed to both engines),
  `--output-dir`, and `--no-convert` to skip the parquet conversion step.

### Trade Schema Normalisation
- **D-12:** Daniel trades CSV columns used: `date`, `direction`, `entry_price`, `exit_price`,
  `exit_type`, `pnl_usd`, `pnl_points` (pnl_usd / 20 for LG parity).
- **D-13:** LG Model trades CSV columns used: `session_date`, `side`, `entry_price`, `exit_category`,
  `pnl_points`, `pnl_usd` (pnl_points × $20/pt).
- **D-14:** Normalised common schema: `date`, `strategy`, `direction`, `entry_price`, `exit_type`,
  `pnl_points`, `pnl_usd`, `source` (`"daniel"` or `"lg"`).

### Dashboard Design
- **D-15:** Tabbed HTML dashboard with **3 tabs**:
  - **Combined** — Merged equity curve from $100k, aggregate metrics (total P&L, Sharpe, Win Rate,
    Max DD, Profit Factor, total trades, Calmar, Expectancy)
  - **Daniel** — Isolated Daniel metrics + equity curve (reuses existing `src/dashboard.py` format)
  - **LG Model** — Isolated LG metrics + equity curve (mirrors LG's own `report.html` KPI set)
- **D-16:** Dashboard is generated in Python (Jinja2-style string templating, Chart.js for curves)
  and auto-opened in browser on completion — consistent with existing Daniel dashboard behaviour.
- **D-17:** Combined equity curve plots Daniel, LG, and Combined lines on the same chart for
  direct visual comparison.

### Agent's Discretion
- Exact HTML/CSS styling of the tabbed dashboard — should be consistent with the premium aesthetic
  of the existing `src/dashboard.py` glassmorphism theme.
- Whether to filter LG trades marked `CLOSED_SCRATCH` or `CLOSED_TIMEOUT` — treat them as closed
  trades that affect equity (consistent with how LG's own metrics.js handles them).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Daniel Strategy Engine
- `main.py` — entry point, `run_backtest()` function, CLI args, trade result schema
- `src/dashboard.py` — existing dashboard generator (reuse styling patterns)
- `src/metrics.py` — `get_performance_summary()` for per-strategy metrics
- `src/execution.py` — `TradeResult` schema

### LG Model Engine (submodule target)
- `src/cli/backtest.js` — the LG backtest CLI, its `--1h`, `--1m`, `--from`, `--to` args
- `src/reporting/metrics.js` — `computeCoreMetrics()`, Sharpe/Sortino calculation, $20/pt
- `src/reporting/trade-csv.js` — `TRADE_CSV_COLUMNS` schema (the normalisation target)
- `package.json` — npm `backtest` script, dependencies (luxon, decimal.js, csv-parse)

### Data
- `data/nq_1min_10y.parquet` — source parquet (Daniel's input, must be converted for LG)
- `data/lg_format/` — output directory for converted LG CSVs (gitignored)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/dashboard.py`: `generate_dashboard()` — produces the Daniel HTML report; the new combined
  dashboard should adopt the same glassmorphism / Chart.js aesthetic
- `src/metrics.py`: `get_performance_summary()` — returns Sharpe, Sortino, Win Rate, Max DD etc.
  Can be called on the normalised combined trade list directly.

### Established Patterns
- Backtest output: Run creates a timestamped folder under `D:\Algorithms\Dodgy Backtest Results\run_{id}/`
  — dual backtest output should follow the same pattern.
- ML data gitignore pattern: `data/` is already gitignored — `data/lg_format/` is covered.

### Integration Points
- `run_dual_backtest.py` is a new top-level script (peer to `main.py`), not a replacement.
- LG submodule lives at `strategies/lg_model/` — its `npm install` and `node` invocations use
  a `cwd` of that directory.
- The combined dashboard is a new file: `src/combined_dashboard.py`.

</code_context>

<specifics>
## Specific Implementation Notes

- LG Model uses **$20/point** (NQ mini), same as Daniel's `SimulationConfig.point_value = 20`.
- LG timestamps are Berlin-session dates (`session_date`); Daniel timestamps are Chicago-local.
  Normalise both to UTC date for merging and equity curve sequencing.
- The LG engine outputs **at most 1 trade per Berlin session day** — very different trade frequency
  from Daniel. This should be visible in the per-strategy tab (trade count will be much lower for LG).
- The parquet → CSV conversion needs to handle Chicago timezone correctly.
  LG's loader (`chicago-to-utc.js`) expects timestamps in format `MM/DD/YYYY HH:MM:SS` or similar
  Chicago-local — the conversion script must match this exactly.

</specifics>

<deferred>
## Deferred Ideas

- BBO-augmented LG Model filtering (separate phase — Phase 14 already covers BBO for Daniel)
- Monte Carlo simulation across both strategies combined (belongs in a later stress-test phase)
- Weighting / allocation optimisation between Daniel and LG (belongs after initial combined results are seen)

</deferred>

---

*Phase: 15-dual-strategy-parallel-backtest-with-combined-performance-dashboard-daniel-lg-model*
*Context gathered: 2026-04-12*
