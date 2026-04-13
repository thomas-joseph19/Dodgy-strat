---
phase: 15
plan_id: "04"
title: "Combined Three-Tab HTML Dashboard"
wave: 2
depends_on: ["01", "02"]
autonomous: true
files_modified:
  - src/combined_dashboard.py
---

# Plan 04: Combined Three-Tab HTML Dashboard

## Objective
Create `src/combined_dashboard.py` which generates a single self-contained HTML file with three tabs (Combined / Daniel / LG Model), each showing an equity curve and KPI grid. Uses the same glassmorphism dark aesthetic as the existing `src/dashboard.py`.

## Tasks

<task id="1" title="Create src/combined_dashboard.py">
<read_first>
- src/dashboard.py — Read the full file to extract the CSS variables, font, color palette, card styles, panel styles, and Chart.js CDN version in use (`chart.js@4.4.6`). Use identical dark background (`#0b1220`), surface (`#121a2b`, `#172134`), border (`#2a3853`), text (`#e8eefc`), muted (`#8ea0c4`), and accent (`#5cd6ff`) variables. Reuse the `.panel`, `.card`, `.stats`, `.wrap` patterns exactly.
</read_first>

<action>
Create `src/combined_dashboard.py` with the following implementation.

This module generates a single self-contained HTML file embedding three tabs:
  - Combined: 3-line equity chart + aggregate KPI metrics
  - Daniel: single equity line + KPI metrics for Daniel only
  - LG Model: single equity line + KPI metrics for LG only

