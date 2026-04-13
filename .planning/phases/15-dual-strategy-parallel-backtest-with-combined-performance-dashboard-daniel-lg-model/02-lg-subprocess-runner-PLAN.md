---
phase: 15
plan_id: "02"
title: "LG Model Subprocess Runner"
wave: 1
depends_on: []
autonomous: true
files_modified:
  - src/lg_runner.py
---

# Plan 02: LG Model Subprocess Runner

## Objective
Create a Python module that invokes the LG Model's Node.js backtest CLI as a subprocess, handles Windows/Unix path differences, ensures npm dependencies are installed, and returns the path to the generated trades CSV.

## Tasks

<task id="1" title="Create src/lg_runner.py">
<read_first>
- strategies/lg_model/src/cli/backtest.js — CLI flags and behaviour
- strategies/lg_model/package.json — npm scripts and dependencies list
- src/execution.py — to understand the module pattern used in this project
</read_first>

<action>
Create `src/lg_runner.py` with the following implementation:

```python
"""
LG Model subprocess runner.

Invokes the LG Model's Node.js backtest CLI as a subprocess and returns
the path to the generated trades.csv.

The LG Model expects:
  --1h   Path to 1H semicolon CSV (preamble on line 1, header on line 2)
  --1m   Path to 1Min semicolon CSV (header on line 1)
  --out-dir   Output directory for trades.csv
  --from YYYY-MM-DD  (optional) Berlin calendar start date
  --to   YYYY-MM-DD  (optional) Berlin calendar end date
  --no-progress   Suppress TUI progress bars (required for subprocess)
  --no-html       Skip generating LG's own report.html (we build our own)
"""

import subprocess
import sys
import shutil
from pathlib import Path


def _npm_cmd() -> str:
    """Return 'npm.cmd' on Windows, 'npm' elsewhere."""
    if sys.platform == "win32":
        return "npm.cmd"
    return "npm"


def _node_cmd() -> str:
    """Return the node executable name."""
    return "node"


def ensure_npm_install(submodule_dir: Path) -> None:
    """Run npm install in the LG submodule if node_modules doesn't exist."""
    node_modules = submodule_dir / "node_modules"
    if not node_modules.exists():
        print(f"📦 Installing LG Model npm dependencies in {submodule_dir} ...")
        result = subprocess.run(
            [_npm_cmd(), "install"],
            cwd=submodule_dir,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"npm install failed in {submodule_dir}:\n{result.stderr}"
            )
        print("✅ npm install complete.")
    else:
        print(f"📦 LG node_modules already present — skipping npm install.")


def run_lg_backtest(
    submodule_dir: Path,
    m1_path: Path,
    h1_path: Path,
    out_dir: Path,
    from_date: str = None,
    to_date: str = None,
) -> Path:
    """
    Run the LG Model backtest CLI.

    Args:
        submodule_dir: Path to strategies/lg_model/ (the submodule root)
        m1_path: Absolute path to 1-minute semicolon CSV
        h1_path: Absolute path to 1-hour semicolon CSV (with preamble line 1)
        out_dir: Directory where trades.csv will be written
        from_date: Optional YYYY-MM-DD Berlin calendar start date
        to_date: Optional YYYY-MM-DD Berlin calendar end date

    Returns:
        Path to the generated trades.csv file

    Raises:
        RuntimeError: If node process exits non-zero
        FileNotFoundError: If trades.csv is not produced
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    submodule_dir = Path(submodule_dir)

    # Ensure npm dependencies
    ensure_npm_install(submodule_dir)

    # Check node is available
    node_path = shutil.which(_node_cmd())
    if node_path is None:
        raise EnvironmentError(
            "node not found in PATH. Install Node.js 18+ to run the LG Model."
        )

    cmd = [
        _node_cmd(),
        "src/cli/backtest.js",
        "--1m", str(m1_path.resolve()),
        "--1h", str(h1_path.resolve()),
        "--out-dir", str(out_dir.resolve()),
        "--no-progress",   # suppress TUI progress bars in subprocess
        "--no-html",       # skip LG's own HTML report — we generate our own
    ]
    if from_date:
        cmd += ["--from", from_date]
    if to_date:
        cmd += ["--to", to_date]

    print(f"\n🚀 Running LG Model backtest...")
    print(f"   Command: {' '.join(cmd[:6])} ...")
    if from_date or to_date:
        print(f"   Date range: {from_date or 'start'} → {to_date or 'end'}")

    result = subprocess.run(
        cmd,
        cwd=submodule_dir,
        capture_output=True,
        text=True,
    )

    # Print stdout (LG console report)
    if result.stdout.strip():
        print("\n📊 LG Model Report:")
        print(result.stdout)

    if result.returncode != 0:
        raise RuntimeError(
            f"LG backtest failed (exit {result.returncode}):\n{result.stderr}"
        )

    trades_path = out_dir / "trades.csv"
    if not trades_path.exists():
        raise FileNotFoundError(
            f"LG backtest completed but trades.csv not found in {out_dir}"
        )

    print(f"✅ LG trades saved: {trades_path}")
    return trades_path
```
</action>

<acceptance_criteria>
- `src/lg_runner.py` exists
- File contains `def run_lg_backtest(`
- File contains `def ensure_npm_install(`
- File contains `_npm_cmd()` function that returns `npm.cmd` on Windows
- File contains `--no-progress` and `--no-html` in the subprocess command
- File contains `RuntimeError` raised on non-zero exit code
- File contains `FileNotFoundError` raised if `trades.csv` not found
</acceptance_criteria>
</task>

## Verification
The module can be imported without error:
  python -c "from src.lg_runner import run_lg_backtest, ensure_npm_install; print('OK')"

## must_haves
- `src/lg_runner.py` is importable as a Python module
- `run_lg_backtest()` accepts `from_date` and `to_date` optional parameters
- Windows npm path (`npm.cmd`) is handled
- Node availability is checked before running
- Non-zero exit from node raises a clear `RuntimeError` with stderr content
