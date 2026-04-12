# Phase 13: ML Signal Enhancement with Synthetic Gamma & EOD Options Data

## Scope

This phase focuses **exclusively** on QQQ EOD options data (2011–2025) to derive synthetic gamma exposure (GEX) levels for NQ, integrate them into the backtest engine as new setup triggers, and build an XGBoost ML filter on top of all setups. BBO microstructure data is deferred to Phase 14.

## Decisions

### 1. Synthetic Gamma Levels — Both Approaches
- **GEX Flip Calculation**: Aggregate `gamma × OI × contractMultiplier × spot²` across strikes to compute net dealer positioning. Identify the **GEX flip level** (price where net gamma = 0) — this is where dealer hedging flips from suppressing to amplifying moves.
- **High-Gamma Strike Clustering**: Identify individual strikes with extreme `gamma × OI` concentration. These act as magnet/barrier levels (price tends to pin near positive gamma clusters and repel from negative gamma clusters).

### 2. Interaction with Existing Engine — Filter + New Setups
- **ML Filter (Goal A)**: Keep existing IFVG sweep logic as the signal generator. Use gamma-derived features as inputs to an XGBoost classifier that gates which signals to take (probability threshold).
- **New Setup Identification (Goal B)**: Gamma levels become additional liquidity targets in the engine. When price sweeps a gamma cluster AND an IFVG inverts → new `GAMMA_REVERSAL` setup type. GEX flip approaches generate a separate `GEX_FLIP` model type.

### 3. BBO Data → Deferred to Phase 14
BBO microstructure (bid-ask spread, order book imbalance, sub-minute momentum) is parked for Phase 14: "BBO Microstructure Signal Integration for Entry Optimization."

### 4. QQQ → NQ Price Mapping
- Use **direct strike scaling with daily ratio correction**.
- Daily ratio = NQ close / (QQQ close × multiplier) from `underlying_prices.parquet`.
- All QQQ strikes are projected into NQ price space using this ratio before GEX aggregation.

### 5. Expiry Bucketing — ML-Optimized
- Compute GEX across **multiple expiry windows simultaneously**:
  - Bucket A: 0–7 DTE (weekly/0DTE — highest gamma sensitivity)
  - Bucket B: Front-month only (most liquid, institutional standard)
  - Bucket C: All expirations weighted by OI (full picture)
- Each bucket produces separate features (gex_flip_A, gex_flip_B, gex_flip_C, etc.)
- XGBoost feature importance + Optuna hyperparameter tuning determines which bucket(s) carry the most predictive signal.
- The model learns the optimal expiry weighting automatically — no manual tuning.

### 6. Gamma Level → Trade Setup Logic
1. Each trading day, compute daily GEX profile from prior day's EOD options snapshot.
2. Identify: **GEX flip level** (net gamma = 0) + **top-N high-gamma clusters** (sorted by |gamma × OI|).
3. These levels are injected into the backtest engine as additional `LiquidityLevel` objects with `quality="GAMMA_CLUSTER"` or `quality="GEX_FLIP"`.
4. Sweep detection runs on gamma levels exactly like HTF swing levels.
5. New setup types:
   - `GAMMA_REVERSAL`: Price sweeps a gamma cluster + IFVG inversion → entry at IFVG edge.
   - `GEX_FLIP`: Price crosses the GEX flip level from positive to negative gamma territory (amplification zone) + structural confirmation.

### 7. ML Model
- **Algorithm**: XGBoost binary classifier (win/loss prediction).
- **Training features** (per-setup):
  - Distance to nearest gamma cluster (NQ points)
  - GEX regime: positive or negative dealer gamma at entry price
  - GEX flip distance (points from nearest flip level)
  - Daily IV rank (percentile rank of ATM IV vs trailing 252-day window)
  - Put/call OI ratio (near-the-money strikes)
  - Net gamma exposure magnitude (normalized)
  - Existing mechanical features: sweep quality, FVG size, risk/reward, momentum score, session, day of week
- **Label**: 1 = trade hit target, 0 = stopped out / expired
- **Optimization**: Optuna for hyperparameters (max_depth, learning_rate, n_estimators, min_child_weight, subsample, colsample_bytree, gamma, reg_alpha, reg_lambda)
- **Objective**: Maximize walk-forward Sharpe ratio (not accuracy)
- **Validation**: Expanding-window walk-forward with 1-year OOS blocks (no lookahead)

### 8. Data Sources
| Source | Path | Coverage | Notes |
|---|---|---|---|
| QQQ EOD Options | `ML data/parquet_qqq/options_YYYY.parquet` | 2011–2025 | Strike, delta, gamma, theta, vega, IV, OI, volume |
| QQQ Underlying | `ML data/parquet_qqq/underlying_prices.parquet` | 2011–2025 | Daily close for NQ ratio calc |
| NQ 1-min OHLC | `data/nq_1min_10y.parquet` | ~2015–2025 | Existing backtest data |

### 9. Implementation Order
1. **GEX Engine** (`src/gamma.py`): Load EOD options → compute GEX profile → output daily gamma levels in NQ space
2. **Engine Integration** (`main.py`): Inject gamma levels as `LiquidityLevel` objects in the daily loop
3. **Feature Extraction** (`src/ml_features.py`): At each setup, compute gamma-derived features
4. **XGBoost Pipeline** (`src/ml_pipeline.py`): Train/validate with Optuna, walk-forward evaluation
5. **Dashboard Update & Visual ML Metrics** (`src/dashboard.py` & `src/ml_visualizations.py`): 
   - Integrate ML-filtered vs Mechanical baseline equity curves in the main HTML dashboard
   - Auto-generate interactive HTML visual metrics for the ML pipeline (Feature Importance charts, ROC/AUC curves, Precision-Recall curves, and Confusion Matrices) after every run.

### 10. Deferred Ideas
- BBO spread/imbalance features (Phase 14)
- Real-time GEX computation from live options feed (production deployment)
- Multi-instrument gamma (SPX options for ES correlation)
- Intraday options data for dynamic GEX updates
