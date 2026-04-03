# Phase 3: Signal Engine - Discussion Log

**Date:** 2026-04-02
**Phase:** Phase 3: Signal Engine

## Q1: Continuation Model Retracement
**User context provided:**
Displacement leg needs a deterministic start and end point. 

**User selection:**
- **LEG_START:** Sweep extreme (lowest low / highest high of the sweep candle).
- **LEG_END:** Close of the IFVG confirming candle on the reversal leg.
- **50% Level:** Derived exactly from `(leg_start + leg_end) / 2`.
- **Expiry:** Stays open until sweep extreme is taken out, DOL hit, or MAX_BARS reached.

## Q2: Mechanical Validity (DOLs vs Internal H/L)
**User context provided:**
Internal highs/lows and DOL pools serve different functions. 

**User selection:**
- **DOL:** Serves as the actual target.
- **Internal H/L:** Represents nearest swing H/L before the DOL. Used for Break-Even triggering and entry validity. If an internal H/L is breached prior to entry confirmation, model falls from MECHANICAL to ADVANCED or becomes invalid.

## Q3: Signal Output Format
**User context provided:**
A boolean column forces downstream logic to recreate bounds for entry, stop, exits, and bias.

**User selection:** 
- Use Object-Oriented **TradeSetup** schemas (with nested `SweepEvent` and `FVGZone`). 
- Signal generator creates objects containing explicit price levels for setup boundaries.
- Emits these generated objects to a **SetupRegistry** class mapping for `pending`, `active`, and `closed` setups, keeping boundaries flawlessly clean perfectly splitting duties between Signaling and Execution mechanisms.
