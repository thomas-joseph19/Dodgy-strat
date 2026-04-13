# Phase 15 Research: Dual-Strategy Parallel Backtest

*Researched: 2026-04-12 via direct code inspection of lg-model and dodgy-strat repos.*

---

## Standard Stack

- **Python 3.10+** — Orchestrator (`run_dual_backtest.py`), parquet conversion, trade merging, dashboard generation
- **pandas + pyarrow** — Parquet read, 1H resampling, 1min export to CSV
- **Node.js 18+** — LG Model engine (called as subprocess)
- **subprocess (stdlib)** — Python → Node.js invocation
- **Chart.js (CDN)** — Dashboard equity curves and charts (already used in existing `src/dashboard.py`)
- **git submodule** — Embed `https://github.com/cuzohh/lg-model.git` at `strategies/lg_model/`

---

## Architecture Patterns

```
run_dual_backtest.py          ← Top-level orchestrator
  ├── convert_parquet.py      ← (or inline) parquet → LG semicolon CSVs
  ├── main.py run_backtest()  ← Calls existing Daniel engine in-process
  ├── subprocess: node        ← Calls LG engine, captures trades.csv
  ├── merge_trades()          ← Normalise + merge both trade lists
  └── combined_dashboard.py   ← Generates 3-tab HTML dashboard
```

The orchestrator does NOT modify either engine. It runs them as black boxes and post-processes outputs.

---

## LG CSV Format (CRITICAL)

From direct inspection of `src/data/load-csv-bars.js` and `src/time/chicago-to-utc.js`:

**1-minute CSV** (`1Min_NQ.csv`):
- Header on line 1 (no preamble line)
- Delimiter: `;`
- Columns: `Date;Symbol;Open;High;Low;Close;Volume`
- Timestamp format: Chicago local time (`America/Chicago`), parsed by `parseSourceTimestampToUtc()`
- Expected format example: `01/02/2020 18:01:00` (MM/DD/YYYY HH:MM:SS)

**1-hour CSV** (`1H_NQ.csv`):
- Header on line 2 (line 1 is a metadata preamble — `from_line: 2` in parser)
- Same delimiter and column spec as 1-minute
- Same Chicago timezone

**Conversion approach** from `data/nq_1min_10y.parquet`:
```python
import pandas as pd

df = pd.read_parquet("data/nq_1min_10y.parquet")
df["timestamp"] = pd.to_datetime(df["timestamp"])
# parquet timestamps are UTC — convert to Chicago
df_chi = df.set_index("timestamp").tz_localize("UTC").tz_convert("America/Chicago")

# 1-minute output
df_1m = df_chi.copy().reset_index()
df_1m["Date"] = df_1m["timestamp"].dt.strftime("%m/%d/%Y %H:%M:%S")
df_1m["Symbol"] = "NQ_CONT"
df_1m[["Date","Symbol","Open","High","Low","Close","Volume"]].to_csv(
    "data/lg_format/1Min_NQ.csv", sep=";", index=False
)

# 1-hour output — NOTE: line 1 must be preamble for LG's load1HBars()
df_1h = df_chi.resample("1h").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
df_1h = df_1h.reset_index()
df_1h["Date"] = df_1h["timestamp"].dt.strftime("%m/%d/%Y %H:%M:%S")
df_1h["Symbol"] = "NQ_CONT"
with open("data/lg_format/1H_NQ.csv", "w") as f:
    f.write("Time Series (NQ 1H)\n")  # preamble line required by load1HBars
    df_1h[["Date","Symbol","Open","High","Low","Close","Volume"]].to_csv(f, sep=";", index=False)
```

**Volume**: The parquet may not have a volume column. If missing, fill with `0` — LG's `parseVolume` handles empty/zero gracefully.

---

## Subprocess Pattern

