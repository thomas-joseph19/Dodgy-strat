"""
NY ORB signal processor — Python port of src/signals/orb-ny.js + src/backtest/run-orb-session.js.

Processes live 1-minute NQ bars one at a time and emits a TradeSetup when:
  1. The 8:00-8:10 AM ET opening range is locked.
  2. A bias is established (close > zone high or < zone low) from 9:30 AM onward.
  3. Price retraces to the zone midpoint (limit fill).

Session level windows (for SL anchoring):
  Asia:   18:00 prev-day ET  →  03:00 ET
  London: 03:30 ET           →  11:30 ET

All times are America/New_York.  The processor resets automatically at midnight ET.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from enum import Enum, auto
from typing import Optional

from zoneinfo import ZoneInfo

from src.core import Candle
from src.execution import (
    Direction, ModelType, SignalGrade, StopType, TradeSetup,
)

ET = ZoneInfo("America/New_York")

# ── ORB config (mirrors run-orb-session.js defaults) ──────────────────────────
ZONE_START_H, ZONE_START_M = 8, 0       # 08:00 ET — zone opens
ZONE_BARS                  = 10         # 10 one-minute bars → zone closes at 08:10
BIAS_EARLIEST_H, BIAS_EARLIEST_M = 9, 30  # don't check bias before 09:30 ET
TRADE_WINDOW_H, TRADE_WINDOW_M   = 8, 10  # limit orders active from 08:10 ET
CUTOFF_H, CUTOFF_M               = 11, 0  # no new entries after 11:00 ET
EOD_FLATTEN_H, EOD_FLATTEN_M     = 16, 15 # force-close by 16:15 ET

RR_MULTIPLIER  = 4.0
SL_SCAN_LOW    = 5.0
SL_SCAN_HIGH   = 10.0
SL_DEFAULT     = 8.0
MAX_ZONE_WIDTH = 20.0
MIN_ZONE_WIDTH = 2.0

TICK = 0.25

def _round_tick(price: float) -> float:
    return round(round(price / TICK) * TICK, 10)


class _Phase(Enum):
    OVERNIGHT    = auto()   # before 08:00, accumulating Asia/London levels
    ZONE_FORMING = auto()   # 08:00–08:10, building the opening range
    ZONE_LOCKED  = auto()   # 08:10–09:30, zone done, no bias yet
    BIAS_WATCH   = auto()   # 09:30–11:00, watching for breakout close
    LIMIT_ACTIVE = auto()   # bias set, waiting for retrace to zoneMid
    IN_TRADE     = auto()   # position open
    DONE         = auto()   # trade complete or cutoff passed for today


@dataclass
class OrbTrade:
    setup: TradeSetup
    is_closed: bool = False
    exit_category: str = "OPEN"
    pnl_points: float = 0.0
    exit_time: Optional[datetime] = None


@dataclass
class _DayState:
    date_et: str              # "YYYY-MM-DD"
    phase: _Phase = _Phase.OVERNIGHT

    # Session level trackers
    asia_high: float = -math.inf
    asia_low:  float =  math.inf
    london_high: float = -math.inf
    london_low:  float =  math.inf

    # Zone
    zone_high: float = -math.inf
    zone_low:  float =  math.inf
    zone_bars: int   = 0

    # Trade state
    bias: Optional[str]   = None   # "bullish" | "bearish"
    zone_mid: float       = 0.0
    trade: Optional[OrbTrade] = None
    trade_taken: bool     = False


class OrbProcessor:
    """
    Feed 1-minute bars via on_bar().  Returns a TradeSetup the bar a limit
    fills, or None otherwise.  Call on_exit(bar) to notify that the active
    trade is being managed externally (engine will call it when stop/target
    hit so ORB can reset its state).
    """

    def __init__(self) -> None:
        self._day: Optional[_DayState] = None

    # ── public API ─────────────────────────────────────────────────────────

    def on_bar(self, bar: Candle) -> Optional[TradeSetup]:
        ts_et = bar.timestamp.astimezone(ET)
        date_str = ts_et.strftime("%Y-%m-%d")

        if self._day is None or self._day.date_et != date_str:
            self._day = _DayState(date_et=date_str)

        d = self._day
        h_et = ts_et.hour
        m_et = ts_et.minute

        # ── Session level tracking (runs every bar regardless of phase) ────
        self._update_session_levels(d, ts_et, bar)

        # ── Phase transitions ──────────────────────────────────────────────
        if d.phase == _Phase.OVERNIGHT:
            if h_et == ZONE_START_H and m_et == ZONE_START_M:
                d.phase = _Phase.ZONE_FORMING

        if d.phase == _Phase.ZONE_FORMING:
            d.zone_high = max(d.zone_high, bar.high)
            d.zone_low  = min(d.zone_low,  bar.low)
            d.zone_bars += 1
            if d.zone_bars >= ZONE_BARS:
                zone_width = _round_tick(d.zone_high - d.zone_low)
                if zone_width < MIN_ZONE_WIDTH or zone_width > MAX_ZONE_WIDTH:
                    d.phase = _Phase.DONE
                else:
                    d.zone_mid = _round_tick((d.zone_high + d.zone_low) / 2.0)
                    d.phase = _Phase.ZONE_LOCKED
            return None

        if d.phase == _Phase.ZONE_LOCKED:
            if h_et > BIAS_EARLIEST_H or (h_et == BIAS_EARLIEST_H and m_et >= BIAS_EARLIEST_M):
                d.phase = _Phase.BIAS_WATCH

        if d.phase == _Phase.BIAS_WATCH:
            if h_et > CUTOFF_H or (h_et == CUTOFF_H and m_et >= CUTOFF_M):
                d.phase = _Phase.DONE
                return None
            if d.bias is None and not d.trade_taken:
                if bar.close > d.zone_high:
                    d.bias = "bullish"
                elif bar.close < d.zone_low:
                    d.bias = "bearish"
            if d.bias is not None:
                d.phase = _Phase.LIMIT_ACTIVE

        if d.phase == _Phase.LIMIT_ACTIVE:
            if h_et > CUTOFF_H or (h_et == CUTOFF_H and m_et >= CUTOFF_M):
                d.phase = _Phase.DONE
                return None
            if not d.trade_taken:
                filled = (
                    bar.low <= d.zone_mid  if d.bias == "bullish"
                    else bar.high >= d.zone_mid
                )
                if filled:
                    setup = self._build_setup(d, bar)
                    if setup is None:
                        d.phase = _Phase.DONE
                        return None
                    d.trade = OrbTrade(setup=setup)
                    d.trade_taken = True
                    d.phase = _Phase.IN_TRADE
                    return setup

        if d.phase == _Phase.IN_TRADE and d.trade and not d.trade.is_closed:
            # EOD flatten
            if h_et > EOD_FLATTEN_H or (h_et == EOD_FLATTEN_H and m_et >= EOD_FLATTEN_M):
                self._close_trade(d.trade, "EOD_FLATTEN",
                                  bar.close - d.trade.setup.entry_price
                                  if d.trade.setup.direction == Direction.LONG
                                  else d.trade.setup.entry_price - bar.close,
                                  bar.timestamp)
                d.phase = _Phase.DONE

        return None

    def notify_closed(self, exit_category: str, pnl_points: float, ts: datetime) -> None:
        """Called by the engine when it closes the ORB trade externally."""
        if self._day and self._day.trade and not self._day.trade.is_closed:
            self._close_trade(self._day.trade, exit_category, pnl_points, ts)
            self._day.phase = _Phase.DONE

    def active_trade(self) -> Optional[OrbTrade]:
        d = self._day
        if d and d.trade and not d.trade.is_closed:
            return d.trade
        return None

    # ── internals ──────────────────────────────────────────────────────────

    def _update_session_levels(self, d: _DayState, ts_et: datetime, bar: Candle) -> None:
        h_et = ts_et.hour
        m_et = ts_et.minute

        # Asia: 18:00 prev-day → 03:00 current day
        in_asia = (
            (h_et >= 18)                            # prev-day evening portion
            or (h_et < 3)                           # early morning
            or (h_et == 3 and m_et == 0)
        )
        if in_asia:
            d.asia_high = max(d.asia_high, bar.high)
            d.asia_low  = min(d.asia_low,  bar.low)

        # London: 03:30 → 11:30
        in_london = (
            (h_et == 3  and m_et >= 30)
            or (3 < h_et < 11)
            or (h_et == 11 and m_et < 30)
        )
        if in_london:
            d.london_high = max(d.london_high, bar.high)
            d.london_low  = min(d.london_low,  bar.low)

    def _build_setup(self, d: _DayState, bar: Candle) -> Optional[TradeSetup]:
        is_bull = d.bias == "bullish"
        entry   = d.zone_mid

        candidates = [d.asia_high, d.asia_low, d.london_high, d.london_low]
        best_sl, best_dist = None, 0.0
        for lvl in candidates:
            if lvl in (-math.inf, math.inf) or not math.isfinite(lvl):
                continue
            dist = (entry - lvl) if is_bull else (lvl - entry)
            if SL_SCAN_LOW <= dist <= SL_SCAN_HIGH and dist > best_dist:
                best_dist = dist
                best_sl = lvl

        if best_sl is not None:
            sl = _round_tick(best_sl)
            sl_dist = best_dist
        else:
            sl_dist = SL_DEFAULT
            sl = _round_tick(entry - sl_dist if is_bull else entry + sl_dist)

        tp_dist = RR_MULTIPLIER * sl_dist
        tp  = _round_tick(entry + tp_dist if is_bull else entry - tp_dist)
        rr  = (abs(tp - entry) / abs(entry - sl)) if abs(entry - sl) > 0 else 0.0

        return TradeSetup(
            setup_id=f"ORB-{'L' if is_bull else 'S'}-{bar.timestamp.strftime('%Y%m%d%H%M')}",
            created_at=bar.timestamp,
            symbol="NQ",
            timeframe="1m",
            direction=Direction.LONG if is_bull else Direction.SHORT,
            model_type=ModelType.REVERSAL,
            grade=SignalGrade.MECHANICAL,
            entry_price=entry,
            stop_type=StopType.SWING_STOP,
            stop_price=sl,
            target_price=tp,
            break_even_trigger=entry + (entry - sl) if is_bull else entry - (sl - entry),
            invalidation_price=sl,
            expiry_time=None,
            internal_level=d.zone_high if is_bull else d.zone_low,
            risk_reward=rr,
            momentum_score=0.0,
            reasoning=(
                f"NY ORB {'bullish' if is_bull else 'bearish'} breakout | "
                f"zone {_round_tick(d.zone_high)}/{_round_tick(d.zone_low)} | "
                f"SL anchor {'session level' if best_sl else 'default'}"
            ),
        )

    @staticmethod
    def _close_trade(trade: OrbTrade, category: str, pnl: float, ts: datetime) -> None:
        trade.is_closed = True
        trade.exit_category = category
        trade.pnl_points = pnl
        trade.exit_time = ts
