---
phase: 4
wave: 2
depends_on: ["01-PLAN.md"]
files_modified:
  - "src/execution_engine.py"
autonomous: true
requirements_addressed:
  - "EXEC-01"
  - "EXEC-02"
  - "EXEC-03"
  - "EXEC-04"
  - "EXEC-05"
---

# Phase 4: Risk & Execution - Wave 2

<objective>
To implement the Independent Setup-by-Setup evaluation wrapper isolating the simulated progression to resolve unambiguous exit logic.
</objective>

<must_haves>
- An `ExecutionEngine` orchestrating `evaluate_setup`.
- Correct exit checking priority enforcing `Stop Loss -> Fail Stop -> Target`.
- Deterministic break-even updates locking the Hard Stop.
</must_haves>

<tasks>

<task>
<description>Implement Setup Evaluation Simulator</description>
<action>
Create `src/execution_engine.py`. Build the `ExecutionEngine` class. Implement the `evaluate_setup(self, setup, df)` method which loops over the subset of `df` chronologically following the setup creation time. Maintain local `TradeState` mapping inside the sub loop evaluating invalidation prior to filling, execution of break_even triggers, and utilizing an unambiguous `check_exits` mechanism. Match the exact check\_exits priority structure defined in `DISCUSSION-LOG.md` logic (1. hard stop triggered by wick, 2. fail stop triggered by close, then 3. target).
</action>
<read_first>
- .planning/phases/04-risk-execution/DISCUSSION-LOG.md
- src/simulator_models.py
</read_first>
<acceptance_criteria>
- File syntax parses flawlessly.
- Contains independent evaluative chronological loop for tracking a single signal to completion.
- Logic safely enforces stop outs identically to discussed deterministic conservative metrics.
</acceptance_criteria>
</task>

</tasks>

## Verification
- Code passes syntax check without error.
