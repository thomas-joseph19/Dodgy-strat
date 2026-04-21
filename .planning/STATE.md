# Project State

## Current Focus
Phase 19-20: Prop Firm Safety Guard & Quantower Cleanup (Gap Closure from v2.0 Audit)

## Accumulated Context

### Roadmap Evolution
- v1.0 Milestone shipped: Institutional Backtest Engine (Phases 1-7)
- Phase 12 completed: 10-Year Mechanical Backtest with Interactive HTML Dashboard
- Phase 13 completed: ML Signal Enhancement with Synthetic Gamma & EOD Options Data
- Phase 15 completed: Dual-Strategy Parallel Backtest with Combined Performance Dashboard
- Phase 16 shelved: Quantower Integration — pivoted to NinjaTrader Bridge
- Phase 17 in progress: Multi-Strategy Live Integration (Mechanical)
- Phase 18 completed: NinjaTrader Live Bridge Implementation
- Phase 19 completed: Prop Firm Safety Guard (MAX_DAILY_LOSS enforcement)
- Phase 20 in progress: Quantower Cleanup & Planning Docs Refresh

### Architecture Decision: NinjaTrader over Quantower
- **Decision Date:** 2026-04-21
- **Reason:** Better stability, simpler TCP protocol, native Rithmic support
- **Active Bridge:** `live/NinjaScript/PythonSignalStrategy.cs` ↔ `live/ninja_bridge.py`
- **Data Flow:** NT8 → BAR JSON → Python LiveEngine → SIGNAL JSON → NT8 order

### ML Pipeline Status
- Phases 8-11 (ML Feature Engineering through Monte Carlo) are deprioritized
- ML files (`ml_features.py`, `ml_pipeline.py`, `ml_visualizations.py`) were removed
- Phase 13 completed the Synthetic GEX integration which feeds into the live engine

## Quick Tasks Completed
- MC Pipeline Optimization (Node.js workers, batch processing)
- Dashboard 🎲 Monte Carlo tab implementation
- Logic Soundness Audit (Slippage integration, GEX filter fix)
- NinjaTrader environment setup (.env, requirements.txt, python-dotenv)
