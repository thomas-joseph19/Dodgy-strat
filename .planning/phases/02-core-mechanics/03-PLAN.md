---
phase: 2
wave: 3
depends_on: ["02-PLAN.md"]
files_modified:
  - "src/core.py"
autonomous: true
requirements_addressed:
  - "CORE-04"
---

# Phase 2: Core Mechanics - Wave 3

<objective>
To implement the Inverted Fair Value Gap (IFVG) trigger logic, which requires a body close acting completely across an active Zone's top/bottom from the opposing direction.
</objective>

<must_haves>
- Inversion detection based strictly on candle close through the complete stacked zone array mapping.
</must_haves>

<tasks>

<task>
<description>Implement IFVG Trigger logic</description>
<action>
In `src/core.py` under `StrategyLogic`, add `detect_ifvgs(self, df: pd.DataFrame) -> pd.DataFrame`. Create logic that confirms inversion: for `active_bull_zone`, if price `close` < `active_bull_zone_bottom`, it flips to `ifvg_bear` trigger. For `active_bear_zone`, if price `close` > `active_bear_zone_top`, it flips to `ifvg_bull` trigger. Establish boolean columns `ifvg_bull_trigger` and `ifvg_bear_trigger`.
</action>
<read_first>
- src/core.py
- .planning/phases/02-core-mechanics/02-CONTEXT.md
</read_first>
<acceptance_criteria>
- `def detect_ifvgs` exists in `src/core.py`
- Code checks for `close` against the `ZONE_BOTTOM`/`ZONE_TOP`
- `python -m py_compile src/core.py` exits 0
</acceptance_criteria>
</task>

</tasks>

## Verification
- Code passes syntax check without errors.
