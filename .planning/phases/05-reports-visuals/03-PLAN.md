---
phase: 5
wave: 3
depends_on: ["01-PLAN.md", "02-PLAN.md"]
files_modified:
  - "src/reporting/report_generator.py"
autonomous: true
requirements_addressed:
  - "REP-01"
  - "REP-03"
---

# Phase 5: Reports & Visuals - Wave 3

<objective>
To implement the artifact generation framework mapping exact directory hierarchies, tearsheets, CSV structures, and aggregate plotting combinations correctly.
</objective>

<must_haves>
- Uses `pandas` to write identical standard logs mapping 30 metrics parameters perfectly.
- Combines `metrics.md` generation into raw Markdown parsing outputs.
- Matplotlib script generates localized static `.png` mappings cleanly independent of active `.html` traces.
</must_haves>

<tasks>

<task>
<description>Create File Output Generators</description>
<action>
Create `src/reporting/report_generator.py`. Define `generate_report(run_id, metrics, trade_results, ohlc_df, config, output_root)`. 
1. Map `Path` directories enforcing `[output_root]/[run_id]/setups/` creation dynamically.
2. Draft `write_metrics_md` extracting formatted string logic reflecting exact tear-sheet visual markdown outputs requested explicitly.
3. Apply `pd.DataFrame([{...}]).to_csv()` executing 30 individual specific array combinations mapping Setup bounds mathematically.
4. Integrate `matplotlib` strictly producing a minimalistic global Equity array plotting peak balances and netting static `equity_curve.png`.
5. Call internal `plots.py` wrapper looping all trade results depositing independent layout strings natively generating nested `setup/...html` logs.
</action>
<read_first>
- .planning/phases/05-reports-visuals/DISCUSSION-LOG.md
- src/reporting/plots.py
- src/reporting/metrics.py
</read_first>
<acceptance_criteria>
- End-to-end framework outputs clean standard logs without error formatting constraints.
- Matplotlib logic contained firmly executing single `.png`.
</acceptance_criteria>
</task>

</tasks>

## Verification
- Syntax compilation.