```python
import subprocess
import sys
from pathlib import Path

def run_lg_backtest(submodule_dir: Path, m1_path: Path, h1_path: Path,
                    out_dir: Path, from_date: str = None, to_date: str = None) -> Path:
    """Run LG Model backtest via Node.js subprocess. Returns path to trades.csv."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # Ensure dependencies installed
    node_modules = submodule_dir / "node_modules"
    if not node_modules.exists():
        print("Installing LG Model dependencies...")
        subprocess.run(["npm", "install"], cwd=submodule_dir, check=True)

    cmd = [
        "node", "src/cli/backtest.js",
        "--1m", str(m1_path.resolve()),
        "--1h", str(h1_path.resolve()),
        "--out-dir", str(out_dir.resolve()),
        "--no-progress",   # suppress progress bars in subprocess
        "--no-html",       # we generate our own dashboard
    ]
    if from_date:
        cmd += ["--from", from_date]
    if to_date:
        cmd += ["--to", to_date]

    result = subprocess.run(cmd, cwd=submodule_dir, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"LG backtest failed:\n{result.stderr}")

    trades_path = out_dir / "trades.csv"
    if not trades_path.exists():
        raise FileNotFoundError(f"LG backtest produced no trades.csv in {out_dir}")
    return trades_path
```

**Windows note**: Use `npm.cmd` instead of `npm` on Windows if subprocess can't find it:
```python
npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
```

---

## Trade Schema Normalisation

### Daniel output columns (from `main.py` `trade_rows`):
`date, setup_id, direction, session, entry_price, stop_price, target_price, risk_points, exit_price, exit_type, pnl_points, pnl_usd, r_multiple, risk_reward, reasoning`

### LG output columns (from `src/reporting/trade-csv.js`):
`session_date, side, entry_time_utc, exit_time_utc, entry_price, initial_stop, final_stop, tp1, tp2, exit_category, pnl_points, pnl_usd, max_favorable_excursion_points, time_to_be_bars`

### Normalised common schema:
```python
# For each trade from either engine:
{
    "date": str,           # YYYY-MM-DD (Chicago local for Daniel, Berlin date for LG)
    "exit_time": str,      # ISO UTC string for sorting (Daniel: derive from date; LG: entry_time_utc)
    "strategy": str,       # "daniel" or "lg"
    "direction": str,      # "LONG"/"SHORT" (Daniel) or "long"/"short" (LG side)
    "entry_price": float,
    "exit_type": str,      # Daniel: exit_type; LG: exit_category
    "pnl_points": float,
    "pnl_usd": float,      # Daniel: pnl_usd; LG: pnl_points * 20
}
```

**Key mapping:**
- `pnl_usd` (LG) = `pnl_points * 20` (LG uses `dollarsPerPoint=20`)  
- Daniel `pnl_usd` already includes commission deductions, LG does not deduct commission

---

## Combined Equity Curve

```python
def build_combined_equity(daniel_trades, lg_trades, initial_capital=100_000.0):
    """Walk forward combined equity from both trade streams."""
    # Tag and merge
    for t in daniel_trades:
        t["strategy"] = "daniel"
    for t in lg_trades:
        t["strategy"] = "lg"

    all_trades = sorted(daniel_trades + lg_trades, key=lambda t: t["date"])

    equity = initial_capital
    daniel_equity = initial_capital
    lg_equity = initial_capital
    equity_curve = []

    for t in all_trades:
        pnl = t["pnl_usd"]
        if t["strategy"] == "daniel":
            daniel_equity += pnl
        else:
            lg_equity += pnl
        combined = daniel_equity + lg_equity - initial_capital  # avoid double-counting starting capital
        equity_curve.append({
            "date": t["date"],
            "combined": combined,
            "daniel": daniel_equity,
            "lg": lg_equity,
            "strategy": t["strategy"],
            "pnl_usd": pnl
        })

    return equity_curve
```

**Note on combined equity formula:**
- Daniel starts at $100k, LG starts at $100k — but the *combined* portfolio starts at $100k
- `combined_equity = initial_capital + sum(all pnl_usd)` — do NOT sum both starting capitals
- Equivalently: `combined = daniel_equity + lg_equity - initial_capital`

