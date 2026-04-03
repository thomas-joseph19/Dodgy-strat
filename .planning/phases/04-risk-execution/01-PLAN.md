---
phase: 4
wave: 1
depends_on: []
files_modified:
  - "src/simulator_models.py"
autonomous: true
requirements_addressed:
  - "EXEC-06"
---

# Phase 4: Risk & Execution - Wave 1

<objective>
To establish the core simulation structures modeling Trade Results, State tracking, and strict Simulation Configurations. Ensure dynamic position sizing limits are supported natively.
</objective>

<must_haves>
- Implements `TradeResult`, `TradeState`, `SimulationConfig`, and `AccountState` data structures.
- Logic for calculating position sizing based on 1% fixed risk constraints mapping strict point value economics ($20 p/pt/$4 comm).
</must_haves>

<tasks>

<task>
<description>Create Simulator Datastructures and Matrix</description>
<action>
Create `src/simulator_models.py` with dataclasses for `SimulationConfig` (starting_capital=100000, risk_pct=0.01, commission_rt=4.00, slippage_ticks=1, tick_size=0.25, point_value=20.00, min_contracts=1, max_contracts=10). Add classes for `TradeState` and `TradeResult`. Implement the `calculate_position_size` function processing dynamic contract math bound exactly as specified in the Phase 4 Context / Discussion.
</action>
<read_first>
- .planning/phases/04-risk-execution/04-CONTEXT.md
- .planning/phases/04-risk-execution/DISCUSSION-LOG.md
</read_first>
<acceptance_criteria>
- `src/simulator_models.py` compiles successfully.
- `calculate_position_size` yields exact whole contract multiples constrained mechanically.
- Structure contains standard configuration limits.
</acceptance_criteria>
</task>

</tasks>

## Verification
- Code passes syntax check.
