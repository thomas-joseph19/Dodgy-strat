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
    mc_summary: dict | None = None,
    trade_pnls: list | None = None,
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

    # JSON trades for JS recalculation
    daniel_trades_json = json.dumps(daniel_trades)
    lg_trades_json = json.dumps(lg_trades)

    # KPI cards HTML per tab (initial)
    combined_cards = _build_kpi_cards(combined_summary)
    daniel_cards = _build_kpi_cards(daniel_summary)
    lg_cards = _build_kpi_cards(lg_summary)
    
    mc_summary_json = json.dumps(mc_summary or {})
    trade_pnls_json = json.dumps(trade_pnls or [])

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg:#0b1220;--surface:#121a2b;--surface2:#172134;--border:#2a3853;
    --text:#e8eefc;--muted:#8ea0c4;--accent:#5cd6ff;
    --win:#4ade80;--loss:#fb7185;
    --daniel:#4fc3f7;--lg:#81c784;--combined:#ffffff;
  }}
  * {{box-sizing:border-box;margin:0;padding:0}}
  body {{background:radial-gradient(circle at top,#15213b 0%,#0b1220 55%);color:var(--text);font:14px/1.5 "Segoe UI",system-ui,sans-serif;min-height:100vh}}
  .wrap {{max-width:1400px;margin:0 auto;padding:28px 20px}}
  header {{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:24px;flex-wrap:wrap;gap:20px}}
  h1 {{font-size:28px;font-weight:800;letter-spacing:-0.02em;margin-bottom:6px}}
  .subtitle {{color:var(--muted);font-size:13px}}
  
  /* Sizing Controls */
  .sizing-panel {{background:rgba(255,255,255,0.03);border:1px solid var(--border);border-radius:14px;padding:12px 18px;display:flex;gap:20px;align-items:center;backdrop-filter:blur(10px)}}
  .sizing-group {{display:flex;flex-direction:column;gap:4px}}
  .sizing-group label {{font-size:9px;text-transform:uppercase;letter-spacing:0.1em;color:var(--muted);font-weight:700}}
  .sizing-group select, .sizing-group input {{background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:8px;font-size:13px;font-weight:600;outline:none}}
  .sizing-group select:focus, .sizing-group input:focus {{border-color:var(--accent)}}

  .panel {{background:rgba(18,26,43,.94);border:1px solid var(--border);border-radius:18px;padding:20px;margin-bottom:18px;box-shadow:0 20px 45px rgba(0,0,0,.18)}}
  .stats {{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:4px}}
  .card {{background:var(--surface2);border:1px solid var(--border);border-radius:14px;padding:14px;transition:transform .12s}}
  .card:hover {{transform:translateY(-2px)}}
  .label {{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}}
  .value {{font-size:20px;font-weight:800;line-height:1.1}}
  .subvalue {{color:var(--muted);font-size:11px;margin-top:4px}}
  .chart-wrap {{height:380px;position:relative}}
  /* Tabs */
  .tab-bar {{display:flex;gap:4px;margin-bottom:20px;background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:6px}}
  .tab-btn {{flex:1;padding:10px 16px;border:none;background:transparent;color:var(--muted);font-weight:700;font-size:13px;border-radius:10px;cursor:pointer;transition:all .15s;letter-spacing:.04em}}
  .tab-btn:hover {{color:var(--text);background:var(--surface2)}}
  .tab-btn.active {{background:var(--accent);color:#07111f}}
  .tab-btn[data-tab="daniel"].active {{background:var(--daniel);color:#07111f}}
  .tab-btn[data-tab="lg"].active {{background:var(--lg);color:#0f1a0f}}
  .tab-btn[data-tab="mc"].active {{background:#ff9800;color:#111}}
  .tab-panel {{display:none}}
  .tab-panel.active {{display:block}}
  /* Legend dots */
  .legend {{display:flex;gap:16px;margin-bottom:12px;font-size:12px;color:var(--muted)}}
  .dot {{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px}}
  .note {{color:var(--muted);font-size:12px}}
  @media(max-width:700px) {{.chart-wrap {{height:260px}}}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>⚡ {title}</h1>
      <div class="subtitle">Generated {generated_at} · Daniel (IFVG breakout) + ORB Strategy · $20/pt NQ</div>
    </div>
    
    <div class="sizing-panel">
      <div class="sizing-group">
        <label>Sizing Mode</label>
        <select id="sizingMode" onchange="recalculateAll()">
          <option value="fixed">Fixed Contracts</option>
          <option value="risk">Risk Percentage</option>
        </select>
      </div>
      <div class="sizing-group" id="contractGroup">
        <label>Contracts</label>
        <input type="number" id="contracts" value="1" min="1" max="50" onchange="recalculateAll()">
      </div>
      <div class="sizing-group" id="riskGroup" style="display:none">
        <label>Risk %</label>
        <input type="number" id="riskPct" value="1.0" min="0.1" max="10" step="0.1" onchange="recalculateAll()">
      </div>
      <div class="sizing-group">
        <label>Initial Equity</label>
        <input type="number" id="equityInput" value="100000" step="1000" onchange="recalculateAll()">
      </div>
      <div class="sizing-group">
        <label>From Date</label>
        <input type="date" id="fromDate" onchange="recalculateAll()">
      </div>
      <div class="sizing-group">
        <label>To Date</label>
        <input type="date" id="toDate" onchange="recalculateAll()">
      </div>
    </div>
  </header>

  <!-- Tab Bar -->
  <div class="tab-bar">
    <button class="tab-btn active" data-tab="combined" onclick="switchTab('combined',this)">🔗 Combined</button>
    <button class="tab-btn" data-tab="daniel" onclick="switchTab('daniel',this)">📈 Daniel</button>
    <button class="tab-btn" data-tab="lg" onclick="switchTab('lg',this)">🎯 ORB Strategy</button>
    <button class="tab-btn" data-tab="mc" onclick="switchTab('mc',this)">🎲 Monte Carlo</button>
  </div>

  <!-- Combined Tab -->
  <div id="tab-combined" class="tab-panel active">
    <div class="panel">
      <div class="legend">
        <span><span class="dot" style="background:var(--combined)"></span>Combined Portfolio</span>
        <span><span class="dot" style="background:var(--daniel)"></span>Daniel</span>
        <span><span class="dot" style="background:var(--lg)"></span>ORB Strategy</span>
      </div>
      <div class="chart-wrap"><canvas id="chart-combined"></canvas></div>
    </div>
    <div class="panel">
      <div class="label" style="margin-bottom:14px">Combined Portfolio Metrics</div>
      <div class="stats" id="combinedStats"></div>
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
      <div class="stats" id="danielStats"></div>
    </div>
  </div>

  <!-- LG Model Tab -->
  <div id="tab-lg" class="tab-panel">
    <div class="panel">
      <div class="legend">
        <span><span class="dot" style="background:var(--lg)"></span>ORB Strategy — Session Breakouts</span>
      </div>
      <div class="chart-wrap"><canvas id="chart-lg"></canvas></div>
    </div>
    <div class="panel">
      <div class="label" style="margin-bottom:14px">ORB Strategy Metrics</div>
      <div class="stats" id="lgStats"></div>
    </div>
  </div>

  <!-- Monte Carlo Tab -->
  <div id="tab-mc" class="tab-panel">
    <div class="panel">
      <div class="legend">
        <span><span class="dot" style="background:#ffffff"></span>Mean Path (Combined Average)</span>
        <span><span class="dot" style="background:rgba(255,255,255,0.15)"></span>Random Equity Paths (x100 Samples)</span>
      </div>
      <div class="chart-wrap"><canvas id="chart-mc"></canvas></div>
    </div>
    <div class="panel">
      <div class="label" style="margin-bottom:14px">Monte Carlo Statistics (Bootstrapped)</div>
      <div class="stats" id="mcStats"></div>
    </div>
  </div>

</div>

<script>
// ── Data ──────────────────────────────────────────────────
const DANIEL_TRADES = {daniel_trades_json};
const ORB_TRADES    = {lg_trades_json};
const MC_SUMMARY    = {mc_summary_json};
const TRADE_PNLS    = {trade_pnls_json};
const POINT_VALUE   = 20;

// ── Tab switching ──────────────────────────────────────────
const chartInstances = {{}};
let activeTab = 'combined';

function switchTab(name, btn) {{
  activeTab = name;
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
  if (chartInstances[name]) {{
    setTimeout(() => chartInstances[name].resize(), 10);
  }}
}}

// ── Calculation Logic ──────────────────────────────────────
function tradePnl(t, currentEquity) {{
  const mode = document.getElementById('sizingMode').value;
  let contracts = 1;

  if (mode === 'fixed') {{
    contracts = parseInt(document.getElementById('contracts').value) || 1;
  }} else {{
    const riskPct = parseFloat(document.getElementById('riskPct').value) / 100;
    const riskDollars = currentEquity * riskPct;
    const stopPoints = Math.max(0.25, t.risk_points || 4); // fallbacks
    const riskPerContract = stopPoints * POINT_VALUE;
    contracts = Math.floor(riskDollars / riskPerContract);
    contracts = Math.max(1, Math.min(contracts, 100)); // cap for sanity
  }}

  const usd = t.pnl_points * contracts * POINT_VALUE;
  return {{ usd, contracts }};
}}

function getCurve(trades, initialEquity) {{
  let equity = initialEquity;
  const curve = [{{ date: "Start", equity }}];
  for (const t of trades) {{
    const p = tradePnl(t, equity);
    equity += p.usd;
    curve.push({{ date: t.date, equity: parseFloat(equity.toFixed(2)) }});
  }}
  return curve;
}}

function buildMetrics(trades, initialEquity) {{
  let equity = initialEquity;
  let peak = initialEquity;
  let maxDdUsd = 0;
  let wins = 0;
  let grossWin = 0;
  let grossLoss = 0;
  
  for (const t of trades) {{
    const p = tradePnl(t, equity);
    equity += p.usd;
    if (p.usd > 0) {{ wins++; grossWin += p.usd; }}
    else if (p.usd < 0) {{ grossLoss += Math.abs(p.usd); }}
    
    if (equity > peak) peak = equity;
    let dd = peak - equity;
    if (dd > maxDdUsd) maxDdUsd = dd;
  }}
  
  const totalPnl = equity - initialEquity;
  const winRate = trades.length ? wins / trades.length : 0;
  const pf = grossLoss > 0 ? grossWin / grossLoss : (grossWin > 0 ? 99 : 0);
  const maxDdPct = peak > 0 ? (maxDdUsd / peak) : 0;

  return {{
    total_pnl: totalPnl,
    total_trades: trades.length,
    win_rate: winRate,
    profit_factor: pf,
    max_dd_pct: maxDdPct,
    max_dd_usd: maxDdUsd,
    expectancy: trades.length ? totalPnl / trades.length : 0,
    avg_win_usd: wins ? grossWin / wins : 0,
    avg_loss_usd: (trades.length - wins) ? grossLoss / (trades.length - wins) : 0
  }};
}}

function renderStats(summary, elementId) {{
  const el = document.getElementById(elementId);
  const fmt = (v) => v.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}});
  const clr = (v) => v >= 0 ? 'var(--win)' : 'var(--loss)';
  
  const cards = [
    ['Total P&L', (summary.total_pnl >= 0 ? '+$' : '-$') + Math.abs(summary.total_pnl).toLocaleString(), '', clr(summary.total_pnl)],
    ['Total Trades', summary.total_trades.toString(), '', 'var(--text)'],
    ['Win Rate', (summary.win_rate * 100).toFixed(1) + '%', '', summary.win_rate >= 0.5 ? 'var(--win)' : 'var(--loss)'],
    ['Profit Factor', summary.profit_factor.toFixed(2), '', 'var(--text)'],
    ['Max Drawdown', (summary.max_dd_pct * 100).toFixed(1) + '%', '-$' + summary.max_dd_usd.toLocaleString(), 'var(--loss)'],
    ['Avg Win', '$' + fmt(summary.avg_win_usd), '', 'var(--win)'],
    ['Avg Loss', '-$' + fmt(summary.avg_loss_usd), '', 'var(--loss)'],
    ['Expectancy', '$' + fmt(summary.expectancy), 'Per trade', 'var(--text)'],
  ];
  
  el.innerHTML = cards.map(c => `
    <div class="card">
      <div class="label">${{c[0]}}</div>
      <div class="value" style="color:${{c[3]}}">${{c[1]}}</div>
      ${{c[2] ? `<div class="subvalue">${{c[2]}}</div>` : ''}}
    </div>
  `).join('');
}}

function recalculateAll() {{
  const initialEquity = parseFloat(document.getElementById('equityInput').value) || 100000;
  const mode = document.getElementById('sizingMode').value;
  const fromD = document.getElementById('fromDate').value;
  const toD = document.getElementById('toDate').value;

  document.getElementById('contractGroup').style.display = mode === 'fixed' ? 'flex' : 'none';
  document.getElementById('riskGroup').style.display = mode === 'risk' ? 'flex' : 'none';

  // Filter trades by date
  const filterByDate = (trades) => trades.filter(t => {{
    if (fromD && t.date < fromD) return false;
    if (toD && t.date > toD) return false;
    return true;
  }});

  const filteredDaniel = filterByDate(DANIEL_TRADES);
  const filteredOrb = filterByDate(ORB_TRADES);

  // 1. Calculate Individual Curves
  const dCurve = getCurve(filteredDaniel, initialEquity);
  const oCurve = getCurve(filteredOrb, initialEquity);

  // 2. Calculate Combined Curve
  const allMerged = [...filteredDaniel.map(t=>({{...t, s:'d'}})), ...filteredOrb.map(t=>({{...t, s:'o'}}))]
                     .sort((a,b) => a.exit_time_sort.localeCompare(b.exit_time_sort));
  
  let combinedEquity = initialEquity;
  let dPnl = 0;
  let oPnl = 0;
  const cCurve = [{{ date: "Start", equity: initialEquity, d: initialEquity, o: initialEquity }}];
  
  for(const t of allMerged) {{
    const p = tradePnl(t, combinedEquity);
    combinedEquity += p.usd;
    if(t.s === 'd') dPnl += p.usd; else oPnl += p.usd;
    cCurve.push({{
      date: t.date,
      equity: combinedEquity,
      d: initialEquity + dPnl,
      o: initialEquity + oPnl
    }});
  }}

  // 3. Update Charts
  updateChart('combined', [
    {{ label: 'Combined', data: cCurve.map(p=>p.equity), borderColor: '#ffffff', fill: true, backgroundColor: 'rgba(255,255,255,0.05)' }},
    {{ label: 'Daniel', data: cCurve.map(p=>p.d), borderColor: 'rgba(79,195,247,0.4)', pointRadius: 0 }},
    {{ label: 'ORB', data: cCurve.map(p=>p.o), borderColor: 'rgba(129,199,132,0.4)', pointRadius: 0 }}
  ], cCurve.map(p=>p.date));

  updateChart('daniel', [
    {{ label: 'Daniel', data: dCurve.map(p=>p.equity), borderColor: '#4fc3f7', fill: true, backgroundColor: 'rgba(79,195,247,0.07)' }}
  ], dCurve.map(p=>p.date));

  updateChart('lg', [
    {{ label: 'ORB', data: oCurve.map(p=>p.equity), borderColor: '#81c784', fill: true, backgroundColor: 'rgba(129,199,132,0.07)' }}
  ], oCurve.map(p=>p.date));

  // 5. Update Monte Carlo Chart
  updateMcChart(initialEquity);

  // 4. Update Summaries
  renderStats(buildMetrics(filteredDaniel, initialEquity), 'danielStats');
  renderStats(buildMetrics(filteredOrb, initialEquity), 'lgStats');
  
  // Combined metrics uses the merged trade PnLs
  let tempEquity = initialEquity;
  const combinedTrades = allMerged.map(t => {{
    const p = tradePnl(t, tempEquity);
    tempEquity += p.usd;
    return {{ ...t, pnl_usd: p.usd }};
  }});
  renderStats(buildMetrics(combinedTrades, initialEquity), 'combinedStats');
}}

function updateChart(id, datasets, labels) {{
  const canvas = document.getElementById('chart-' + id);
  if (chartInstances[id]) {{
    chartInstances[id].data.labels = labels;
    chartInstances[id].data.datasets = datasets.map((ds, i) => {{
      const existing = chartInstances[id].data.datasets[i];
      return {{ ...existing, ...ds }};
    }});
    chartInstances[id].update('none');
  }} else {{
    const ctx = canvas.getContext('2d');
    chartInstances[id] = new Chart(ctx, {{
      type: 'line',
      data: {{ labels, datasets }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        elements: {{ point: {{ radius: 0 }}, line: {{ tension: 0.2, borderWidth: 2 }} }},
        scales: {{
          x: {{ display: true, ticks: {{ color: '#8ea0c4', maxTicksLimit: 12 }} }},
          y: {{ display: true, ticks: {{ color: '#8ea0c4', callback: v => '$' + (v >= 1000 ? v/1000 + 'k' : v) }} }}
        }},
        plugins: {{ legend: {{ display: false }}, tooltip: {{ mode: 'index', intersect: false }} }}
      }}
    }});
  }}
}}

function updateMcChart(initialEquity) {{
  if (!TRADE_PNLS || TRADE_PNLS.length === 0) return;
  
  const canvas = document.getElementById('chart-mc');
  const nVisPaths = 100;
  const nTrades = TRADE_PNLS.length;
  const datasets = [];
  
  // 1. Generate Ghost Paths (random sampling from TRADE_PNLS)
  // We use a simple PRNG to keep it deterministic for a given set of trades
  let seed = 42;
  const rng = () => {{ seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }};
  
  for (let p = 0; p < nVisPaths; p++) {{
    let eq = initialEquity;
    const data = [eq];
    for (let t = 0; t < nTrades; t++) {{
        const idx = Math.floor(rng() * nTrades);
        eq += TRADE_PNLS[idx];
        data.push(eq);
    }}
    datasets.push({{
        label: p === 0 ? 'Sample Paths' : undefined,
        data,
        borderColor: 'rgba(255,255,255,0.06)',
        borderWidth: 1,
        pointRadius: 0,
        order: 10
    }});
  }}

  // 2. Generate Mean Path (True mathematical mean path)
  const meanPnl = TRADE_PNLS.reduce((a, b) => a + b, 0) / nTrades;
  const meanPath = [initialEquity];
  let mEq = initialEquity;
  for (let t = 0; t < nTrades; t++) {{
    mEq += meanPnl;
    meanPath.push(mEq);
  }}
  datasets.push({{
    label: 'Mean Path',
    data: meanPath,
    borderColor: '#ffffff',
    borderWidth: 3,
    pointRadius: 0,
    order: 0
  }});

  const labels = Array.from({{length: nTrades + 1}}, (_, i) => i === 0 ? "Start" : i.toString());

  if (chartInstances['mc']) {{
    chartInstances['mc'].data.labels = labels;
    chartInstances['mc'].data.datasets = datasets;
    chartInstances['mc'].update('none');
  }} else {{
    const ctx = canvas.getContext('2d');
    chartInstances['mc'] = new Chart(ctx, {{
      type: 'line',
      data: {{ labels, datasets }},
      options: {{
        responsive: true, maintainAspectRatio: false,
        scales: {{
          x: {{ display: true, ticks: {{ color: '#8ea0c4', maxTicksLimit: 12 }}, title: {{ display: true, text: 'Trade Number', color: '#8ea0c4' }} }},
          y: {{ display: true, ticks: {{ color: '#8ea0c4', callback: v => '$' + (v >= 1000 ? v/1000 + 'k' : v) }} }}
        }},
        plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }} }},
        animation: false
      }}
    }});
  }}

  // Update MC Stats Cards
  const fmt = (v) => v.toLocaleString(undefined, {{minimumFractionDigits:2, maximumFractionDigits:2}});
  const el = document.getElementById('mcStats');
  if (MC_SUMMARY && MC_SUMMARY.mean_final_equity) {{
    const cards = [
        ['Mean Final Equity', '$' + fmt(MC_SUMMARY.mean_final_equity), 'Average of all paths', 'var(--win)'],
        ['5% Percentile', '$' + fmt(MC_SUMMARY.p05_final_equity), '95% certainty above this', 'var(--loss)'],
        ['50% Percentile', '$' + fmt(MC_SUMMARY.p50_final_equity), 'Median outcome', 'var(--text)'],
        ['95% Percentile', '$' + fmt(MC_SUMMARY.p95_final_equity), 'Top 5% outcome', 'var(--win)'],
        ['Trade Count', MC_SUMMARY.trades_per_path.toString(), 'Trades per path', 'var(--text)'],
        ['MC Paths', MC_SUMMARY.paths.toString(), 'Total simulations', 'var(--text)'],
    ];
    el.innerHTML = cards.map(c => `
      <div class="card">
        <div class="label">${{c[0]}}</div>
        <div class="value" style="color:${{c[3]}}">${{c[1]}}</div>
        <div class="subvalue">${{c[2]}}</div>
      </div>
    `).join('');
  }}
}}

// Initialize
window.onload = recalculateAll;
</script>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return str(output_path.resolve())
