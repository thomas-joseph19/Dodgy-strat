# DodgysDD IFVG Automation Project

## Core Value
Automate the DodgysDD Inversion Fair Value Gap (IFVG) Strategy with zero hindsight bias, specifically for NQ (Nasdaq) 1-minute data.

## What This Is
A backtesting and signal generation engine for a price action/Smart Money Concepts (SMC) trading strategy. The core mechanic relies on liquidity sweeps, Fair Value Gaps (FVG), and Inverted FVGs (IFVG) to trigger trades toward the next liquidity pool (Draw on Liquidity - DOL). It needs to take 1-minute NQ OHLCV parquet data, calculate swings without hindsight bias, handle specific stop losses (Fail Stop, Narrow Stop, Swing Stop), and output accurate backtest metrics using Plotly visualizations for each trade.

## Key Decisions
| Decision | Rationale | Outcome |
|----------|-----------|---------|
| No Hindsight Bias | To prevent false results, swing highs/lows must only be confirmed `N` candles *after* they occur. | Standardized math models. |
| Plotly Charting per Setup | Matplotlib can't be zoomed. We need to zoom into 1-minute wicks to verify trade validity. | Output HTML files per trade. |
| Setup-by-setup Engine | Running trade resolution independently is simpler and aligns with the strategy's non-overlapping focus. | Simpler engine design. |
| Dynamic Position Sizing | Risk 1% of simulated $100k account per trade to reflect real performance. | Precise contract calculation. |

## Evolution
- **v1.0 (Current)**: High-performance mechanical backtest engine with 1H HTF swept liquidity context.
- **v2.0 (Planned)**: Machine Learning optimization for signal filtering and predictive setup grading.

## Milestone V2: Machine Learning Optimization
**Goal**: Implement a predictive layer that grades trade setups before entry to increase Win Rate and reduce drawdown.
- **Features**: Quantitative price action structural features.
- **Modeling**: XGBoost/Random Forest classification.
- **Validation**: Walk-forward analysis and Monte Carlo stress testing.