```python
"""
Combined three-tab HTML dashboard for dual-strategy backtest.

Produces a single self-contained HTML file with:
  - Combined tab: merged equity curve (Combined+Daniel+LG), aggregate KPIs
  - Daniel tab: isolated Daniel equity curve + KPIs
  - LG Model tab: isolated LG equity curve + KPIs

Style is consistent with src/dashboard.py (same Chart.js CDN, same CSS variables,
same glassmorphism dark theme).
"""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime


def _fmt_usd(val: float) -> str:
    sign = "+" if val >= 0 else ""
    return f"{sign}${val:,.2f}"


def _fmt_pct(val: float) -> str:
    return f"{val * 100:.1f}%"


def _build_kpi_cards(summary: dict) -> str:
    """Build KPI card HTML from a metrics summary dict."""
    total_pnl = summary.get("total_pnl", 0.0)
    total_trades = summary.get("total_trades", 0)
    win_rate = summary.get("win_rate", 0.0)
    profit_factor = summary.get("profit_factor", 0.0)
    expectancy = summary.get("expectancy", 0.0)
    sharpe = summary.get("sharpe", None)
    sortino = summary.get("sortino", None)
    max_dd_pct = summary.get("max_dd_pct", 0.0)
    max_dd_usd = summary.get("max_dd_usd", 0.0)
    calmar = summary.get("calmar", 0.0)
    avg_win = summary.get("avg_win_usd", 0.0)
    avg_loss = summary.get("avg_loss_usd", 0.0)

    pnl_color = "var(--win)" if total_pnl >= 0 else "var(--loss)"
    win_color = "var(--win)" if win_rate >= 0.5 else "var(--loss)"
    sharpe_str = f"{sharpe:.2f}" if sharpe is not None else "—"
    sortino_str = f"{sortino:.2f}" if sortino is not None else "—"
    sharpe_color = "var(--win)" if (sharpe or 0) >= 1 else "var(--muted)"

    cards = [
        ("Total P&L", _fmt_usd(total_pnl), "", pnl_color),
        ("Total Trades", str(total_trades), "", "var(--text)"),
        ("Win Rate", _fmt_pct(win_rate), "", win_color),
        ("Profit Factor", f"{profit_factor:.2f}", "Gross Win / Gross Loss", "var(--text)"),
        ("Expectancy", _fmt_usd(expectancy), "Per trade", "var(--text)"),
        ("Sharpe Ratio", sharpe_str, "Annualised", sharpe_color),
        ("Sortino Ratio", sortino_str, "Annualised", "var(--text)"),
        ("Max Drawdown", _fmt_pct(max_dd_pct), _fmt_usd(-abs(max_dd_usd)), "var(--loss)"),
        ("Avg Win", _fmt_usd(avg_win), "", "var(--win)"),
        ("Avg Loss", _fmt_usd(-abs(avg_loss)), "", "var(--loss)"),
    ]
    html_parts = []
    for label, value, subvalue, color in cards:
        sub_html = f'<div class="subvalue">{subvalue}</div>' if subvalue else ""
        html_parts.append(
            f'<div class="card">'
            f'<div class="label">{label}</div>'
            f'<div class="value" style="color:{color}">{value}</div>'
            f'{sub_html}'
            f'</div>'
        )
    return "\n".join(html_parts)


def generate_combined_dashboard(
    daniel_trades: list,
    lg_trades: list,
    equity_curves: dict,
    output_path: str | Path,
    daniel_summary: dict,
    lg_summary: dict,
    combined_summary: dict,
    title: str = "Dual-Strategy Backtest: Daniel + LG Model",
) -> str:
    """
    Generate the combined tabbed HTML dashboard.

    Args:
        daniel_trades: Normalised Daniel trade list (from trade_merger)
        lg_trades: Normalised LG trade list (from trade_merger)
        equity_curves: Output of build_equity_curves() — keys: combined, daniel, lg
        output_path: Where to write the HTML file
        daniel_summary: Metrics dict from get_performance_summary() for Daniel
        lg_summary: Metrics dict from get_performance_summary() for LG
        combined_summary: Metrics dict from compute_combined_summary()
        title: Dashboard title string

    Returns:
        Absolute path to the written HTML file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build equity curve data for Chart.js
    def _curves_to_chartjs(curves):
        return {
            "labels": [p["date"] for p in curves],
            "data": [p["equity"] for p in curves],
        }

    combined_chartjs = _curves_to_chartjs(equity_curves.get("combined", []))
    daniel_chartjs = _curves_to_chartjs(equity_curves.get("daniel", []))
    lg_chartjs = _curves_to_chartjs(equity_curves.get("lg", []))

    # Interleaved combined chart needs all three datasets on one chart
    # We use the combined curve dates as the x-axis and join the others
    combined_dates_json = json.dumps(combined_chartjs["labels"])
    combined_data_json = json.dumps(combined_chartjs["data"])
    daniel_data_json = json.dumps(daniel_chartjs["data"])
    daniel_labels_json = json.dumps(daniel_chartjs["labels"])
    lg_data_json = json.dumps(lg_chartjs["data"])
    lg_labels_json = json.dumps(lg_chartjs["labels"])

    # KPI cards HTML per tab
    combined_cards = _build_kpi_cards(combined_summary)
    daniel_cards = _build_kpi_cards(daniel_summary)
    lg_cards = _build_kpi_cards(lg_summary)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js"></script>
<style>
  :root{{
    --bg:#0b1220;--surface:#121a2b;--surface2:#172134;--border:#2a3853;
    --text:#e8eefc;--muted:#8ea0c4;--accent:#5cd6ff;
    --win:#4ade80;--loss:#fb7185;
    --daniel:#4fc3f7;--lg:#81c784;--combined:#ffffff;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:radial-gradient(circle at top,#15213b 0%,#0b1220 55%);color:var(--text);font:14px/1.5 "Segoe UI",system-ui,sans-serif;min-height:100vh}}
  .wrap{{max-width:1400px;margin:0 auto;padding:28px 20px}}
  h1{{font-size:28px;font-weight:800;letter-spacing:-0.02em;margin-bottom:6px}}
  .subtitle{{color:var(--muted);font-size:13px;margin-bottom:24px}}
  .panel{{background:rgba(18,26,43,.94);border:1px solid var(--border);border-radius:18px;padding:20px;margin-bottom:18px;box-shadow:0 20px 45px rgba(0,0,0,.18)}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:4px}}
  .card{{background:var(--surface2);border:1px solid var(--border);border-radius:14px;padding:14px;transition:transform .12s}}
  .card:hover{{transform:translateY(-2px)}}
  .label{{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}}
  .value{{font-size:20px;font-weight:800;line-height:1.1}}
  .subvalue{{color:var(--muted);font-size:11px;margin-top:4px}}
  .chart-wrap{{height:380px;position:relative}}
  /* Tabs */
  .tab-bar{{display:flex;gap:4px;margin-bottom:20px;background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:6px}}
  .tab-btn{{flex:1;padding:10px 16px;border:none;background:transparent;color:var(--muted);font-weight:700;font-size:13px;border-radius:10px;cursor:pointer;transition:all .15s;letter-spacing:.04em}}
  .tab-btn:hover{{color:var(--text);background:var(--surface2)}}
  .tab-btn.active{{background:var(--accent);color:#07111f}}
  .tab-btn[data-tab="daniel"].active{{background:var(--daniel);color:#07111f}}
  .tab-btn[data-tab="lg"].active{{background:var(--lg);color:#0f1a0f}}
  .tab-panel{{display:none}}
  .tab-panel.active{{display:block}}
  /* Legend dots */
  .legend{{display:flex;gap:16px;margin-bottom:12px;font-size:12px;color:var(--muted)}}
  .dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px}}
  .note{{color:var(--muted);font-size:12px}}
  @media(max-width:700px){{.chart-wrap{{height:260px}}}}
</style>
</head>
<body>
<div class="wrap">
  <h1>⚡ {title}</h1>
  <div class="subtitle">Generated {generated_at} · Daniel (IFVG breakout) + LG Model (Berlin session IFVG) · $100k shared capital · 1 contract each · $20/pt NQ</div>

  <!-- Tab Bar -->
  <div class="tab-bar">
    <button class="tab-btn active" data-tab="combined" onclick="switchTab('combined',this)">🔗 Combined</button>
    <button class="tab-btn" data-tab="daniel" onclick="switchTab('daniel',this)">📈 Daniel</button>
    <button class="tab-btn" data-tab="lg" onclick="switchTab('lg',this)">🌍 LG Model</button>
  </div>

  <!-- Combined Tab -->
  <div id="tab-combined" class="tab-panel active">
    <div class="panel">
      <div class="legend">
        <span><span class="dot" style="background:var(--combined)"></span>Combined Portfolio</span>
        <span><span class="dot" style="background:var(--daniel)"></span>Daniel</span>
        <span><span class="dot" style="background:var(--lg)"></span>LG Model</span>
      </div>
      <div class="chart-wrap"><canvas id="chart-combined"></canvas></div>
    </div>
    <div class="panel">
      <div class="label" style="margin-bottom:14px">Combined Portfolio Metrics</div>
      <div class="stats">{combined_cards}</div>
    </div>
  </div>

  <!-- Daniel Tab -->
  <div id="tab-daniel" class="tab-panel">
    <div class="panel">
      <div class="legend">
        <span><span class="dot" style="background:var(--daniel)"></span>Daniel — IFVG Breakout Strategy</span>
      </div>
      <div class="chart-wrap"><canvas id="chart-daniel"></canvas></div>
    </div>
    <div class="panel">
      <div class="label" style="margin-bottom:14px">Daniel Strategy Metrics</div>
      <div class="stats">{daniel_cards}</div>
    </div>
  </div>

  <!-- LG Model Tab -->
  <div id="tab-lg" class="tab-panel">
    <div class="panel">
      <div class="legend">
        <span><span class="dot" style="background:var(--lg)"></span>LG Model — Berlin Session IFVG</span>
      </div>
      <div class="chart-wrap"><canvas id="chart-lg"></canvas></div>
    </div>
    <div class="panel">
      <div class="label" style="margin-bottom:14px">LG Model Metrics</div>
      <div class="stats">{lg_cards}</div>
    </div>
  </div>

</div>

<script>
// ── Tab switching ──────────────────────────────────────────
const chartInstances = {{}};

function switchTab(name, btn) {{
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
  // Resize chart after tab becomes visible (Chart.js issue: hidden canvases render at 0x0)
  if (chartInstances[name]) {{
    setTimeout(() => chartInstances[name].resize(), 10);
  }}
}}

// ── Chart factory ──────────────────────────────────────────
function makeChart(canvasId, datasets, labels) {{
  const ctx = document.getElementById(canvasId).getContext('2d');
  return new Chart(ctx, {{
    type: 'line',
    data: {{ labels, datasets }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      animation: {{ duration: 400 }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          mode: 'index', intersect: false,
          backgroundColor: '#172134', titleColor: '#e8eefc',
          bodyColor: '#8ea0c4', borderColor: '#2a3853', borderWidth: 1,
          callbacks: {{ label: ctx => ' $' + ctx.parsed.y.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}}) }}
        }}
      }},
      scales: {{
        x: {{ display: true, grid: {{ color: 'rgba(42,56,83,.25)' }}, ticks: {{ color: '#8ea0c4', maxTicksLimit: 14, font: {{ size: 10 }} }} }},
        y: {{ display: true, grid: {{ color: 'rgba(42,56,83,.25)' }}, ticks: {{ color: '#8ea0c4', callback: v => '$' + v.toLocaleString() }} }}
      }}
    }}
  }});
}}

// ── Data ──────────────────────────────────────────────────
const COMBINED_LABELS = {combined_dates_json};
const COMBINED_DATA   = {combined_data_json};
const DANIEL_LABELS   = {daniel_labels_json};
const DANIEL_DATA     = {daniel_data_json};
const LG_LABELS       = {lg_labels_json};
const LG_DATA         = {lg_data_json};

// Combined chart — 3 datasets
chartInstances['combined'] = makeChart('chart-combined', [
  {{
    label: 'Combined', data: COMBINED_DATA,
    borderColor: 'rgba(255,255,255,0.9)', backgroundColor: 'rgba(255,255,255,0.04)',
    fill: true, borderWidth: 2, pointRadius: 0, tension: 0.2
  }},
  {{
    label: 'Daniel', data: DANIEL_DATA.length ? DANIEL_DATA : [],
    borderColor: '#4fc3f7', backgroundColor: 'transparent',
    fill: false, borderWidth: 1.5, pointRadius: 0, tension: 0.2,
    borderDash: []
  }},
  {{
    label: 'LG Model', data: LG_DATA.length ? LG_DATA : [],
    borderColor: '#81c784', backgroundColor: 'transparent',
    fill: false, borderWidth: 1.5, pointRadius: 0, tension: 0.2
  }}
], COMBINED_LABELS);

// Daniel chart
chartInstances['daniel'] = makeChart('chart-daniel', [
  {{
    label: 'Daniel', data: DANIEL_DATA,
    borderColor: '#4fc3f7', backgroundColor: 'rgba(79,195,247,0.07)',
    fill: true, borderWidth: 2, pointRadius: 0, tension: 0.2
  }}
], DANIEL_LABELS);

// LG chart
chartInstances['lg'] = makeChart('chart-lg', [
  {{
    label: 'LG Model', data: LG_DATA,
    borderColor: '#81c784', backgroundColor: 'rgba(129,199,132,0.07)',
    fill: true, borderWidth: 2, pointRadius: 0, tension: 0.2
  }}
], LG_LABELS);
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return str(output_path.resolve())
```
</action>

<acceptance_criteria>
- `src/combined_dashboard.py` exists
- File contains `def generate_combined_dashboard(`
- File contains `def _build_kpi_cards(`
- File contains `switchTab` function in JS string
- File contains `chart.js@4.4.6` CDN reference
- File contains `tab-combined`, `tab-daniel`, `tab-lg` IDs
- File contains CSS variables `--daniel`, `--lg`, `--combined`
- Module imports without error: `python -c "from src.combined_dashboard import generate_combined_dashboard; print('OK')"`
</acceptance_criteria>
</task>

## Verification
Run: `python -c "from src.combined_dashboard import generate_combined_dashboard; print('Module OK')"`

## must_haves
- Three tabs: Combined / Daniel / LG Model
- Chart resize on tab switch (`.resize()` call after `setTimeout`)
- Combined tab shows three lines: combined (white), Daniel (blue), LG (green)
- KPI grid with Total P&L, Win Rate, Profit Factor, Sharpe, Sortino, Max DD, Expectancy, Avg Win, Avg Loss
- Consistent dark glassmorphism styling matching existing `src/dashboard.py`
- Self-contained HTML (no external dependencies except Chart.js CDN)
