# Phase 2: Core Mechanics - Discussion Log

**Date:** 2026-04-02
**Phase:** Phase 2: Core Mechanics

## Q1: Identification Approach
**User selection:** Vectorized operations (Recommended for backtesting)

## Q2: Data Structures for Features
**User selection:** Hybrid — Both columns for fast vectorized checks and objects for logic states (Recommended)

## Q3: Liquidity Sweep strictness
**User context provided:**
The PDF says price must make a "clear sweep of an obvious liquidity pool" and that "some form of BSL or SSL has to be taken." It does not specify whether the reversal must be immediate.

**User selection:** 
- Wick sweep is sufficient (standard `WICK_SWEEP`), body close is a stronger signal (`BODY_SWEEP`).
- Sweep requires no intervening fresh extreme in the same direction before the IFVG completes. If a fresh extreme happens, the previous sweep context breaks. Expiry loop logic applies over N-bar max.

## Q4: Stacked FVG Construction
**User context provided:**
Consecutive gaps combined and used the exact same way. Wait for inversion through exact zone parameters.

**User selection:** 
- Adjacency Rule: Two FVGs are stacked if they are in the exact same direction and NOT separated/filled by an intervening candle body close.
- Inversion Trigger: Body must close across the *entire* combined zone (Max of Top to Min of Bottom).
- One FVG is fully valid by itself; stacking logic applies only if additional are found consecutively.
