---
phase: 4
wave: 3
depends_on: ["02-PLAN.md"]
files_modified:
  - "src/execution_engine.py"
  - "src/simulator_models.py"
autonomous: true
requirements_addressed:
  - "EXEC-06"
---

# Phase 4: Risk & Execution - Wave 3

<objective>
To implement the final simulation P&L math (commission and slippage adjustment) and manage the overarching `AccountState` registry over the simulated timeline.
</objective>

<must_haves>
- P&L calculator taking raw deterministic fill levels and tracking realistic exit penalties.
- Manager applying the setup list correctly chronological-wise adjusting account limits sequentially.
- Enforcement of acceptable RTH bounds.
</must_haves>

<tasks>

<task>
<description>Implement Equity Simulation Engine</description>
<action>
In `src/simulator_models.py`, add the `AccountState` logic incorporating tracking peak equity to model drawdowns. Implement the `calculate_trade_pnl()` function correctly evaluating entry and exit parameters against slippage logic. 
In `src/execution_engine.py` wrapper, implement `run_backtest(self, registry, df)` which iterates through all setups chronologically. Submits them to `evaluate_setup` individually, retrieves the `TradeResult`, applies positional sizing from `calculate_position_size`, nets P&L, modifies the current `AccountState` and retains the output history log. Add a session gate ignoring setups occurring outside RTH (9:30-16:00 ET).
</action>
<read_first>
- src/simulator_models.py
- src/execution_engine.py
- .planning/phases/04-risk-execution/DISCUSSION-LOG.md
</read_first>
<acceptance_criteria>
- End-to-end framework calculates realistic sized contract performance natively against account states.
- Applies standard dual slippage + commission logic identically to specs.
</acceptance_criteria>
</task>

</tasks>

## Verification
- Syntax check.
