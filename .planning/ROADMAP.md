# Roadmap

## [v1.0 - Institutional Backtest Engine](milestones/v1-ROADMAP.md) [SHIPPED]
*High-performance 1min backtest engine with 1H HTF swept liquidity context and limit order entry logic.*

## Phase 8: ML Feature Engineering & Structural Extraction [DEPRIORITIZED]
- **Goal:** Transform price action (sweeps, FVGs, momentum) into quantified features for model training.
- **Status:** ML pipeline deprioritized in favor of live trading infrastructure.

## Phase 9: Data Labeling & Set Partitioning [DEPRIORITIZED]
- **Goal:** Label historical setups as Success/Fail and create Training, Validation, and OOS Testing sets.
- **Status:** ML pipeline deprioritized in favor of live trading infrastructure.

## Phase 10: Model Training & Signal Filtering [DEPRIORITIZED]
- **Goal:** Train a classification model (XGBoost/RF) to predict trade success probability and filter low-probability signals.
- **Status:** ML pipeline deprioritized in favor of live trading infrastructure.

## Phase 11: Monte Carlo Simulation & Sensitivity Analysis [DEPRIORITIZED]
- **Goal:** Run stress tests and trade reshuffling to verify strategy robustness across different market regimes.
- **Status:** ML pipeline deprioritized in favor of live trading infrastructure.

### Phase 12: 10-Year Mechanical Backtest with Interactive HTML Dashboard [COMPLETED]
- **Goal:** Execute a multi-year high-fidelity simulation and visualize institutional metrics.
- **Success:** Final 10-year report generated with audited performance stats.

### Phase 13: ML Signal Enhancement with Synthetic Gamma & EOD Options Data [COMPLETED]
- **Goal:** Integrate Synthetic GEX levels and train XGBoost filter via Optuna.
- **Success:** Feature extraction pipeline operational; XGBoost model achieving > 0.60 AUC on walk-forward validation.

### Phase 14: BBO Microstructure Signal Integration for Entry Optimization [NEXT]
- **Goal:** Incorporate 1-second BBO bid/ask imbalance into entry gating.
- **Success:** Order book pressure features integrated into the ML feature vector.

### Phase 15: Dual-Strategy Parallel Backtest with Combined Performance Dashboard (Daniel + LG Model) [COMPLETED]
- **Goal:** Run parallel backtest of Daniel + ORB strategies with merged trade stream and Monte Carlo simulation.
- **Success:** Combined HTML dashboard with dynamic sizing and MC confidence intervals.

### Phase 16: Quantower API Integration & Multi-Strategy Live Bridge [SHELVED]
**Reason:** Pivoted to NinjaTrader Bridge for better stability and execution speed.

### Phase 17: Multi-Strategy Live Integration (Mechanical) [COMPLETED]
- **Goal:** Port Daniel and ORB logic to live runners using Rithmic data and NinjaTrader execution.
- **Success:** Mechanical signals triggering orders in NinjaTrader SIM.

### Phase 18: NinjaTrader Live Bridge Implementation [COMPLETED]
- [x] **T18.1: NinjaScript Python Bridge Strategy** (`PythonSignalStrategy.cs`)
- [x] **T18.2: Python Live Engine** (`live/engine.py`)
- [x] **T18.3: Rithmic Data Feed Integration** (`live/rithmic_bridge.py`)
- [x] **T18.4: Environment Setup & Setup Guide** (`.env` & `SETUP.md`)

### Phase 19: Prop Firm Safety Guard [COMPLETED]
- **Goal:** Implement daily loss limit enforcement in the NinjaTrader bridge to prevent MFFU account termination.
- **Success:** Bridge refuses new signals once cumulative daily P&L exceeds configurable `MAX_DAILY_LOSS` threshold.
- **Requirements:** REQ-SAFETY-01

### Phase 20: Quantower Cleanup & Planning Docs Refresh [COMPLETED]
- **Goal:** Remove orphaned Quantower bridge code and update stale planning documentation to reflect the NinjaTrader pivot.
- **Success:** No Quantower references remain in active code; STATE.md, ROADMAP, and phase plans accurately reflect current architecture.
- **Requirements:** REQ-LIVE-01
