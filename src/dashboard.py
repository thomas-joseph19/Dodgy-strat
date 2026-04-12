"""
Interactive HTML Dashboard Generator for DodgysDD IFVG Mechanical Backtest.

Produces a single self-contained HTML file with:
- Chart.js equity curve
- Live-recalculating stats (P&L, Sharpe, Sortino, Calmar, PF, etc.)
- Session / date / slippage mode filtering
- Day-of-week and calendar-year breakdowns
- Full scrollable trade log
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import List

from src.execution import Direction, TradeResult


def _classify_session(ts: datetime) -> str:
    """Classify a timestamp into a trading session bucket."""
    h, m = ts.hour, ts.minute
    if h < 9 or (h == 9 and m < 30):
        return "pre_market"
    if h < 12:
        return "open_drive"
    if h < 14:
        return "midday"
    if h < 16:
        return "power_hour"
    return "overnight"


def _session_label(code: str) -> str:
    return {
        "pre_market": "Pre-Mkt",
        "open_drive": "Open Drive",
        "midday": "Midday",
        "power_hour": "Power Hr",
        "overnight": "Overnight",
    }.get(code, code)


_DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _build_trade_records(results: List[TradeResult]) -> list[dict]:
    """Convert TradeResults to JSON-serializable dicts for embedding."""
    records = []
    for r in results:
        entry = r.setup.entry_price
        stop = r.setup.stop_price
        risk = abs(entry - stop)
        if r.setup.direction == Direction.LONG:
            pnl_pts = r.exit_price - entry
        else:
            pnl_pts = entry - r.exit_price

        records.append({
            "date": r.setup.created_at.strftime("%Y-%m-%d"),
            "time": r.setup.created_at.strftime("%H:%M"),
            "setup_id": r.setup.setup_id,
            "direction": r.setup.direction.value,
            "session": _classify_session(r.setup.created_at),
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "target": round(r.setup.target_price, 2),
            "exit_price": round(r.exit_price, 2),
            "exit_type": r.exit_type,
            "risk_points": round(risk, 2),
            "pnl_points": round(pnl_pts, 2),
            "pnl_raw": round(pnl_pts * 20.0, 2),
            "r_multiple": round(pnl_pts / risk, 2) if risk > 0 else 0.0,
            "risk_reward": round(r.setup.risk_reward, 2),
            "reasoning": r.setup.reasoning,
            "day_of_week": r.setup.created_at.weekday(),
            "year": r.setup.created_at.year,
        })
    return records


def generate_dashboard(
    results: list[TradeResult],
    output_path: str,
    initial_capital: float = 100_000.0,
    title: str = "DodgysDD IFVG Mechanical Backtest",
) -> str:
    """Generate a self-contained interactive HTML dashboard and write it to *output_path*.

    Returns the absolute path written.
    """
    trades_json = json.dumps(_build_trade_records(results), indent=None)

    html = _HTML_TEMPLATE.replace("{{TITLE}}", title)
    html = html.replace("{{TRADES_JSON}}", trades_json)
    html = html.replace("{{INITIAL_CAPITAL}}", str(initial_capital))

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    return output_path


# ---------------------------------------------------------------------------
# Full HTML template (inline CSS + JS, Chart.js via CDN)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{{TITLE}}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js"></script>
<style>
  :root{--bg:#0b1220;--surface:#121a2b;--surface2:#172134;--border:#2a3853;--text:#e8eefc;--muted:#8ea0c4;--accent:#5cd6ff;--pre:#d8a7ff;--open:#73b7ff;--mid:#ffd56a;--pwr:#ff9a76;--ovn:#a3f7bf;--win:#4ade80;--loss:#fb7185}
  *{box-sizing:border-box}
  body{margin:0;background:radial-gradient(circle at top,#15213b 0%,#0b1220 55%);color:var(--text);font:14px/1.4 "Segoe UI",system-ui,sans-serif}
  .wrap{max-width:1550px;margin:0 auto;padding:28px}
  .hero{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;flex-wrap:wrap;margin-bottom:22px}
  h1{margin:0;font-size:30px}
  .sub{color:var(--muted);margin-top:8px;max-width:900px}
  .toolbar,.toggle-row{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
  .panel{background:rgba(18,26,43,.94);border:1px solid var(--border);border-radius:18px;padding:18px;margin-bottom:18px;box-shadow:0 20px 45px rgba(0,0,0,.18)}
  .controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}
  .control label{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px}
  .control input,.control select{width:100%;background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:12px;padding:10px 12px}
  .quick-range{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
  .quick-range .pill{padding:7px 12px;font-size:12px}
  .pill{border:1px solid var(--border);background:var(--surface2);color:var(--muted);padding:9px 14px;border-radius:999px;cursor:pointer;font-weight:700;transition:all .15s}
  .pill:hover{border-color:var(--accent);color:var(--text)}
  .pill.active{background:var(--accent);color:#07111f;border-color:transparent}
  .session-pill[data-session="pre_market"].active{background:var(--pre);color:#1d1230}
  .session-pill[data-session="open_drive"].active{background:var(--open);color:#0f1a2c}
  .session-pill[data-session="midday"].active{background:var(--mid);color:#241b06}
  .session-pill[data-session="power_hour"].active{background:var(--pwr);color:#2a1308}
  .session-pill[data-session="overnight"].active{background:var(--ovn);color:#0a2016}
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
  .card{background:var(--surface2);border:1px solid var(--border);border-radius:14px;padding:14px;transition:transform .12s}
  .card:hover{transform:translateY(-2px)}
  .card .label{font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
  .card .value{font-size:22px;font-weight:800}
  .card .subvalue{margin-top:5px;color:var(--muted);font-size:12px}
  .grid{display:grid;grid-template-columns:1.3fr .9fr;gap:18px}
  .chart-wrap{height:380px}
  table{width:100%;border-collapse:collapse}
  th,td{padding:10px 12px;border-bottom:1px solid var(--border);text-align:left}
  th{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
  .num{text-align:right;font-variant-numeric:tabular-nums}
  .win{color:var(--win)}
  .loss{color:var(--loss)}
  .badge{display:inline-block;padding:4px 9px;border-radius:999px;font-size:11px;font-weight:700}
  .badge.pre_market{background:rgba(216,167,255,.16);color:var(--pre)}
  .badge.open_drive{background:rgba(115,183,255,.14);color:var(--open)}
  .badge.midday{background:rgba(255,213,106,.15);color:var(--mid)}
  .badge.power_hour{background:rgba(255,154,118,.15);color:var(--pwr)}
  .badge.overnight{background:rgba(163,247,191,.14);color:var(--ovn)}
  .scroll{max-height:480px;overflow:auto}
  .note{color:var(--muted);font-size:12px}
  @media (max-width:980px){.grid{grid-template-columns:1fr}.chart-wrap{height:320px}}
</style>
</head>
<body>
<div class="wrap">

  <!-- Hero -->
  <div class="hero">
    <div>
      <h1 id="dashTitle">{{TITLE}}</h1>
      <div class="sub">Mechanical IFVG backtest dashboard — session-specific DodgysDD breakdowns. Toggle session, slippage mode, and contract sizing live. Default view starts at $100,000 with 1 contract.</div>
    </div>
    <div class="panel" style="min-width:320px">
      <div class="note">Saved outputs: <strong>dashboard.html</strong> and <strong>trades.csv</strong></div>
      <div class="note" style="margin-top:8px">Pure mechanical strategy — no ML filtering applied. This is the ground-truth baseline from the v1.0 backtest engine over the full available dataset.</div>
    </div>
  </div>

  <!-- Controls -->
  <div class="panel">
    <div class="controls">
      <div class="control"><label>Contract Size</label><input id="contractsInput" type="number" min="1" step="1" value="1"/></div>
      <div class="control"><label>Initial Equity</label><input id="equityInput" type="number" min="1000" step="1000" value="{{INITIAL_CAPITAL}}"/></div>
      <div class="control"><label>Round-Trip Slippage</label><input id="slippageInput" type="number" min="0" step="0.05" value="0.50"/></div>
      <div class="control"><label>Commission / Contract / RT</label><input id="commissionInput" type="number" min="0" step="0.1" value="4.00"/></div>
      <div class="control"><label>Timeframe Preset</label>
        <select id="timeframePreset">
          <option value="full">Full history</option>
          <option value="ytd">Year to date</option>
          <option value="1y">Last 1 year</option>
          <option value="3y">Last 3 years</option>
          <option value="5y">Last 5 years</option>
          <option value="10y">Last 10 years</option>
          <option value="custom">Custom range</option>
        </select>
      </div>
      <div class="control"><label>From Date</label><input id="fromDateInput" type="date"/></div>
      <div class="control"><label>To Date</label><input id="toDateInput" type="date"/></div>
    </div>
    <div class="quick-range">
      <button class="pill range-pill active" data-range="full">Full History</button>
      <button class="pill range-pill" data-range="5y">Last 5Y</button>
      <button class="pill range-pill" data-range="3y">Last 3Y</button>
      <button class="pill range-pill" data-range="1y">Last 1Y</button>
      <button class="pill range-pill" data-range="ytd">YTD</button>
    </div>
    <div class="toggle-row" style="margin-top:14px">
      <button class="pill mode-pill active" data-mode="raw">Raw Fills</button>
      <button class="pill mode-pill" data-mode="net">With Slippage</button>
    </div>
    <div class="toggle-row" style="margin-top:12px">
      <button class="pill session-pill active" data-session="PORTFOLIO">Portfolio</button>
      <button class="pill session-pill" data-session="pre_market">Pre-Mkt</button>
      <button class="pill session-pill" data-session="open_drive">Open Drive</button>
      <button class="pill session-pill" data-session="midday">Midday</button>
      <button class="pill session-pill" data-session="power_hour">Power Hr</button>
      <button class="pill session-pill" data-session="overnight">Overnight</button>
    </div>
    <div class="toggle-row" id="portfolio-filters" style="margin-top:12px;font-size:12px;color:var(--muted);align-items:center;">
      <span style="font-weight:600;text-transform:uppercase;letter-spacing:0.05em;margin-right:6px">Include in Portfolio:</span>
      <label style="display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" class="portfolio-filter" value="pre_market" checked> Pre-Mkt</label>
      <label style="display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" class="portfolio-filter" value="open_drive" checked> Open Drive</label>
      <label style="display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" class="portfolio-filter" value="midday" checked> Midday</label>
      <label style="display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" class="portfolio-filter" value="power_hour" checked> Power Hr</label>
      <label style="display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" class="portfolio-filter" value="overnight" checked> Overnight</label>
    </div>
  </div>

  <!-- Stats -->
  <div class="panel"><div id="statsGrid" class="stats"></div></div>

  <!-- Charts + Session Table -->
  <div class="grid">
    <div class="panel">
      <div class="note" id="chartTitle" style="margin-bottom:10px"></div>
      <div class="chart-wrap"><canvas id="equityChart"></canvas></div>
    </div>
    <div class="panel">
      <div class="note" style="margin-bottom:10px">Session comparison updates for the current slippage mode and contract size.</div>
      <table>
        <thead><tr><th>Session</th><th class="num">Trades</th><th class="num">Win %</th><th class="num">USD</th><th class="num">PF</th><th class="num">Sharpe</th><th class="num">Max DD</th></tr></thead>
        <tbody id="sessionTableBody"></tbody>
      </table>
    </div>
  </div>

  <!-- DOW + Year tables -->
  <div class="grid">
    <div class="panel">
      <div class="note" style="margin-bottom:10px">Day-of-week breakdown for the selected session and mode.</div>
      <table>
        <thead><tr><th>Day</th><th class="num">Trades</th><th class="num">Win %</th><th class="num">Pts</th><th class="num">USD</th></tr></thead>
        <tbody id="dowTableBody"></tbody>
      </table>
    </div>
    <div class="panel">
      <div class="note" style="margin-bottom:10px">Calendar-year returns for the selected view.</div>
      <table>
        <thead><tr><th>Year</th><th class="num">Trades</th><th class="num">P/L USD</th><th class="num">Return</th><th class="num">End Equity</th></tr></thead>
        <tbody id="yearTableBody"></tbody>
      </table>
    </div>
  </div>

  <!-- Outcome summary -->
  <div class="grid">
    <div class="panel">
      <div class="note" id="summaryTitle" style="margin-bottom:10px">Outcome distribution for the selected view.</div>
      <table>
        <thead><tr><th>Outcome</th><th class="num">Count</th><th class="num">Share</th></tr></thead>
        <tbody id="summaryBody"></tbody>
      </table>
    </div>
    <div class="panel">
      <div class="note" style="margin-bottom:10px">R-multiple distribution (risk-adjusted performance).</div>
      <table>
        <thead><tr><th>R Bucket</th><th class="num">Count</th><th class="num">Share</th><th class="num">Avg PnL</th></tr></thead>
        <tbody id="rDistBody"></tbody>
      </table>
    </div>
  </div>

  <!-- Trade log -->
  <div class="panel">
    <div class="note" style="margin-bottom:10px">Trade log follows your current session, slippage, and sizing selection.</div>
    <div class="scroll">
      <table>
        <thead><tr>
          <th>Date</th><th>Session</th><th>Side</th><th class="num">Entry</th><th class="num">Stop</th><th class="num">Risk</th><th class="num">P/L pts</th><th class="num">P/L USD</th><th class="num">R</th><th>Exit</th>
        </tr></thead>
        <tbody id="tradeLogBody"></tbody>
      </table>
    </div>
  </div>

</div>

<script>
/* ── Data ─────────────────────────────────────────────── */
const TRADES = {{TRADES_JSON}};
const INITIAL_CAPITAL = {{INITIAL_CAPITAL}};
const POINT_VALUE = 20;
const DOW = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
const SESSION_LABELS = {pre_market:"Pre-Mkt",open_drive:"Open Drive",midday:"Midday",power_hour:"Power Hr",overnight:"Overnight"};
const SESSIONS = ["pre_market","open_drive","midday","power_hour","overnight"];

/* ── State ────────────────────────────────────────────── */
let mode = "raw";
let activeSession = "PORTFOLIO";
let chart = null;

/* ── Helpers ──────────────────────────────────────────── */
function $(id){return document.getElementById(id)}
function val(id){return parseFloat($(id).value)||0}
function fmt(n,d=2){return n.toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d})}
function pct(n){return (n*100).toFixed(1)+"%"}
function clr(n){return n>=0?"win":"loss"}

function tradePnl(t){
  const contracts = val("contractsInput");
  let pts = t.pnl_points;
  if(mode==="net"){
    const slip = val("slippageInput");
    pts -= slip*2; /* round-trip slippage in points */
  }
  const usd = pts * POINT_VALUE * contracts;
  const comm = mode==="net" ? val("commissionInput")*contracts : 0;
  return {pts, usd: usd - comm};
}

function getFiltered(){
  const from = $("fromDateInput").value;
  const to = $("toDateInput").value;
  let arr = TRADES;
  if(from) arr = arr.filter(t=>t.date>=from);
  if(to) arr = arr.filter(t=>t.date<=to);

  if(activeSession==="PORTFOLIO"){
    const checks = document.querySelectorAll(".portfolio-filter");
    const included = new Set();
    checks.forEach(c=>{if(c.checked) included.add(c.value)});
    arr = arr.filter(t=>included.has(t.session));
  } else {
    arr = arr.filter(t=>t.session===activeSession);
  }
  return arr;
}

/* ── Stats ────────────────────────────────────────────── */
function calcStats(trades){
  if(!trades.length) return null;
  const n = trades.length;
  const pnls = trades.map(t=>tradePnl(t));
  const usds = pnls.map(p=>p.usd);
  const wins = usds.filter(u=>u>0);
  const losses = usds.filter(u=>u<0);
  const totalPnl = usds.reduce((a,b)=>a+b,0);
  const winRate = wins.length/n;
  const grossWin = wins.reduce((a,b)=>a+b,0);
  const grossLoss = Math.abs(losses.reduce((a,b)=>a+b,0));
  const pf = grossLoss>0 ? grossWin/grossLoss : grossWin>0?Infinity:0;
  const avgTrade = totalPnl/n;
  const rs = pnls.map(p=>p.pts / (trades[pnls.indexOf(p)].risk_points||1));
  const avgR = rs.reduce((a,b)=>a+b,0)/n;
  const ev = avgTrade;

  /* Daily returns for Sharpe/Sortino */
  const byDate = {};
  trades.forEach((t,i)=>{
    if(!byDate[t.date]) byDate[t.date]=0;
    byDate[t.date] += pnls[i].usd;
  });
  const equity = val("equityInput");
  const dailyRets = Object.values(byDate).map(d=>d/equity);
  const mean = dailyRets.reduce((a,b)=>a+b,0)/dailyRets.length;
  const std = Math.sqrt(dailyRets.reduce((a,b)=>a+(b-mean)**2,0)/(dailyRets.length-1||1));
  const sharpe = std>0 ? Math.sqrt(252)*mean/std : 0;
  const downside = dailyRets.filter(r=>r<0);
  const dStd = downside.length>0 ? Math.sqrt(downside.reduce((a,b)=>a+b**2,0)/downside.length) : 0;
  const sortino = dStd>0 ? Math.sqrt(252)*mean/dStd : 0;

  /* Max DD */
  let peak=equity, maxDD=0;
  const eqCurve=[equity];
  const eqDates=Object.keys(byDate).sort();
  let running=equity;
  eqDates.forEach(d=>{
    running+=byDate[d];
    eqCurve.push(running);
    if(running>peak) peak=running;
    const dd=(peak-running)/peak;
    if(dd>maxDD) maxDD=dd;
  });

  /* Calmar */
  const totalDays = eqDates.length||1;
  const annReturn = (totalPnl/equity)*(252/totalDays);
  const calmar = maxDD>0 ? annReturn/maxDD : 0;

  /* P-value (one-sample t-test) */
  const tStat = usds.length>1 ? (avgTrade) / (Math.sqrt(usds.reduce((a,b)=>a+(b-avgTrade)**2,0)/(n-1)) / Math.sqrt(n)) : 0;
  /* Approx p-value using normal CDF for large n */
  const pValue = 1 - 0.5*(1+erf(Math.abs(tStat)/Math.SQRT2));

  return {n, winRate, totalPnl, pf, sharpe, sortino, maxDD, avgTrade, avgR, calmar, ev, pValue, eqCurve, eqDates:["Start",...eqDates]};
}

function erf(x){
  const a1=0.254829592, a2=-0.284496736, a3=1.421413741, a4=-1.453152027, a5=1.061405429, p=0.3275911;
  const sign=x<0?-1:1; x=Math.abs(x);
  const t=1/(1+p*x);
  return sign*(1-((((a5*t+a4)*t+a3)*t+a2)*t+a1)*t*Math.exp(-x*x));
}

/* ── Render ───────────────────────────────────────────── */
function renderStats(s){
  const g=$("statsGrid");
  if(!s){g.innerHTML='<div class="card"><div class="value" style="font-size:16px">No trades in selected range</div></div>';return}
  const cards=[
    {l:"Total Trades",v:s.n,sv:""},
    {l:"Win Rate",v:pct(s.winRate),sv:"",c:s.winRate>=0.5?"win":"loss"},
    {l:"Net P&L",v:"$"+fmt(s.totalPnl),sv:"",c:clr(s.totalPnl)},
    {l:"Profit Factor",v:fmt(s.pf),sv:"Wins / Losses"},
    {l:"Sharpe Ratio",v:fmt(s.sharpe),sv:"Annualized",c:s.sharpe>=1?"win":s.sharpe>=0?"":"loss"},
    {l:"Sortino Ratio",v:fmt(s.sortino),sv:"Annualized"},
    {l:"Max Drawdown",v:pct(s.maxDD),sv:"Peak to trough",c:"loss"},
    {l:"Avg Trade",v:"$"+fmt(s.avgTrade),sv:"Per trade",c:clr(s.avgTrade)},
    {l:"Avg R",v:fmt(s.avgR)+"R",sv:"Risk-adjusted"},
    {l:"Calmar Ratio",v:fmt(s.calmar),sv:"Return / MaxDD"},
    {l:"EV / Trade",v:"$"+fmt(s.ev),sv:"Expected Value",c:clr(s.ev)},
    {l:"P-Value",v:s.pValue<0.001?"<0.001":s.pValue.toFixed(3),sv:s.pValue<0.05?"Significant":"Not significant",c:s.pValue<0.05?"win":"loss"},
  ];
  g.innerHTML=cards.map(c=>`<div class="card"><div class="label">${c.l}</div><div class="value ${c.c||''}">${c.v}</div>${c.sv?`<div class="subvalue">${c.sv}</div>`:''}</div>`).join("");
}

function renderChart(s){
  const ctx = $("equityChart").getContext("2d");
  if(chart) chart.destroy();
  if(!s) return;
  $("chartTitle").textContent = `Equity curve — ${activeSession==="PORTFOLIO"?"Portfolio":SESSION_LABELS[activeSession]||activeSession} · ${mode==="raw"?"Raw":"Net"} · ${val("contractsInput")} contract(s)`;
  chart = new Chart(ctx,{
    type:"line",
    data:{
      labels:s.eqDates,
      datasets:[{
        label:"Equity",
        data:s.eqCurve,
        borderColor:"#5cd6ff",
        backgroundColor:"rgba(92,214,255,.08)",
        fill:true,
        borderWidth:2,
        pointRadius:0,
        tension:0.25
      }]
    },
    options:{
      responsive:true,
      maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{mode:"index",intersect:false,backgroundColor:"#172134",titleColor:"#e8eefc",bodyColor:"#8ea0c4",borderColor:"#2a3853",borderWidth:1}},
      scales:{
        x:{display:true,grid:{color:"rgba(42,56,83,.3)"},ticks:{color:"#8ea0c4",maxTicksLimit:12,font:{size:10}}},
        y:{display:true,grid:{color:"rgba(42,56,83,.3)"},ticks:{color:"#8ea0c4",callback:v=>"$"+v.toLocaleString()}}
      }
    }
  });
}

function renderSessionTable(){
  const trades = getFiltered();
  const body=$("sessionTableBody");
  let rows = "";
  SESSIONS.forEach(ses=>{
    const st = trades.filter(t=>t.session===ses);
    if(!st.length) return;
    const s = calcStats(st);
    if(!s) return;
    rows += `<tr><td><span class="badge ${ses}">${SESSION_LABELS[ses]}</span></td><td class="num">${s.n}</td><td class="num">${pct(s.winRate)}</td><td class="num ${clr(s.totalPnl)}">$${fmt(s.totalPnl)}</td><td class="num">${fmt(s.pf)}</td><td class="num">${fmt(s.sharpe)}</td><td class="num loss">${pct(s.maxDD)}</td></tr>`;
  });
  body.innerHTML = rows || '<tr><td colspan="7" class="note">No data</td></tr>';
}

function renderDOW(){
  const trades = getFiltered();
  const body=$("dowTableBody");
  let rows="";
  for(let d=0;d<5;d++){
    const dt = trades.filter(t=>t.day_of_week===d);
    if(!dt.length) continue;
    const pnls = dt.map(t=>tradePnl(t));
    const totalPts = pnls.reduce((a,p)=>a+p.pts,0);
    const totalUsd = pnls.reduce((a,p)=>a+p.usd,0);
    const wr = dt.filter((_,i)=>pnls[i].usd>0).length/dt.length;
    rows+=`<tr><td>${DOW[d]}</td><td class="num">${dt.length}</td><td class="num">${pct(wr)}</td><td class="num ${clr(totalPts)}">${fmt(totalPts)}</td><td class="num ${clr(totalUsd)}">$${fmt(totalUsd)}</td></tr>`;
  }
  body.innerHTML=rows||'<tr><td colspan="5" class="note">No data</td></tr>';
}

function renderYears(){
  const trades = getFiltered();
  const body=$("yearTableBody");
  const years = [...new Set(trades.map(t=>t.year))].sort();
  let rows="", running=val("equityInput");
  years.forEach(y=>{
    const yt = trades.filter(t=>t.year===y);
    const pnls = yt.map(t=>tradePnl(t));
    const totalUsd = pnls.reduce((a,p)=>a+p.usd,0);
    const ret = running>0 ? totalUsd/running : 0;
    running += totalUsd;
    rows+=`<tr><td>${y}</td><td class="num">${yt.length}</td><td class="num ${clr(totalUsd)}">$${fmt(totalUsd)}</td><td class="num ${clr(ret)}">${pct(ret)}</td><td class="num">$${fmt(running)}</td></tr>`;
  });
  body.innerHTML=rows||'<tr><td colspan="5" class="note">No data</td></tr>';
}

function renderOutcomes(){
  const trades = getFiltered();
  const body=$("summaryBody");
  const counts={};
  trades.forEach(t=>{counts[t.exit_type]=(counts[t.exit_type]||0)+1});
  const total=trades.length||1;
  let rows="";
  Object.keys(counts).sort().forEach(k=>{
    rows+=`<tr><td>${k}</td><td class="num">${counts[k]}</td><td class="num">${pct(counts[k]/total)}</td></tr>`;
  });
  body.innerHTML=rows||'<tr><td colspan="3" class="note">No data</td></tr>';
}

function renderRDist(){
  const trades = getFiltered();
  const body=$("rDistBody");
  const buckets = {"< -2R":[],"[-2R, -1R]":[],"(-1R, 0)":[],"[0, 1R]":[],"(1R, 2R]":[],"> 2R":[]};
  trades.forEach(t=>{
    const r = tradePnl(t).pts / (t.risk_points||1);
    if(r < -2) buckets["< -2R"].push(t);
    else if(r <= -1) buckets["[-2R, -1R]"].push(t);
    else if(r < 0) buckets["(-1R, 0)"].push(t);
    else if(r <= 1) buckets["[0, 1R]"].push(t);
    else if(r <= 2) buckets["(1R, 2R]"].push(t);
    else buckets["> 2R"].push(t);
  });
  const total=trades.length||1;
  let rows="";
  Object.entries(buckets).forEach(([k,arr])=>{
    if(!arr.length) return;
    const avgUsd = arr.reduce((a,t)=>a+tradePnl(t).usd,0)/arr.length;
    rows+=`<tr><td>${k}</td><td class="num">${arr.length}</td><td class="num">${pct(arr.length/total)}</td><td class="num ${clr(avgUsd)}">$${fmt(avgUsd)}</td></tr>`;
  });
  body.innerHTML=rows||'<tr><td colspan="4" class="note">No data</td></tr>';
}

function renderTradeLog(){
  const trades = getFiltered();
  const body=$("tradeLogBody");
  let rows="";
  trades.forEach(t=>{
    const p = tradePnl(t);
    const rc = p.usd>=0?"win":"loss";
    rows+=`<tr>
      <td>${t.date}</td>
      <td><span class="badge ${t.session}">${SESSION_LABELS[t.session]||t.session}</span></td>
      <td>${t.direction.toUpperCase()}</td>
      <td class="num">${fmt(t.entry)}</td>
      <td class="num">${fmt(t.stop)}</td>
      <td class="num">${fmt(t.risk_points)}</td>
      <td class="num ${rc}">${fmt(p.pts)}</td>
      <td class="num ${rc}">$${fmt(p.usd)}</td>
      <td class="num">${fmt(p.pts/(t.risk_points||1))}R</td>
      <td>${t.exit_type}</td>
    </tr>`;
  });
  body.innerHTML=rows||'<tr><td colspan="10" class="note">No trades</td></tr>';
}

/* ── Master Recalc ────────────────────────────────────── */
function recalc(){
  const trades = getFiltered();
  const stats = calcStats(trades);
  renderStats(stats);
  renderChart(stats);
  renderSessionTable();
  renderDOW();
  renderYears();
  renderOutcomes();
  renderRDist();
  renderTradeLog();
}

/* ── Event Wiring ─────────────────────────────────────── */
function initDates(){
  if(!TRADES.length) return;
  const dates = TRADES.map(t=>t.date).sort();
  $("fromDateInput").value=dates[0];
  $("toDateInput").value=dates[dates.length-1];
}

function applyRange(range){
  if(!TRADES.length) return;
  const dates = TRADES.map(t=>t.date).sort();
  const last = dates[dates.length-1];
  const lastD = new Date(last);
  let from = dates[0];
  if(range==="ytd") from = lastD.getFullYear()+"-01-01";
  else if(range==="1y"){const d=new Date(lastD);d.setFullYear(d.getFullYear()-1);from=d.toISOString().slice(0,10);}
  else if(range==="3y"){const d=new Date(lastD);d.setFullYear(d.getFullYear()-3);from=d.toISOString().slice(0,10);}
  else if(range==="5y"){const d=new Date(lastD);d.setFullYear(d.getFullYear()-5);from=d.toISOString().slice(0,10);}
  else if(range==="10y"){const d=new Date(lastD);d.setFullYear(d.getFullYear()-10);from=d.toISOString().slice(0,10);}
  $("fromDateInput").value=from;
  $("toDateInput").value=last;
  $("timeframePreset").value=range;
  recalc();
}

document.querySelectorAll(".range-pill").forEach(btn=>{
  btn.addEventListener("click",()=>{
    document.querySelectorAll(".range-pill").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
    applyRange(btn.dataset.range);
  });
});

document.querySelectorAll(".mode-pill").forEach(btn=>{
  btn.addEventListener("click",()=>{
    document.querySelectorAll(".mode-pill").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
    mode = btn.dataset.mode;
    recalc();
  });
});

document.querySelectorAll(".session-pill").forEach(btn=>{
  btn.addEventListener("click",()=>{
    document.querySelectorAll(".session-pill").forEach(b=>b.classList.remove("active"));
    btn.classList.add("active");
    activeSession = btn.dataset.session;
    $("portfolio-filters").style.display = activeSession==="PORTFOLIO"?"flex":"none";
    recalc();
  });
});

["contractsInput","equityInput","slippageInput","commissionInput","fromDateInput","toDateInput"].forEach(id=>{
  $(id).addEventListener("input",recalc);
});

$("timeframePreset").addEventListener("change",function(){
  document.querySelectorAll(".range-pill").forEach(b=>b.classList.remove("active"));
  applyRange(this.value);
});

document.querySelectorAll(".portfolio-filter").forEach(cb=>{
  cb.addEventListener("change",recalc);
});

/* ── Init ─────────────────────────────────────────────── */
initDates();
recalc();
</script>
</body>
</html>"""
