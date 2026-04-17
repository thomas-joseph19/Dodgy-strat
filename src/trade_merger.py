"""
Trade stream normaliser and equity curve builder for dual-strategy backtest.

Handles normalisation of:
  - Daniel trades CSV (Python engine, Chicago local dates)
  - LG Model trades CSV (Node.js engine, Berlin session dates, semicolon-delimited)

Common normalised schema:
  date         str       YYYY-MM-DD (local calendar date for the session)
  strategy     str       "daniel" or "lg"
  direction    str       "LONG" or "SHORT"
  entry_price  float
  exit_type    str       (Daniel: exit_type; LG: exit_category)
  pnl_points   float     NQ points
  pnl_usd      float     USD P&L (Daniel: direct; LG: pnl_points * 20)
  exit_time_sort str     ISO UTC timestamp for chronological sorting
"""

import csv
from pathlib import Path
from datetime import datetime

# LG Model uses $20 per NQ point
LG_DOLLARS_PER_POINT = 20.0


def _to_float(val: str) -> float:
    """Safe float conversion - return 0.0 on empty or invalid."""
    try:
        return float(val) if val and val.strip() else 0.0
    except ValueError:
        return 0.0


def normalise_daniel_trades(csv_path: Path) -> list:
    """
    Read Daniel trades.csv and return list of normalised trade dicts.
    Daniel CSV is comma-delimited with header on line 1.

    Daniel exit types:
      TARGET_HIT       -> win
      HARD_STOP        -> loss
      EXPIRED_OR_STILL_OPEN -> excluded (not closed)
    """
    if not Path(csv_path).exists():
        raise FileNotFoundError(f"Daniel trades CSV not found: {csv_path}")

    trades = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            exit_type = row.get("exit_type", "")
            if exit_type == "EXPIRED_OR_STILL_OPEN":
                continue  # exclude open/expired trades from analysis

            # Derive a sortable UTC-like timestamp from the date (Daniel doesn't have exit_time_utc)
            # Use date + 23:59:59 as a fallback sort key (LG trades sort by entry_time_utc)
            date_str = row.get("date", "")
            exit_time_sort = date_str + "T23:59:59Z" if date_str else "0000-00-00T00:00:00Z"

            trades.append({
                "date": date_str,
                "strategy": "daniel",
                "direction": row.get("direction", "").upper(),
                "entry_price": _to_float(row.get("entry_price", "")),
                "exit_type": exit_type,
                "pnl_points": _to_float(row.get("pnl_points", "")),
                "pnl_usd": _to_float(row.get("pnl_usd", "")),
                "risk_points": _to_float(row.get("risk_points", "")),
                "exit_time_sort": exit_time_sort,
            })
    return trades


def normalise_lg_trades(csv_path: Path) -> list:
    """
    Read LG Model trades.csv and return list of normalised trade dicts.
    LG CSV is COMMA-delimited (despite the input CSVs being semicolon-delimited,
    the output trades.csv from LG uses standard comma CSV format).

    LG exit categories (closed trades):
      CLOSED_WIN, CLOSED_LOSS, CLOSED_SCRATCH, CLOSED_TIMEOUT_FLATTEN
    Excluded (open/invalid):
      OPEN, other non-CLOSED_ values
    """
    if not Path(csv_path).exists():
        raise FileNotFoundError(f"LG trades CSV not found: {csv_path}")

    CLOSED_EXITS = {"CLOSED_WIN", "CLOSED_LOSS", "CLOSED_SCRATCH", "CLOSED_TIMEOUT_FLATTEN"}

    trades = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            exit_category = row.get("exit_category", "")
            if exit_category not in CLOSED_EXITS:
                continue  # exclude open or non-closed trades

            pnl_points = _to_float(row.get("pnl_points", ""))
            pnl_usd_raw = row.get("pnl_usd", "").strip()
            # LG writes pnl_usd in the CSV already; use it if present, else compute
            pnl_usd = _to_float(pnl_usd_raw) if pnl_usd_raw else pnl_points * LG_DOLLARS_PER_POINT

            # LG direction mapping: side column = "long" or "short"
            side = row.get("side", "").lower()
            direction = "LONG" if side == "long" else "SHORT"

            # Use entry_time_utc as sort key
            exit_time_sort = row.get("exit_time_utc", "") or row.get("entry_time_utc", "") or "0000-00-00T00:00:00Z"

            trades.append({
                "date": row.get("session_date", ""),
                "strategy": "lg",
                "direction": direction,
                "entry_price": _to_float(row.get("entry_price", "")),
                "exit_type": exit_category,
                "pnl_points": pnl_points,
                "pnl_usd": pnl_usd,
                "risk_points": _to_float(row.get("risk_points", "")),
                "exit_time_sort": exit_time_sort,
            })
    return trades


