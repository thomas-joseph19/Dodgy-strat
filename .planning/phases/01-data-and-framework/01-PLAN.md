---
phase: 1
wave: 1
depends_on: []
files_modified:
  - "src/config.py"
autonomous: true
requirements_addressed:
  - "DATA-02"
---

# Phase 1: Data & Framework - Wave 1

<objective>
To establish the Python configuration management structure using strongly typed Dataclasses to house all parameterized inputs for the IFVG strategy.
</objective>

<must_haves>
- Uses Python `dataclass`.
- Defines thresholds and execution parameters that will be configurable.
</must_haves>

<tasks>

<task>
<description>Create initial system configuration Dataclass</description>
<action>
Create `src/config.py` (and the `src` directory) with a `StrategyConfig` dataclass covering dummy parameters: BSL/SSL tolerance, timeframes, and stop-loss choices which can be updated later. It must load environment variables or use safe defaults.
</action>
<read_first>
- .planning/phases/01-data-and-framework/01-CONTEXT.md
- src/config.py
</read_first>
<acceptance_criteria>
- `src/config.py` exists and contains `@dataclass class StrategyConfig`
- File parses without errors (`python -m py_compile src/config.py` exits 0)
</acceptance_criteria>
</task>

</tasks>

## Verification
- `python -m py_compile src/config.py` runs without errors.
