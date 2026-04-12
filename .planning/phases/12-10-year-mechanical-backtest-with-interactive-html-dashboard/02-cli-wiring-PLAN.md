---
phase: 12
plan: 02
title: CLI Updates and Backtest Wiring
wave: 2
depends_on: [01]
files_modified:
  - main.py
autonomous: true
---

# Plan 02: CLI Updates and Backtest Wiring

<objective>
Update main.py CLI with --output-root and --end flags, wire the dashboard generator into run_backtest(), generate trades.csv, and auto-open the dashboard in the default browser on completion.
</objective>

<must_haves>
- CLI supports: --data, --start, --end, --output-root, --no-charts
- Default output root: D:\Algorithms\Dodgy Backtest Results
- Dashboard auto-opens in default browser after generation
- trades.csv generated with all required columns
- Backtest prints institutional performance summary to console
</must_haves>

## Tasks

<task id="02.1">
<title>Update main.py CLI and run_backtest to output dashboard + CSV</title>
<read_first>
- main.py (current CLI and run_backtest function — the ENTIRE file)
- src/execution.py (TradeResult, TradeSetup, SimulationConfig dataclasses)
- src/metrics.py (get_performance_summary function signature and return dict)
- src/dashboard.py (generate_dashboard function signature — created in Plan 01)
</read_first>
<action>
Modify `main.py` to:

1. **Update argparse:**
   - Add `--end` argument: `parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)", default=None)`
   - Add `--output-root` argument: `parser.add_argument("--output-root", type=str, default=r"D:\Algorithms\Dodgy Backtest Results", help="Root output directory")`
   - Add `--no-charts` argument: `parser.add_argument("--no-charts", action="store_true", help="Skip per-trade Plotly HTML charts")`
   - Update the call to `run_backtest()` to pass all new args

2. **Update `run_backtest()` function signature:**
   ```python
   def run_backtest(data_path: str, start_date=None, end_date=None, output_root=None, save_charts=False):
   ```
   - Add `end_date` parameter — filter `df[df['timestamp'] < end_date]` (exclusive)
   - Change `output_root` default to `r"D:\Algorithms\Dodgy Backtest Results"`
   - Change `save_charts` default to `False` (user explicitly said no charts for 10yr run)

3. **Add end_date filtering:**
   After the existing start_date filter, add:
   ```python
   if end_date:
       df = df[df['timestamp'] < end_date].reset_index(drop=True)
   ```

4. **Update output path:**
   ```python
   output_base = Path(output_root or r"D:\Algorithms\Dodgy Backtest Results") / f"run_{run_id}"
   ```

5. **Generate trades.csv** with these columns (after all_results is populated):
   ```python
   trade_rows = []
   for r in all_results:
       entry = r.setup.entry_price
       stop = r.setup.stop_price
       risk = abs(entry - stop)
       if r.setup.direction == Direction.LONG:
           pnl_pts = r.exit_price - entry
       else:
           pnl_pts = entry - r.exit_price
       
       # Session classification
       hour = r.setup.created_at.hour
       minute = r.setup.created_at.minute
       if hour < 9 or (hour == 9 and minute < 30):
           session = "pre_market"
       elif hour < 12:
           session = "open_drive"
       elif hour < 14:
           session = "midday"
       elif hour < 16:
           session = "power_hour"
       else:
           session = "overnight"
       
       trade_rows.append({
           "date": r.setup.created_at.strftime('%Y-%m-%d'),
           "setup_id": r.setup.setup_id,
           "direction": r.setup.direction.value,
           "session": session,
           "entry_price": entry,
           "stop_price": stop,
           "target_price": r.setup.target_price,
           "risk_points": round(risk, 2),
           "exit_price": r.exit_price,
           "exit_type": r.exit_type,
           "pnl_points": round(pnl_pts, 2),
           "pnl_usd": round(r.net_pnl, 2),
           "r_multiple": round(pnl_pts / risk, 2) if risk > 0 else 0.0,
           "risk_reward": round(r.setup.risk_reward, 2),
           "reasoning": r.setup.reasoning
       })
   
   output_base.mkdir(exist_ok=True, parents=True)
   pd.DataFrame(trade_rows).to_csv(output_base / "trades.csv", index=False)
   ```

6. **Generate HTML dashboard:**
   ```python
   from src.dashboard import generate_dashboard
   dashboard_path = generate_dashboard(
       results=all_results,
       output_path=str(output_base / "dashboard.html"),
       initial_capital=100_000.0,
       title="DodgysDD IFVG Mechanical Backtest"
   )
   ```

7. **Auto-open in browser:**
   ```python
   import webbrowser
   webbrowser.open(f"file:///{dashboard_path.replace(os.sep, '/')}")
   ```

8. **Keep the existing console summary output** (the INSTITUTIONAL PERFORMANCE REPORT block).

9. **Fix the missing `List` import** — the current main.py uses `List[datetime]` but doesn't import it. Add: `from typing import List`

10. **Update the `__main__` block:**
    ```python
    if __name__ == "__main__":
        import argparse
        parser = argparse.ArgumentParser(description="DodgysDD Backtest Engine")
        parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)", default=None)
        parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)", default=None)
        parser.add_argument("--data", type=str, help="Path to parquet data", default="data/nq_1min_10y.parquet")
        parser.add_argument("--output-root", type=str, default=r"D:\Algorithms\Dodgy Backtest Results")
        parser.add_argument("--no-charts", action="store_true", help="Skip per-trade Plotly charts")
        
        args = parser.parse_args()
        run_backtest(
            args.data,
            start_date=args.start,
            end_date=args.end,
            output_root=args.output_root,
            save_charts=not args.no_charts
        )
    ```
</action>
<acceptance_criteria>
- `main.py` contains `parser.add_argument("--end"`
- `main.py` contains `parser.add_argument("--output-root"`
- `main.py` contains `parser.add_argument("--no-charts"`
- `main.py` contains `from src.dashboard import generate_dashboard`
- `main.py` contains `"D:\\Algorithms\\Dodgy Backtest Results"` as default output root
- `main.py` contains `.to_csv(` for trades.csv generation
- `main.py` contains `webbrowser.open(` for auto-opening dashboard
- `main.py` contains `from typing import List`
- `main.py` run_backtest function accepts `end_date` parameter
- Running `python main.py --help` shows --start, --end, --data, --output-root, --no-charts options
</acceptance_criteria>
</task>
