# Quick Task: CSV Data Migration & Mechanical Audit

## Objective
Enable `main.py` to load `.csv` files (specifically semicolon-delimited, comma-decimal institutional format) for the Daniel strategy backtest, as the Parquet data has been removed. Then, execute a clean mechanical (unoptimized) backtest on the full dataset.

## Plan
1.  **Modify `main.py`**:
    *   Update `run_backtest` to detect `.csv` extension.
    *   Implement robust CSV loading with `sep=';'` and `decimal=','`.
    *   Map columns if necessary (`Open`, `High`, `Low`, `Close`, `Volume`).
2.  **Run Mechanical Audit**:
    *   Use `python main.py` with `--data data/lg_format/1Min_NQ.csv` and `--rule-filter none`.
3.  **Verification**:
    *   Verify trades are generated.
    *   Compare density with previous Parquet-based runs to ensure no data loss.