def merge_and_sort(daniel_trades: list, lg_trades: list) -> list:
    """
    Merge both trade lists and sort chronologically by exit_time_sort.
    Returns a single list with all trades tagged by strategy.
    """
    all_trades = daniel_trades + lg_trades
    return sorted(all_trades, key=lambda t: t["exit_time_sort"])


def build_equity_curves(merged_trades: list, initial_capital: float = 100_000.0) -> dict:
    """
    Build equity curves for combined, daniel-only, and lg-only.

    Capital model:
      - Both strategies start at $100k
      - Combined equity = initial_capital + sum(all pnl_usd)
        (NOT $200k starting - they share a single $100k pool)
      - daniel_equity tracks Daniel cumulative P&L above $100k
      - lg_equity tracks LG cumulative P&L above $100k
      - combined = initial_capital + (daniel_pnl + lg_pnl)

    Returns:
      {
        "combined": [{"date": str, "equity": float}, ...],
        "daniel": [{"date": str, "equity": float}, ...],
        "lg": [{"date": str, "equity": float}, ...],
      }
    """
    daniel_pnl = 0.0
    lg_pnl = 0.0

    combined_curve = []
    daniel_curve = []
    lg_curve = []

    for t in merged_trades:
        pnl = t["pnl_usd"]
        date = t["date"]

        if t["strategy"] == "daniel":
            daniel_pnl += pnl
            daniel_curve.append({"date": date, "equity": round(initial_capital + daniel_pnl, 2)})
        else:
            lg_pnl += pnl
            lg_curve.append({"date": date, "equity": round(initial_capital + lg_pnl, 2)})

        combined_equity = initial_capital + daniel_pnl + lg_pnl
        combined_curve.append({
            "date": date,
            "equity": round(combined_equity, 2),
            "strategy": t["strategy"],
        })

    return {
        "combined": combined_curve,
        "daniel": daniel_curve,
        "lg": lg_curve,
    }


def compute_combined_summary(merged_trades: list) -> dict:
    """
    Compute aggregate metrics for the combined trade stream.
    Works on the normalised merged trade list.
    """
    closed = [t for t in merged_trades]
    if not closed:
        return {}

    total_pnl = sum(t["pnl_usd"] for t in closed)
    wins = [t for t in closed if t["pnl_points"] > 0]
    losses = [t for t in closed if t["pnl_points"] < 0]
    win_rate = len(wins) / len(closed) if closed else 0.0
    avg_win = sum(t["pnl_usd"] for t in wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(t["pnl_usd"] for t in losses) / len(losses)) if losses else 0.0
    profit_factor = (
        sum(t["pnl_usd"] for t in wins) / abs(sum(t["pnl_usd"] for t in losses))
        if losses else 0.0
    )
    expectancy = total_pnl / len(closed) if closed else 0.0

    return {
        "total_pnl": round(total_pnl, 2),
        "total_trades": len(closed),
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "expectancy": round(expectancy, 2),
        "avg_win_usd": round(avg_win, 2),
        "avg_loss_usd": round(avg_loss, 2),
    }
