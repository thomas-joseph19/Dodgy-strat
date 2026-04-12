---
phase: 12
plan: 01
title: Interactive HTML Dashboard Generator
wave: 1
depends_on: []
files_modified:
  - src/dashboard.py
autonomous: true
---

# Plan 01: Interactive HTML Dashboard Generator

<objective>
Create a self-contained HTML dashboard generator module (`src/dashboard.py`) that takes trade results and produces a single interactive HTML file with Chart.js equity curves, live-recalculating stats, session/date filtering, and full trade log. The dashboard uses the exact dark glassmorphic design template provided by the user.
</objective>

<must_haves>
- Self-contained HTML with inline CSS/JS, only external dep is Chart.js CDN
- Dark glassmorphic theme matching provided template (--bg:#0b1220, accent:#5cd6ff, win:#4ade80, loss:#fb7185)
- Interactive controls: contract size, initial equity, slippage, commission, date range, session filter
- Stats grid: Total Trades, Win Rate, Net P&L, Profit Factor, Sharpe, Sortino, Max DD, Avg Trade, Avg R, Calmar, EV, P-value
- Equity curve via Chart.js canvas
- Session comparison table, day-of-week breakdown, calendar-year returns, outcome summary
- Full scrollable trade log table
- All filtering/recalculation happens client-side in JavaScript from embedded JSON data
</must_haves>

## Tasks

<task id="01.1">
<title>Create src/dashboard.py with generate_dashboard function</title>
<read_first>
- src/metrics.py (existing metric calculations to understand data shapes)
- src/execution.py (TradeResult, TradeSetup, Direction dataclasses)
- src/core.py (SimulationConfig defaults, NQ instrument config)
</read_first>
<action>
Create `src/dashboard.py` with a single public function:

```python
def generate_dashboard(
    results: list[TradeResult],
    output_path: str,
    initial_capital: float = 100_000.0,
    title: str = "DodgysDD IFVG Mechanical Backtest"
) -> str:
```

This function must:

1. **Build trade data as JSON-serializable list.** For each TradeResult, extract:
   - `date`: setup.created_at formatted as "YYYY-MM-DD"
   - `time`: setup.created_at formatted as "HH:MM"
   - `setup_id`: setup.setup_id
   - `direction`: setup.direction.value ("long"/"short")  
   - `session`: classify by time (pre_market: <9:30, open_drive: 9:30-12:00, midday: 12:00-14:00, power_hour: 14:00-16:00, overnight: >=16:00)
   - `entry`: setup.entry_price
   - `stop`: setup.stop_price
   - `target`: setup.target_price
   - `exit_price`: result.exit_price
   - `exit_type`: result.exit_type
   - `risk_points`: abs(entry - stop)
   - `pnl_points`: (exit - entry) for LONG, (entry - exit) for SHORT
   - `pnl_raw`: pnl_points * 20.0 (NQ point value)
   - `r_multiple`: pnl_points / risk_points
   - `risk_reward`: setup.risk_reward
   - `reasoning`: setup.reasoning
   - `day_of_week`: 0-6 (Monday-Sunday)
   - `year`: integer year

2. **Embed trade data as `const TRADES = [...];`** in the HTML `<script>` block.

3. **Generate the complete HTML string** using the exact CSS from the user's template (all CSS custom properties, panel styles, card styles, pill toggles, table styles, responsive breakpoints). 

4. **JavaScript engine must implement:**
   - `recalc()` — master function called on any control change
   - Filter trades by date range, session
   - Apply slippage mode (raw vs net): net mode subtracts `slippage * 2 * 20` and `commission` from each trade's PnL
   - Multiply by contract count
   - Calculate all stats: trades count, win rate, net PnL, profit factor (sum wins / abs sum losses), Sharpe (annualized from daily returns), Sortino, max drawdown (peak-to-trough as %), avg trade, avg R, Calmar (annualized return / abs max DD), EV (avg PnL per trade), p-value (one-sample t-test on trade PnL: `t = mean / (std / sqrt(n))`, convert to p-value using approximation)
   - Build equity curve data array for Chart.js (cumulative PnL)
   - Populate session comparison table (per session: trades, win%, USD, profit factor, sharpe, max DD)
   - Populate day-of-week table (per day: trades, win%, points, USD)
   - Populate calendar-year table (per year: trades, P/L USD, return%, end equity)
   - Populate outcome summary table (per exit_type: count, share%)
   - Populate trade log table (all filtered trades with styling: .win/.loss classes)

5. **Chart.js configuration:**
   - Line chart, no fill, line color `#5cd6ff`, point radius 0
   - Dark grid lines using `rgba(42,56,83,0.5)`
   - Responsive, maintain aspect ratio false
   - Tooltip showing date and equity value

6. **Pill toggle behavior:**
   - `.mode-pill` toggles raw/net slippage
   - `.session-pill` filters by session (Portfolio = all, or individual sessions)
   - `.range-pill` sets date range presets (Full, 5Y, 3Y, 1Y, YTD based on last trade date)
   - Portfolio filter checkboxes for including/excluding sessions in composite view
   - All pills use `.active` class toggling

7. **Adapt the session pills from the ORB template:**
   - Replace "ASIA", "LONDON", "NY" with "Portfolio", "Pre-Mkt", "Open Drive", "Midday", "Power Hr", "Overnight"
   - Update CSS color variables for sessions accordingly
   - Portfolio filter checkboxes match the session names

8. **Write the HTML string to `output_path` and return the path.**

The entire dashboard must work offline (once loaded) except for the Chart.js CDN script.
</action>
<acceptance_criteria>
- `src/dashboard.py` exists and contains `def generate_dashboard(`
- Function accepts `results: list`, `output_path: str`, `initial_capital: float`, `title: str`
- Generated HTML contains `<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js"></script>`
- Generated HTML contains `const TRADES =` with embedded JSON trade data
- Generated HTML contains all CSS custom properties: `--bg:#0b1220`, `--surface:#121a2b`, `--accent:#5cd6ff`, `--win:#4ade80`, `--loss:#fb7185`
- Generated HTML contains `id="equityChart"` canvas element
- Generated HTML contains `id="statsGrid"`, `id="sessionTableBody"`, `id="dowTableBody"`, `id="yearTableBody"`, `id="tradeLogBody"`
- Generated HTML contains interactive control inputs: `id="contractsInput"`, `id="equityInput"`, `id="slippageInput"`, `id="commissionInput"`
- Generated HTML contains `function recalc()` JavaScript function
- Generated HTML contains date range controls: `id="fromDateInput"`, `id="toDateInput"`, `id="timeframePreset"`
</acceptance_criteria>
</task>
