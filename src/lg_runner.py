"""
LG Model subprocess runner.

Invokes the LG Model's Node.js backtest CLI as a subprocess and returns
the path to the generated trades.csv.

The LG Model expects:
  --1h   Path to 1H semicolon CSV (preamble on line 1, header on line 2)
  --1m   Path to 1Min semicolon CSV (header on line 1)
  --out-dir   Output directory for trades.csv
  --from YYYY-MM-DD  (optional) Backtest start date
  --to   YYYY-MM-DD  (optional) Backtest end date
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
        print(f"[INFO] Installing LG Model npm dependencies in {submodule_dir} ...")
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
        print("[SUCCESS] npm install complete.")
    else:
        print(f"[INFO] LG node_modules already present - skipping npm install.")


def run_lg_backtest(
    submodule_dir: Path,
    m1_path: Path,
    h1_path: Path,
    out_dir: Path,
    from_date: str = None,
    to_date: str = None,
    strategy: str = "lg"
) -> Path:
    """
    Run the LG Model or ORB strategy backtest CLI.

    Args:
        submodule_dir: Path to strategies/lg_model/ (the submodule root)
        m1_path: Absolute path to 1-minute semicolon CSV
        h1_path: Absolute path to 1-hour semicolon CSV (with preamble line 1)
        out_dir: Directory where trades.csv will be written
        from_date: Optional YYYY-MM-DD start date
        to_date: Optional YYYY-MM-DD end date
        strategy: "lg" or "orb"

    Returns:
        Path to the generated trades.csv file
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

    if strategy == "orb":
        cmd = [
            _node_cmd(),
            "src/cli/backtest-orb.js",
            f"--dataset-1m={m1_path.resolve()}",
            f"--from={from_date or '2010-01-01'}",
            f"--to={to_date or '2026-12-31'}",
            "--output-stem=orb"
        ]
    else:
        cmd = [
            _node_cmd(),
            "src/cli/backtest.js",
            "--1m", str(m1_path.resolve()),
            "--1h", str(h1_path.resolve()),
            "--out-dir", str(out_dir.resolve()),
            "--no-progress",
            "--no-html",
        ]
        if from_date:
            cmd += ["--from", from_date]
        if to_date:
            cmd += ["--to", to_date]

    print(f"\n[INFO] Running {strategy.upper()} strategy backtest...")
    print(f"   Command: {' '.join(cmd[:6])} ...")

    result = subprocess.run(
        cmd,
        cwd=submodule_dir,
        capture_output=True,
        text=True,
    )

    # Print stdout (LG console report)
    if result.stdout.strip():
        print(f"\n[REPORT] {strategy.upper()} Model Report:")
        print(result.stdout)

    if result.returncode != 0:
        raise RuntimeError(
            f"{strategy.upper()} backtest failed (exit {result.returncode}):\n{result.stderr}"
        )

    trades_path = out_dir / ("trades_orb.csv" if strategy == "orb" else "trades.csv")
    if not trades_path.exists():
        # Try fallback if trades_orb.csv isn't the name (backtest-orb.js might write to cwd)
        fallback = submodule_dir / ("trades_orb.csv" if strategy == "orb" else "trades.csv")
        if fallback.exists():
            shutil.move(str(fallback), str(trades_path))
        else:
            raise FileNotFoundError(
                f"{strategy.upper()} backtest completed but trades CSV not found in {out_dir}"
            )

    print(f"[SUCCESS] {strategy.upper()} trades saved: {trades_path}")
    return trades_path
