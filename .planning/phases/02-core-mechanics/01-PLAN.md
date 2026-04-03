---
phase: 2
wave: 1
depends_on: []
files_modified:
  - "src/config.py"
  - "src/core.py"
autonomous: true
requirements_addressed:
  - "CORE-01"
  - "CORE-05"
---

# Phase 2: Core Mechanics - Wave 1

<objective>
To implement Liquidity Sweep detection by first finding pivots and then marking when those levels are swept, along with a validity loop constraint.
</objective>

<must_haves>
- Vectorized approaches using pandas where possible.
- Tracks `WICK_SWEEP` and `BODY_SWEEP` logic.
</must_haves>

<tasks>

<task>
<description>Update StrategyConfig</description>
<action>
Update `src/config.py` to add `pivot_lookback: int` (default 10) and `sweep_max_lookback: int` (default 20).
</action>
<read_first>
- src/config.py
</read_first>
<acceptance_criteria>
- `src/config.py` contains `pivot_lookback`
- `src/config.py` contains `sweep_max_lookback`
</acceptance_criteria>
</task>

<task>
<description>Create Liquidity Sweep Detector</description>
<action>
Create `src/core.py` with a class `StrategyLogic`. Add a method `detect_sweeps(self, df: pd.DataFrame) -> pd.DataFrame` that first identifies BSL (highest high over `pivot_lookback`) and SSL (lowest low over `pivot_lookback`). It should then scan forward. If a candle's high breaks BSL, it's a `BSL_WICK_SWEEP`. If its close is also > BSL, it's a `BSL_BODY_SWEEP`. Apply the same logic inversely for SSL. Return DataFrame with new boolean columns: `bsl_wick_sweep`, `bsl_body_sweep`, `ssl_wick_sweep`, `ssl_body_sweep` and float columns `active_bsl_level`, `active_ssl_level`. Ensure that standard pandas `.rolling()` or `.shift()` logic is used efficiently.
</action>
<read_first>
- src/data_loader.py
- .planning/phases/02-core-mechanics/02-CONTEXT.md
</read_first>
<acceptance_criteria>
- `src/core.py` exists and contains `class StrategyLogic`
- `src/core.py` contains `def detect_sweeps`
- `python -m py_compile src/core.py` exits 0
</acceptance_criteria>
</task>

</tasks>

## Verification
- `python -m py_compile src/core.py` runs without errors.
