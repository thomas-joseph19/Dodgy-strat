---
milestone: v2.0
audited: 2026-04-21T16:41:00-04:00
status: gaps_found
scores:
  requirements: 8/11
  phases: 3/7
  integration: 4/6
  flows: 2/3
gaps:
  requirements:
    - id: "REQ-LIVE-01"
      status: "partial"
      phase: "17"
      description: "Daniel Mechanical Live Runner needs migration from Quantower to NinjaTrader bridge"
      evidence: "src/live/daniel_mechanical_runner.py still imports QuantowerLive (broken import), not live.ninja_bridge"
    - id: "REQ-LIVE-02"
      status: "partial"
      phase: "17"
      description: "ORB Live Runner exists in Python (live/orb_processor.py) but Node.js runner (T17.2) is not implemented"
      evidence: "No strategies/lg_model/src/live/ directory exists; ORB runs through Python engine only"
    - id: "REQ-SAFETY-01"
      status: "unsatisfied"
      phase: "16/17"
      description: "Prop Firm Guard (daily loss hard-limit) not implemented in any bridge"
      evidence: "Neither PythonSignalStrategy.cs nor ninja_bridge.py has max daily loss checking"
  integration:
    - from: "src/live/daniel_mechanical_runner.py"
      to: "live/ninja_bridge.py"
      issue: "Dead code — runner imports QuantowerLive (port 8081) but the active bridge is NinjaBridge (port 6789)"
    - from: "src/bridge/QuantowerBridge/"
      to: "live/"
      issue: "Orphaned Quantower C# bridge project still in repo — creates confusion about which bridge is active"
  flows: []
tech_debt:
  - phase: "16-quantower-integration"
    items:
      - "Entire Quantower bridge codebase (src/bridge/QuantowerBridge/, src/live/quantower_*.py, src/quantower_bridge/) is orphaned — should be removed or archived"
      - "Phase 16 PLAN still shows incomplete tasks (T16.3, T16.4, T16.7, T16.8) that are now superseded by the NinjaTrader approach"
  - phase: "17-multi-strategy-live-integration"
    items:
      - "daniel_mechanical_runner.py has hardcoded session levels instead of dynamic detection"
      - "17-PLAN.md still references Quantower TCP Bridge (port 8081) and should be updated to reference NinjaBridge"
  - phase: "general"
    items:
      - "ML files (ml_features.py, ml_pipeline.py, ml_visualizations.py) were deleted in latest pull but ROADMAP phases 8-11 still reference ML pipeline as PENDING"
      - "STATE.md references 'Quantower' and is outdated — does not reflect NinjaTrader pivot"
      - "pip dependency conflict: async-rithmic requires protobuf 4.x but cmdop requires protobuf ≥5.29"
      - "pip dependency conflict: async-rithmic requires websockets 14.x but openbb/fastmcp require ≥15.0"
      - "Phase 6 directory is empty (.gitkeep only) — no plans or artifacts"
      - "Phase 14 directory is empty (.gitkeep only) — no plans or artifacts"
      - "No SUMMARY.md files exist for any phase"
---

# v2.0 Milestone Audit — NinjaTrader Live Bridge

**Audited:** 2026-04-21  
**Status:** ⚠ GAPS FOUND  
**Scope:** Phases 12–18 (Backtest → Live Execution)

---

## 1. Phase Status Summary

| Phase | Name | Status | VERIFICATION.md | SUMMARY.md |
|-------|------|--------|----------------|------------|
| 06 | Institutional Metrics | EMPTY | ❌ missing | ❌ missing |
| 12 | 10-Year Mechanical Backtest | COMPLETED (roadmap) | ❌ missing | ❌ missing |
| 13 | ML Signal Enhancement | COMPLETED (roadmap) | ✅ passed | ❌ missing |
| 14 | BBO Microstructure | NEXT (roadmap) | ❌ missing | ❌ missing |
| 15 | Dual-Strategy Backtest | COMPLETED (implied) | ✅ passed | ❌ missing |
| 16 | Quantower Integration | SHELVED | ❌ N/A | ❌ N/A |
| 17 | Multi-Strategy Live | IN PROGRESS | ❌ missing | ❌ missing |
| 18 | NinjaTrader Bridge | COMPLETED (roadmap) | ❌ missing | ❌ missing |

> [!WARNING]
> No SUMMARY.md files exist for any phase. This is a documentation gap across the entire project.

---

## 2. Requirements Coverage (v1.0 Backtest Engine)

All 11 original REQUIREMENTS.md items were scoped for v1.0 (the backtest engine). These are all **backtest-related** and appear to be satisfied by the existing `main.py`, `src/core.py`, `src/execution.py`, `src/fvg.py`, `src/liquidity.py`, `src/swings.py`, `src/vectorized.py`, and `src/dashboard.py`.

| # | Requirement | Status | Evidence |
|---|------------|--------|----------|
| 1 | Read 1-min NQ OHLCV from parquet | ✅ Satisfied | `main.py` loads parquet via pandas |
| 2 | Candle dataclass + pure functions | ✅ Satisfied | `src/core.py` — Candle class |
| 3 | Swing high/low detection | ✅ Satisfied | `src/swings.py` — SwingRegistry |
| 4 | Liquidity Level classification | ✅ Satisfied | `src/liquidity.py` |
| 5 | Liquidity Sweep logic | ✅ Satisfied | `src/liquidity.py` — detect_sweep |
| 6 | FVG detection + stacking | ✅ Satisfied | `src/fvg.py` |
| 7 | IFVG triggers | ✅ Satisfied | `src/fvg.py` + `src/vectorized.py` |
| 8 | Execution Engine | ✅ Satisfied | `src/execution.py` |
| 9 | Stop management | ✅ Satisfied | `src/execution.py` — TradeState |
| 10 | Backtesting metrics | ✅ Satisfied | `src/metrics.py` + `src/dashboard.py` |
| 11 | Plotly HTML trade charts | ✅ Satisfied | `src/plotting.py` + `src/dashboard.py` |

