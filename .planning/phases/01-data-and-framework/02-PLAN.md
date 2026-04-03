---
phase: 1
wave: 2
depends_on: ["01-PLAN.md"]
files_modified:
  - "src/data_loader.py"
  - "requirements.txt"
autonomous: true
requirements_addressed:
  - "DATA-01"
---

# Phase 1: Data & Framework - Wave 2

<objective>
To implement an object-oriented Data Loader that imports 1-minute NQ OHLCV historical data from Parquet files into a Python Pandas DataFrame.
</objective>

<must_haves>
- Uses `pandas` and `pyarrow`/`fastparquet`.
- Implements `DataLoader` class structure to manage imports.
</must_haves>

<tasks>

<task>
<description>Add python dependencies</description>
<action>
Create or update `requirements.txt` with `pandas`, `pyarrow`, and `numpy`.
</action>
<read_first>
- .planning/phases/01-data-and-framework/01-CONTEXT.md
- requirements.txt
</read_first>
<acceptance_criteria>
- `requirements.txt` contains `pandas`
- `requirements.txt` contains `pyarrow`
</acceptance_criteria>
</task>

<task>
<description>Implement DataLoader class</description>
<action>
Create `src/data_loader.py`. Implement a `DataLoader` class configured via the `StrategyConfig` that accepts a parquet filepath in its `load_ohlcv` method and returns a Pandas DataFrame with normalized standard OHLCV columns (`time`, `open`, `high`, `low`, `close`, `volume`).
</action>
<read_first>
- src/config.py
- src/data_loader.py
</read_first>
<acceptance_criteria>
- `src/data_loader.py` exists
- File parses without errors (`python -m py_compile src/data_loader.py` exits 0)
- `src/data_loader.py` contains `class DataLoader:`
- `src/data_loader.py` contains `def load_ohlcv`
</acceptance_criteria>
</task>

</tasks>

## Verification
- Dependencies are declared.
- `python -m py_compile src/data_loader.py` succeeds.