---

## Dashboard Pattern

The existing `src/dashboard.py` uses inline HTML string generation with Chart.js from CDN. Extend this pattern — do NOT introduce Jinja2 or other templating engines.

**Tab structure:**
```html
<div class="tab-nav">
  <button class="tab-btn active" onclick="switchTab('combined')">Combined</button>
  <button class="tab-btn" onclick="switchTab('daniel')">Daniel</button>
  <button class="tab-btn" onclick="switchTab('lg')">LG Model</button>
</div>
<div id="tab-combined" class="tab-panel active">...</div>
<div id="tab-daniel" class="tab-panel">...</div>
<div id="tab-lg" class="tab-panel">...</div>

<script>
function switchTab(name) {
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
  // Resize charts after tab switch (Chart.js needs this)
  if (window['chart_' + name]) window['chart_' + name].resize();
}
</script>
```

**Combined tab chart:** Three datasets on one Chart.js line chart — Combined (white/bright), Daniel (blue), LG (green). Use `fill: false`, tension 0.1.

---

## Don't Hand-Roll

- **Timezone conversion**: Use `pandas` `tz_localize` / `tz_convert` — do NOT manually offset hours
- **CSV parsing**: Use `pandas.read_csv` with `sep=";"` — do NOT parse LG CSV manually
- **npm detection on Windows**: Use `shutil.which("npm") or "npm.cmd"` — do NOT hardcode path
- **Metrics calculation**: Reuse `src/metrics.py::get_performance_summary()` for both strategies and combined — do NOT rewrite Sharpe/Sortino/drawdown
- **Chart.js**: Pull from CDN (`https://cdn.jsdelivr.net/npm/chart.js`) — already the established pattern

---

## Common Pitfalls

1. **LG 1H preamble line**: `load1HBars` skips line 1 (`from_line: 2`). If the CSV has no preamble, ALL data rows are silently shifted and the first bar is dropped. Always write a dummy preamble line.

2. **Volume column missing**: The existing parquet `data/nq_1min_10y.parquet` may not have a `volume` column. Check — if absent, add `df["Volume"] = 0`. LG's parser won't error on zero volume.

3. **LG outputs at most 1 trade/day per Berlin session**: Date range must be specified identically for both engines. Berlin session days ≠ US trading days. LG will quietly skip weekends and non-trading days.

4. **Windows subprocess**: `node` must be in PATH. On Windows, `npm install` must use `npm.cmd`. Always pass `shell=False` and full paths.

5. **Date alignment for sorting**: LG uses `session_date` (Berlin calendar date, YYYY-MM-DD). Daniel uses `date` (Chicago calendar date). They can differ by 1 day around midnight transitions. Use `exit_time_utc` (LG) and derive UTC exit time for Daniel to sort correctly.

6. **Chart.js resize after tab switch**: Charts in hidden divs have zero width. Call `.resize()` on the Chart instance when a tab becomes visible or the canvas will render at 0×0.

7. **git submodule init**: After adding the submodule, users need `git submodule update --init --recursive`. Add this to the setup instructions / README.

---

## Data Concerns

- **Parquet timestamps**: Confirm whether `nq_1min_10y.parquet` timestamps are UTC or Chicago-local. Check with `pd.read_parquet(...).dtypes` — if `datetime64[ns, UTC]` they are UTC-aware; if `datetime64[ns]` they are naive (likely Chicago). Handle both cases.
- **Date range parity**: When user specifies `--start 2020-01-01 --end 2024-12-31`, pass the same dates to both engines. LG uses `--from`/`--to` (Berlin calendar); Daniel uses `start_date`/`end_date` (Chicago). These are equivalent for most dates but edge-case around DST transitions.
- **LG model data file size**: Converting the full 10-year parquet to semicolon CSV will produce large files (~500MB for 1min, ~30MB for 1H). These go in `data/lg_format/` which is gitignored.
