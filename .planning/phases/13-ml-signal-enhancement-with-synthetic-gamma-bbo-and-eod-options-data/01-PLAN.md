---
description: Implement Synthetic Gamma engine, XGBoost pipeline with Optuna, and interactive ML visual metrics dashboard.
dependencies: ["Phase 12"]
gap_closure: false
---

# Phase 13: ML Signal Enhancement with Synthetic Gamma & EOD Options Data

## Objective
Implement a robust Machine Learning pipeline that processes QQQ EOD options data to compute NQ synthetic gamma exposure (GEX) levels. These levels will serve as novel structural setup triggers. An XGBoost model will be trained using these gamma features (along with existing mechanical features) and hyperparameter-tuned via Optuna. The pipeline must generate rich, interactive HTML visual metrics (ROC, Feature Importance, etc.) without actively running the heavy ML execution loop immediately (dry-run logic in place as requested).

## Tasks

### 1. GEX Engine Implementation (`src/gamma.py`)
- **Action**: Create a new module to process `ML data/parquet_qqq/options_YYYY.parquet`.
- **Details**:
  - Implement function to load and combine daily QQQ options data.
  - Compute NQ conversion ratio using `underlying_prices.parquet`.
  - Calculate GEX for strikes (using formula: `gamma * OI * contractMultiplier * spot^2`).
  - Implement bucketing by expiry (0-7 DTE, Front-month, All-expirations).
  - Extract daily `GEX_FLIP` (net zero gamma) and `GAMMA_CLUSTER` (highest positive/negative `gamma * OI` nodes).
- **Validation**: Ensure `gamma.py` successfully reads a single test parquet file and outputs a cleanly formatted DataFrame of daily NQ gamma levels.

### 2. Backtest Engine Integration (`src/backtest_engine.py` & `main.py`)
- **Action**: Inject synthetic gamma levels into the simulation state.
- **Details**:
  - Map `GAMMA_CLUSTER` and `GEX_FLIP` daily levels into the simulation's `LiquidityLevel` tracking system alongside standard HTF swing levels.
  - Define new setups: `GAMMA_REVERSAL` and `GEX_FLIP` interaction patterns for IFVG entries.
- **Validation**: Run the backtest engine over a 1-month subset and verify new `LiquidityLevel` properties are recognized.

### 3. ML Feature Extraction Logic (`src/ml_features.py`)
- **Action**: Build state extraction class for trade entries.
- **Details**:
  - Distance metrics: Points to nearest `GAMMA_CLUSTER`, points from `GEX_FLIP`.
  - Regime indicators: Is dealer gamma positive or negative?
  - Existing attributes: FVG size, sweep quality, risk/reward.
- **Validation**: Ensure feature vectors are correctly formed (no NaNs or mismatched dimensions) at simulated trade triggers.

### 4. XGBoost & Optuna Pipeline Sandbox (`src/ml_pipeline.py`)
- **Action**: Create the XGBoost training and Optuna study architecture.
- **Details**:
  - Define `OptunaObjective`, search space boundaries (learning_rate, max_depth, reg_alpha, etc.), and Expanding-Window Walk-Forward validation methodology.
  - *Per user instruction, the actual massive data processing execution is omitted initially; only the architecture/dry-run capabilities are hooked up.*
- **Validation**: Ensure the module compiles and the Optuna study initializes correctly.

### 5. Visual ML Metrics Output (`src/ml_visualizations.py` & `src/dashboard.py`)
- **Action**: Generate interactive HTML representations of model outputs.
- **Details**:
  - Implement generation of Feature Importance bar charts using Chart.js.
  - Render ROC / AUC and Precision-Recall evaluation curves.
  - Create a side-by-side equity curve generator to compare pure mechanical vs. ML-filtered equity.
- **Validation**: Run a dummy dataset through `ml_visualizations.py` to ensure it outputs a fully rendered `ml_dashboard.html` that adheres to the established premium glassmorphic UI aesthetics.
