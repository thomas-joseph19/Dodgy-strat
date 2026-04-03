---
phase: 3
wave: 3
depends_on: ["02-PLAN.md"]
files_modified:
  - "src/signal_generator.py"
autonomous: true
requirements_addressed:
  - "SIG-02"
  - "SIG-04"
---

# Phase 3: Signal Engine - Wave 3

<objective>
To implement Continuation Entry validation leveraging the 50% displacement retracement constraints and active directional bias monitoring.
</objective>

<must_haves>
- Leg calculation derived dynamically from Sweep Extrema to the Reversal IFVG trigger close.
- Bias continuity for re-entries until DOL hit or leg invalidated.
</must_haves>

<tasks>

<task>
<description>Implement Continuation Logic and Bias Memory</description>
<action>
In `src/signal_generator.py` under `SignalGenerator`, add tracking for active directional bias. When a valid Reversal fires, remember the `leg_start` and `leg_end`. Check subsequent IFVGs appearing in the SAME direction of the bias to see if price hit `(leg_start + leg_end) / 2`. If retracement condition is met, and constraints hold (DOL not hit, leg limit not broken), emit a new `TradeSetup` with `ModelType.CONTINUATION` to the registry. Break bias memory when DOL is hit or leg limit broken.
</action>
<read_first>
- src/signal_generator.py
- .planning/phases/03-signal-engine/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `SignalGenerator` class tracks displacement models (`leg_start`, `leg_end`).
- Check `50%` midpoint logic works prior to emitting `ModelType.CONTINUATION` signals.
- `python -m py_compile src/signal_generator.py` exits 0.
</acceptance_criteria>
</task>

</tasks>

## Verification
- Code passes syntax check.