> [!NOTE]
> v1.0 backtest requirements are all satisfied. The current work is post-milestone (v2.0+ live trading).

---

## 3. Cross-Phase Integration Check

### ✅ Working Integration Points

| From | To | Status |
|------|----|--------|
| `live/engine.py` | `src/core.py` (Candle) | ✅ Imports verified |
| `live/engine.py` | `src/execution.py` (Direction, TradeSetup) | ✅ Imports verified |
| `live/ninja_bridge.py` | `live/engine.py` (LiveEngine) | ✅ Imports verified |
| `live/orb_processor.py` | `src/execution.py` | ✅ Imports verified |
| `live/dodgy_processor.py` | `src/fvg.py`, `src/liquidity.py`, `src/swings.py` | ✅ Imports verified |
| `live/gex_live.py` | yfinance | ✅ Imports verified |

### ⚠ Broken Integration Points

| From | To | Issue | Severity |
|------|----|-------|----------|
| `src/live/daniel_mechanical_runner.py` | `src/live/quantower_live.py` | Imports `QuantowerLive` which fails — class renamed or removed | 🔴 Critical |
| `src/live/daniel_mechanical_runner.py` | N/A | Entire file is dead code — uses old Quantower bridge, not NinjaTrader | 🟡 Medium |
| `src/bridge/QuantowerBridge/*.cs` | N/A | Orphaned C# project — superseded by `live/NinjaScript/` | 🟡 Medium |

### ✅ End-to-End Flow (NinjaTrader Path)

```
NinjaTrader Chart (1m NQ)
  → PythonSignalStrategy.cs sends BAR JSON over TCP
    → NinjaBridge._process_message() parses bar
      → LiveEngine.on_bar() feeds to OrbProcessor + DodgyProcessor
        → Signal fires → NinjaBridge.on_trade_opened()
          → JSON SIGNAL sent back to NinjaTrader
            → PythonSignalStrategy.ExecuteSignal() submits order
```

**This flow is architecturally complete and all imports validate.** ✅

---

## 4. Critical Gaps (Blockers Before Going Live)

### Gap 1: No Prop Firm Safety Guard 🔴
Neither `PythonSignalStrategy.cs` nor `ninja_bridge.py` implements a daily loss limit check. For MyFundedFutures, exceeding the daily loss limit results in account termination.

**Recommendation:** Add a `MAX_DAILY_LOSS` parameter to `NinjaBridge` that tracks cumulative P&L from `on_trade_closed()` and refuses new signals once the threshold is hit.

### Gap 2: Dead Quantower Runner 🟡
`src/live/daniel_mechanical_runner.py` imports `QuantowerLive` which doesn't exist/doesn't work. This file was committed to main but cannot run.

**Recommendation:** Either delete this file or refactor it to use `live.ninja_bridge.NinjaBridge`. The live Dodgy signal logic already exists in `live/dodgy_processor.py` and is wired into the NinjaTrader engine — this duplicate runner is unnecessary.

### Gap 3: Stale Planning Docs 🟡
- `17-PLAN.md` references Quantower TCP Bridge (port 8081)
- `STATE.md` doesn't reflect the NinjaTrader pivot
- Roadmap phases 8-11 (ML) are marked PENDING but the ML files were deleted

**Recommendation:** Update `STATE.md`, `17-PLAN.md`, and ROADMAP to accurately reflect current state.

---

## 5. Tech Debt Summary

| Category | Count | Items |
|----------|-------|-------|
| Orphaned Code | 5 | Quantower bridge (C#), quantower_live.py, quantower_tcp_client.py, daniel_mechanical_runner.py, src/quantower_bridge/ |
| Stale Documentation | 3 | STATE.md, 17-PLAN.md, ROADMAP phases 8-11 |
| Missing Documentation | 7 | No SUMMARY.md for any phase, missing VERIFICATIONs for phases 12/17/18 |
| Dependency Conflicts | 2 | protobuf version mismatch, websockets version mismatch |
| Empty Phase Dirs | 2 | Phase 6, Phase 14 |

**Total: 19 items across 5 categories**

---

## 6. Pre-Live Readiness Checklist

| Item | Status | Notes |
|------|--------|-------|
| Python live engine imports | ✅ Pass | All modules load cleanly |
| NinjaScript strategy compiles | ⚠ Untested | Must be compiled in NT8 editor (F5) |
| .env file exists | ✅ Pass | Created with correct defaults |
| requirements.txt complete | ✅ Pass | python-dotenv, async-rithmic installed |
| Prop Firm daily loss guard | ❌ Missing | **Must implement before real account** |
| TCP protocol documented | ✅ Pass | SETUP.md + inline docstrings |
| Orphaned Quantower code cleaned | ❌ Not done | Confusion risk |
| SIM paper trading validated | ❌ Not done | Required: minimum 1 week paper trading |
