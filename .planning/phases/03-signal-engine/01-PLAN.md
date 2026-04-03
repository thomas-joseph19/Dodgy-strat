---
phase: 3
wave: 1
depends_on: []
files_modified:
  - "src/models.py"
autonomous: true
requirements_addressed:
  - "SIG-01"
---

# Phase 3: Signal Engine - Wave 1

<objective>
To establish the Data Models bounding the signal boundary, defining `TradeSetup` and `SetupRegistry` to eliminate opaque boolean flags and wrap context.
</objective>

<must_haves>
- Implements `TradeSetup` dataclass.
- Implements `SetupRegistry` class.
- Includes `Direction`, `ModelType`, `StopType` enumerations.
</must_haves>

<tasks>

<task>
<description>Create Data Models</description>
<action>
Create `src/models.py` and implement the `TradeSetup` dataclass, `SetupRegistry` manager, and all internal helper enums (`Direction`, `ModelType`, `StopType`, `SignalGrade`) modeled exactly after the agreed format in `03-CONTEXT.md` / `DISCUSSION-LOG.md`. Ensure `TradeSetup` includes fields for `setup_id`, `direction`, `entry_price`, `target_price`, `fail_stop_level`, `internal_level`, `dol_price`, `grade`, and continuation leg variables.
</action>
<read_first>
- .planning/phases/03-signal-engine/03-CONTEXT.md
</read_first>
<acceptance_criteria>
- `src/models.py` exists
- `python -m py_compile src/models.py` exits 0
- Contains `class TradeSetup:` and `class SetupRegistry:`
</acceptance_criteria>
</task>

</tasks>

## Verification
- Code passes compilation without errors.
