# Phase 2: Core Mechanics - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Mechanizing the algorithmic identification of liquidity sweeps (BSL/SSL), Fair Value Gaps (FVGs), and Inverted FVG (IFVG) triggers using the pandas DataFrame structure. This phase establishes the logic engine without taking trades.

</domain>

<decisions>
## Implementation Decisions

### Technical Foundation
- **D-01 Identification Approach:** Use **vectorized operations** heavily over pandas DataFrames. This ensures high-performance backtesting. 
- **D-02 Data Structures:** Use hybrid data structures:
  - Vectorized columns on the DataFrame (e.g. `sweep_bull`, `fvg_bear_top`) for fast row-based checks.
  - Dedicated object data structures (e.g. `List[FVG]`) for state tracking where array-wise logic becomes too convoluted.

### Strategy Implementation Truths
- **D-03 Liquidity Sweep Strictness:** 
  - A *wick* beyond the liquidity level is sufficient (flag as `WICK_SWEEP`), while a body close is tracked as a stronger signal (`BODY_SWEEP`).
  - **Expiry/Validity:** The sweep is valid until the price creates a new extreme in the same direction or a max N-bar lookback (configurable) is reached. If price puts in a new extreme before inversion, the sweep context is stale.
- **D-04 FVG & Stacked FVGs:**
  - **Single:** One clear FVG with a subsequent body inversion is fully valid.
  - **Stacked (Consecutive):** FVGs in the exact same direction are grouped into a "Series/Stack" provided no candle body has closed in the gap space between them.
  - **Zone Construction via Stack:**
    - `ZONE_TOP` = Max of all individual `FVG_TOP`s
    - `ZONE_BOTTOM` = Min of all individual `FVG_BOTTOM`s
  - **Inversion Criteria:** A candle **BODY** must close above the `ZONE_TOP` (for longs) or below the `ZONE_BOTTOM` (for shorts) of the *entire* combined zone.

### Agent's Discretion
- Code modularization (e.g., placing sweep logic vs FVG logic in separate functions/modules).
- Array representations mapping exact OHLC values vs using `np.where`.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definitions
- `.planning/PROJECT.md` — Core context.
- `.planning/REQUIREMENTS.md` — Specifically CORE-01, CORE-02, CORE-03, CORE-04, CORE-05.
- `src/config.py` — Location to embed new strategy configuration items (lookback limits, min pivot bars for liquidity).
- `src/data_loader.py` — Shows the input datatypes returned for OHLCV indexing.
</canonical_refs>
