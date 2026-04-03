# DodgysDD IFVG Strategy Automation

## What This Is

An automated futures trading system based on a rule-based price action strategy known as the DodgysDD Inversion Fair Value Gap (IFVG) Strategy. Everything revolves around waiting for liquidity to be swept, finding a Fair Value Gap (FVG) that gets inverted, and entering in the direction of the inversion toward the next liquidity pool. V1 is fully deterministic, modular, and backtestable.

## Core Value

The system must mechanize the DodgysDD IFVG trading strategy into fully explicit, rule-based logic to enable robust and deterministic backtesting, completely eliminating ambiguity and discretionary steps.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Mechanize the trading strategy logic (liquidity sweeps, FVGs, IFVGs, entries)
- [ ] Implement stop loss rules (fail stop, swing stop, narrow stop)
- [ ] Build a robust backtesting engine supporting slippage, commission, long/short, and avoiding lookahead bias
- [ ] Implement modular system architecture (Data Loader, Signal Generator, Execution Simulator, PnL Tracker, Backtest Engine, Visualization)
- [ ] Parameterize all configuration (thresholds, stop distances, indicators)
- [ ] Create visualization logic (equity curve, trade list, drawdown curve, key metrics)
- [ ] Design for V2 compatibility (easy drop-in for machine learning enhancements later)

### Out of Scope

- Machine Learning features — Deferred to V2. V1 focuses strictly on mechanizing the strategy logic and building the backtest engine.
- Complex discretionary logic without strict mechanical bounds — Must convert any discretionary steps in the strategy into programmatically defined rules.
- Alternate data feeds beyond 1-minute NQ OHLCV — V1 strictly relies only on 1-min NQ OHLCV to keep the scope tight and testing verifiable.

## Context

- **Technical Environment**: Python, pandas/numpy for data handling, matplotlib/plotly for visualization.
- **Data Source**: 1-minute OHLCV data for NQ futures is the primary dataset.
- **Strategy Concept**: Smart Money Concepts (SMC), Fair Value Gaps (FVGs), Liquidity sweep mechanisms.
- **Future Pathway**: Designed so additional data sources and machine learning logic can be easily plugged into the signal generator later.

## Constraints

- **Execution Limit**: V1 must be fully deterministic and backtestable.
- **Data Dependency**: Only utilize 1-minute NQ OHLCV data.
- **Code Quality**: Production-quality Python code with comments and docstrings.
- **Dependency Scope**: Prefer pandas/numpy, matplotlib/plotly. Avoid unnecessary bloat.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Restrict to 1-min NQ OHLCV data only | Minimizes complexity for V1 backtesting and mechanization proof-of-concept. | — Pending |
| Adopt Fail Stop as default Stop Loss | Allows exiting invalid setups quickly to preserve capital without waiting for full stops. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

## Current State

Phase 1 complete — Config management and Data Loader frameworks are established.

---
*Last updated: 2026-04-02 after Phase 1 completion*
