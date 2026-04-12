# Roadmap

## [v1.0 - Institutional Backtest Engine](milestones/v1-ROADMAP.md) [SHIPPED]
*High-performance 1min backtest engine with 1H HTF swept liquidity context and limit order entry logic.*

## Phase 8: ML Feature Engineering & Structural Extraction [PENDING]
- **Goal:** Transform price action (sweeps, FVGs, momentum) into quantified features for model training.
- **Success:** Feature generation pipeline creates a normalized training dataset from 10-year historical data.

## Phase 9: Data Labeling & Set Partitioning [PENDING]
- **Goal:** Label historical setups as Success/Fail and create Training, Validation, and OOS Testing sets.
- **Success:** Randomized yet chronologically separated data partitions ready for model input.

## Phase 10: Model Training & Signal Filtering [PENDING]
- **Goal:** Train a classification model (XGBoost/RF) to predict trade success probability and filter low-probability signals.
- **Success:** Model consistently improves Win Rate by removing marginal setups.

## Phase 11: Monte Carlo Simulation & Sensitivity Analysis [PENDING]
- **Goal:** Run stress tests and trade reshuffling to verify strategy robustness across different market regimes.
- **Success:** Confirmed statistical persistence of the strategy under variation of slippage and execution sequence.

### Phase 12: 10-Year Mechanical Backtest with Interactive HTML Dashboard

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 11
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 12 to break down)

### Phase 13: ML Signal Enhancement with Synthetic Gamma, BBO, and EOD Options Data

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 12
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 13 to break down)

### Phase 14: BBO Microstructure Signal Integration for Entry Optimization

**Goal:** [To be planned]
**Requirements**: TBD
**Depends on:** Phase 13
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd-plan-phase 14 to break down)
