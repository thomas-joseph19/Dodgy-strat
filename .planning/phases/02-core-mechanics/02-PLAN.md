---
phase: 2
wave: 2
depends_on: ["01-PLAN.md"]
files_modified:
  - "src/core.py"
autonomous: true
requirements_addressed:
  - "CORE-02"
  - "CORE-03"
---

# Phase 2: Core Mechanics - Wave 2

<objective>
To implement Vectorized Fair Value Gap (FVG) detection and the stacking logic (combining sequential same-direction gaps that are not filled by body closes).
</objective>

<must_haves>
- Vectorized pandas mapping for initial individual FVGs.
- Loop or structured mapping for identifying stacks.
- Accurate calculation of `ZONE_TOP` and `ZONE_BOTTOM`.
</must_haves>

<tasks>

<task>
<description>Create FVG detection</description>
<action>
In `src/core.py` under `StrategyLogic`, add `detect_fvgs(self, df: pd.DataFrame) -> pd.DataFrame`. Calculate `fvg_bull` (n-2 high < n low) and `fvg_bear` (n-2 low > n high). For bullish FVG, `top` is n low, `bottom` is n-2 high. For bearish, `top` is n-2 low, `bottom` is n high. Add these boolean and float columns to the DataFrame.
</action>
<read_first>
- src/core.py
</read_first>
<acceptance_criteria>
- `def detect_fvgs` exists in `src/core.py`
- Code handles `n-2` indices properly (using `.shift(2)`)
</acceptance_criteria>
</task>

<task>
<description>Implement FVG Stacking logic</description>
<action>
In `src/core.py` under `StrategyLogic`, add `detect_zones(self, df: pd.DataFrame) -> pd.DataFrame` which groups consecutive same-direction FVGs provided the intermediate candles don't close inside the gap. Establish a continuous state tracking for `active_bull_zone_top`, `active_bull_zone_bottom`, `active_bear_zone_top`, and `active_bear_zone_bottom`.
</action>
<read_first>
- src/core.py
- .planning/phases/02-core-mechanics/02-CONTEXT.md
</read_first>
<acceptance_criteria>
- `def detect_zones` exists in `src/core.py`
- `python -m py_compile src/core.py` exits 0
</acceptance_criteria>
</task>

</tasks>

## Verification
- Code passes syntax check without errors.
