---
phase: 5
wave: 2
depends_on: ["01-PLAN.md"]
files_modified:
  - "src/reporting/plots.py"
autonomous: true
requirements_addressed:
  - "REP-04"
---

# Phase 5: Reports & Visuals - Wave 2

<objective>
To implement strictly parameterized interactive Plotly setup chart logic for individual trade debugging.
</objective>

<must_haves>
- Uses `plotly.graph_objects` exclusively for trade setups.
- Employs 50 bars pre-sweep and 20 bars post-exit slice parameters constraint.
- Colors mapped directly to requested dict configuration (`#26a69a`, `#FFD700` etc.) toggling discrete layers structurally.
</must_haves>

<tasks>

<task>
<description>Create Plotly Setup Visualizer</description>
<action>
Create `src/reporting/plots.py`. Define `build_setup_chart(result, ohlc_df)` function using identical `ChartConfig` mechanics shown in context (50 before, 20 after). Render OHLC native candlesticks along with lines explicitly capturing `fail_stop_level`, `target_price`, and `entry`. Include annotation limits placing marker points matching IFVG zone boxes exactly shading historical logic. Code should output a raw HTML string. Include function generating total Equity Curve graph leveraging line trace arrays.
</action>
<read_first>
- .planning/phases/05-reports-visuals/DISCUSSION-LOG.md
- src/simulator_models.py
</read_first>
<acceptance_criteria>
- Native imports load `plotly.graph_objects`.
- Chart layout strings correctly append metadata blocks dynamically mapping P&L annotations and Grades.
- No matplotlib in this specific setup script to remain compliant with explicit instructions.
</acceptance_criteria>
</task>

</tasks>

## Verification
- Syntax compilation.
