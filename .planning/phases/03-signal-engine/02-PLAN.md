---
phase: 3
wave: 2
depends_on: ["01-PLAN.md"]
files_modified:
  - "src/signal_generator.py"
autonomous: true
requirements_addressed:
  - "SIG-01"
  - "SIG-03"
---

# Phase 3: Signal Engine - Wave 2

<objective>
To implement the `SignalGenerator` class which consumes the core mechanics array, maps internal Market Structure vs DOL, and constructs Reversal `TradeSetup` objects into the `SetupRegistry`.
</objective>

<must_haves>
- Integrates with `StrategyLogic` arrays from df.
- Evaluates `MECHANICAL` vs `ADVANCED` signals via internal High/Low tracking.
</must_haves>

<tasks>

<task>
<description>Implement Signal Generator Reversal Logic</description>
<action>
Create `src/signal_generator.py`. Implement `SignalGenerator` class. Add `generate_signals(self, df, registry)` function. 
Write loop parsing over dataframe to identify when a Sweep transitions into a valid IFVG trigger in the opposite direction. Calculate the `MarketStructure` internal highs/lows (using a local n-bar pivot on internal candles separating entry and target bounds) to assess entry validity against DOL. Use this to emit a `TradeSetup` with `ModelType.REVERSAL` to the registry.
</action>
<read_first>
- src/core.py
- src/models.py
- .planning/phases/03-signal-engine/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `src/signal_generator.py` created and has class `SignalGenerator`.
- `def generate_signals` is defined.
- Evaluates internal levels against DOL properly to assign `SignalGrade.MECHANICAL` vs `SignalGrade.ADVANCED`.
- `python -m py_compile src/signal_generator.py` exits 0.
</acceptance_criteria>
</task>

</tasks>

## Verification
- Code passes syntax compilation.
