# Phase 3: Signal Engine - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Phase Boundary

Taking raw mechanical events (sweeps, FVGs, IFVGs) from Phase 2 and converting them into distinct, structured TradeSetup objects. This establishes exactly when a valid Reversal or Continuation signal fires and pre-calculates the execution boundaries (stops, targets).

</domain>

<decisions>
## Implementation Decisions

### 1. Continuation Model Retracement
- **D-01 Displacement Leg Start:** Defined as the sweep extreme (lowest LOW of the sweep candle for SSL sweeps; highest HIGH for BSL sweeps).
- **D-02 Displacement Leg End:** Defined as the **close of the IFVG-confirming candle** on the reversal leg (gives a deterministic, non-lookahead anchor point).
- **D-03 50% Level Calculation:** `(leg_start + leg_end) / 2`. The retracement must touch or exceed this.
- **D-04 Retracement Expiry:** Active until price violates leg_start, hits DOL directly, or MAX_BARS limit is reached.

### 2. Mechanical Validity (SIG-03)
- **D-05 Internal Structure vs DOL:** Tracked entirely separately.
  - *Internal H/L:* Used for entry validity checks (must not have hit before inversion completes) and Break-Even triggers.
  - *DOL (Draw on Liquidity):* The resting BSL/SSL pool that dictates the final Target in the trade. 
- **D-06 Validity Logic:** If nearest directional internal extreme < DOL target, setup is completely mechanically valid. If internal extreme is already hit prior to entry confirm => flag as `ADVANCED` grade or invalid, but do not assign `MECHANICAL` grade.

### 3. Signal Output & Object Representation
- **D-07 Setup Object schema:** Use a strict `TradeSetup` python Dataclass instead of dataframe booleans. The setup class stores identity, direction, price levels (entry, type of stop, target, BE trigger, fail_stop_level), and supporting structures.
- **D-08 SetupRegistry:** Implement a `SetupRegistry` class to act as the communication boundary. The Signal Generator adds `TradeSetup` objects to the registry. The downstream Execution Engine poll/consumes this registry. Signal generator calculates levels; it does **not** manage positions.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Definitions
- `.planning/PROJECT.md` — Core requirements and execution separation.
- `.planning/REQUIREMENTS.md` — Specifically SIG-01, SIG-02, SIG-03, SIG-04.
- `src/core.py` — The base mechanics generator providing the raw arrays.
</canonical_refs>
