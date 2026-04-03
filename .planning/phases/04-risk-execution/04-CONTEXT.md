# Phase 4: Execution Simulation - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Ingesting pre-defined `TradeSetup` objects generated in Phase 3 and actively simulating their outcome over historical OHLC data, calculating fills, exits, dynamic stops, tracking account equity, and producing fully resolved `TradeResult` records.

</domain>

<decisions>
## Implementation Decisions

### 1. Execution Engine Design
- **D-01 Model Architecture:** Setup-by-setup evaluation (independent). Does NOT track multiple positions concurrently or margin limits. Processes each `TradeSetup` chronologically looping forward until an exit condition is met, resolving it completely.
- **D-02 OHLC Exit Conflict Resolution:** Strictly pessimistic. If an OHLC candle could trigger both the stop loss AND the profit target during the same interval, the STOP LOSS is historically assumed to hit first.
- **D-03 Fail Stop Exit Price Assumption:** Since this evaluates against the bar's `close` (acting as a Market Order on Close), the exit fill for a Fail Stop is strictly the actual bar's closing price. (Hard stop operates as the floor and naturally overrides this if hit intra-bar).

### 2. Sizing, Commission & Slippage Models
- **D-04 Dynamic Position Sizing:** Driven by defined `SimulationConfig` targeting a fixed risk boundary (1% risk per trade). Scales contracts to the $1k threshold calculated against the Hard Stop distance at $20.00 a point. Bounded mechanically between 1 and 10 NQ contracts.
- **D-05 Friction Tracking:**
  - Slippage = strictly 1 NQ tick (0.25 points/$5.00) penalized on BOTH sides of the order direction (adjusting entry worse, exit worse), accounting to 0.50 points per complete RT.
  - Commission = $4.00 deducted round-trip (RT) per executed contract on completion.
- **D-06 Break-even Toggling:** Standardly triggers based on the internal H/L mapped by the SignalGenerator, pulling the current hard-stop instantly to the executed entry fill price.

### 3. Session Isolation
- **D-07 Acceptable Engine Bounds:** The evaluation actively limits execution models to standard RTH sessions (09:30 – 16:00 ET) to preserve liquidity integrity around slippage baselines. 
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definitions
- `.planning/PROJECT.md` — Core mechanization constraints.
- `.planning/REQUIREMENTS.md` — Focus on EXEC-01 through EXEC-06 requirements.
- `src/models.py` — Location housing the input object models (`TradeSetup`, `StopType`).
</canonical_refs>
