"""
Incremental (live) Dodgy signal processor.

Mirrors the per-bar logic of dodgy/main.py run_backtest() but processes
one candle at a time instead of a pre-loaded array, using the non-vectorized
SwingRegistry + detect_fvg path so no precomputation is required.

Allowed sessions: midday (12:00–14:00 ET) and power_hour (14:00–16:00 ET).
overnight and open_drive are excluded.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional

from zoneinfo import ZoneInfo

from src.core import Candle, THRESHOLDS
from src.execution import (
    Direction, ModelType, SignalGrade, StopType, TradeSetup,
)
from src.fvg import FairValueGap, detect_fvg
from src.liquidity import LiquidityLevel, SweepEvent, detect_sweep
from src.swings import SwingRegistry

ET = ZoneInfo("America/New_York")

_ALLOWED_SESSIONS = frozenset({"midday", "power_hour"})


def _classify_session(ts: datetime) -> str:
    et = ts.astimezone(ET)
    h, m = et.hour, et.minute
    if h < 9 or (h == 9 and m < 30):
        return "pre_market"
    if h < 12:
        return "open_drive"
    if h < 14:
        return "midday"
    if h < 16:
        return "power_hour"
    return "overnight"


class DodgyProcessor:
    """
    Feed 1-minute bars one at a time via on_bar().
    Returns a TradeSetup when a signal fires, else None.

    Call set_gex_profile(profile) once per trading day (before market open)
    to inject the daily GEX context.
    """

    def __init__(self) -> None:
        # Incremental swing registries
        self._swing_1m = SwingRegistry(lookback=THRESHOLDS.swing_lookback)
        self._swing_htf = SwingRegistry(lookback=THRESHOLDS.htf_swing_lookback, prune_enabled=False)

        # 1H resampling state
        self._htf_bucket_open:  Optional[float] = None
        self._htf_bucket_high:  float = -math.inf
        self._htf_bucket_low:   float =  math.inf
        self._htf_bucket_close: Optional[float] = None
        self._htf_bucket_start: Optional[datetime] = None

        # FVG deque (last 100)
        self._active_fvgs: Deque[FairValueGap] = deque(maxlen=100)

        # Sweep state
        self._current_sweep: Optional[SweepEvent] = None
        self._sweep_detector_levels: List[LiquidityLevel] = []
        self._gex_profile: Optional[Dict[str, Any]] = None
        self._last_gex_date: Optional[str] = None

        # ATR rolling (100-bar)
        self._atr_window: deque = deque(maxlen=THRESHOLDS.atr_period)
        self._prev_close: Optional[float] = None
        self._bar_index: int = 0

        # Bar buffer for detect_fvg (needs last 3)
        self._bar_buffer: List[Candle] = []

    # ── public API ──────────────────────────────────────────────────────────

    def set_gex_profile(self, profile: Optional[Dict[str, Any]]) -> None:
        """Inject today's GEX profile (call at day open, before first bar)."""
        self._gex_profile = profile
        if profile:
            formed_at = datetime.now(tz=ET) - timedelta(days=1)
            gex_levels = [
                LiquidityLevel(profile["gex_flip"], "BSL", "GEX_FLIP",      2, formed_at, True),
                LiquidityLevel(profile["gex_flip"], "SSL", "GEX_FLIP",      2, formed_at, True),
                *[LiquidityLevel(px, "BSL", "GAMMA_CLUSTER", 2, formed_at, True)
                  for px in profile.get("gamma_clusters", [])],
                *[LiquidityLevel(px, "SSL", "GAMMA_CLUSTER", 2, formed_at, True)
                  for px in profile.get("gamma_clusters", [])],
            ]
            # Remove stale gamma levels, add fresh ones
            self._sweep_detector_levels = [
                lv for lv in self._sweep_detector_levels
                if lv.quality not in ("GEX_FLIP", "GAMMA_CLUSTER")
            ]
            self._sweep_detector_levels.extend(gex_levels)

    def on_bar(self, bar: Candle) -> Optional[TradeSetup]:
        i = self._bar_index
        self._bar_index += 1

        # ── ATR ───────────────────────────────────────────────────────────
        tr = bar.high - bar.low
        if self._prev_close is not None:
            tr = max(tr, abs(bar.high - self._prev_close), abs(bar.low - self._prev_close))
        self._atr_window.append(tr)
        curr_atr = sum(self._atr_window) / len(self._atr_window)
        self._prev_close = bar.close

        # ── HTF 1H resampling ─────────────────────────────────────────────
        self._update_htf(bar)

        # ── 1m swing registry ─────────────────────────────────────────────
        self._swing_1m.update(bar)

        # ── FVG detection ─────────────────────────────────────────────────
        self._bar_buffer.append(bar)
        if len(self._bar_buffer) > 200:
            self._bar_buffer = self._bar_buffer[-100:]
        if len(self._bar_buffer) >= 3:
            fvg = detect_fvg(self._bar_buffer, len(self._bar_buffer) - 1)
            if fvg:
                self._active_fvgs.append(fvg)

        # ── Sweep detection ────────────────────────────────────────────────
        intact = [lv for lv in self._sweep_detector_levels if lv.is_intact]
        sweep = detect_sweep(bar, i, intact)
        if sweep:
            self._current_sweep = sweep
        elif self._current_sweep:
            self._current_sweep.bars_since_sweep += 1
            if self._current_sweep.bars_since_sweep > THRESHOLDS.sweep_context_max_bars:
                self._current_sweep = None

        # ── Signal generation (session-gated) ────────────────────────────
        if self._current_sweep and _classify_session(bar.timestamp) in _ALLOWED_SESSIONS:
            setup = self._try_signal(bar, curr_atr)
            if setup:
                self._current_sweep = None
                return setup

        return None

    # ── internals ──────────────────────────────────────────────────────────

    def _update_htf(self, bar: Candle) -> None:
        """Resample 1m bars into 1H candles; update HTF swing registry when a new hour closes."""
        ts_et = bar.timestamp.astimezone(ET)
        bucket_hour = ts_et.replace(minute=0, second=0, microsecond=0)

        if self._htf_bucket_start is None:
            self._htf_bucket_start = bucket_hour

        if bucket_hour != self._htf_bucket_start:
            # New hour — close the previous bucket
            if self._htf_bucket_open is not None:
                htf_candle = Candle(
                    timestamp=self._htf_bucket_start,
                    open=self._htf_bucket_open,
                    high=self._htf_bucket_high,
                    low=self._htf_bucket_low,
                    close=self._htf_bucket_close,
                )
                self._swing_htf.update(htf_candle)
                # Add new HTF swing levels to sweep detector
                for sh in self._swing_htf.confirmed_highs[-5:]:
                    exists = any(
                        abs(lv.price - sh.price) < 0.5
                        for lv in self._sweep_detector_levels
                        if lv.quality == "HTF_SWING"
                    )
                    if not exists:
                        self._sweep_detector_levels.append(
                            LiquidityLevel(sh.price, "BSL", "HTF_SWING", 1, sh.candle_time, True)
                        )
                for sl in self._swing_htf.confirmed_lows[-5:]:
                    exists = any(
                        abs(lv.price - sl.price) < 0.5
                        for lv in self._sweep_detector_levels
                        if lv.quality == "HTF_SWING"
                    )
                    if not exists:
                        self._sweep_detector_levels.append(
                            LiquidityLevel(sl.price, "SSL", "HTF_SWING", 1, sl.candle_time, True)
                        )

            # Start new bucket
            self._htf_bucket_start = bucket_hour
            self._htf_bucket_open  = bar.open
            self._htf_bucket_high  = bar.high
            self._htf_bucket_low   = bar.low
            self._htf_bucket_close = bar.close
        else:
            if self._htf_bucket_open is None:
                self._htf_bucket_open = bar.open
            self._htf_bucket_high  = max(self._htf_bucket_high, bar.high)
            self._htf_bucket_low   = min(self._htf_bucket_low,  bar.low)
            self._htf_bucket_close = bar.close

    def _try_signal(self, bar: Candle, curr_atr: float) -> Optional[TradeSetup]:
        sweep = self._current_sweep
        bias  = "BULLISH" if sweep.direction == "SSL_SWEPT" else "BEARISH"
        fvg_dir = "BEARISH" if bias == "BULLISH" else "BULLISH"

        targ_dist = (
            curr_atr * THRESHOLDS.atr_min_target_mult
            if THRESHOLDS.use_atr_scaling
            else THRESHOLDS.min_target_distance_points
        )

        for fvg in list(self._active_fvgs)[-10:]:
            if fvg.direction != fvg_dir or not fvg.is_intact:
                continue

            if bias == "BULLISH":
                if not (bar.close > fvg.fvg_top and bar.open < fvg.fvg_top):
                    continue
                ih = self._swing_1m.get_nearest_high_above(bar.close)
                targ_px = ih.price if ih else bar.close + targ_dist
                targ    = max(targ_px, bar.close + targ_dist)
                entry   = fvg.fvg_top
                stop    = sweep.sweep_candle.low - 2.0
                risk    = entry - stop
                if risk <= 0:
                    continue
                if (targ - entry) / risk < 1.5:
                    continue
                return TradeSetup(
                    setup_id=f"L-REV-{bar.timestamp.strftime('%Y%m%d%H%M')}",
                    created_at=bar.timestamp,
                    symbol="NQ", timeframe="1m",
                    direction=Direction.LONG,
                    model_type=ModelType.REVERSAL,
                    grade=SignalGrade.MECHANICAL,
                    entry_price=entry,
                    stop_type=StopType.SWING_STOP,
                    stop_price=stop,
                    target_price=targ,
                    break_even_trigger=entry + risk,
                    invalidation_price=sweep.sweep_candle.low,
                    expiry_time=None,
                    internal_level=ih.price if ih else 0.0,
                    risk_reward=(targ - entry) / risk,
                    momentum_score=(
                        abs(bar.close - bar.open) / (bar.high - bar.low)
                        if (bar.high - bar.low) > 0 else 0.0
                    ),
                    reasoning=(
                        f"HTF Sweep ({sweep.swept_level.quality}) + IFVG Bullish Inversion"
                    ),
                )

            else:  # BEARISH
                if not (bar.close < fvg.fvg_bottom and bar.open > fvg.fvg_bottom):
                    continue
                il = self._swing_1m.get_nearest_low_below(bar.close)
                targ_px = il.price if il else bar.close - targ_dist
                targ    = min(targ_px, bar.close - targ_dist)
                entry   = fvg.fvg_bottom
                stop    = sweep.sweep_candle.high + 2.0
                risk    = stop - entry
                if risk <= 0:
                    continue
                if (entry - targ) / risk < 1.5:
                    continue
                return TradeSetup(
                    setup_id=f"S-REV-{bar.timestamp.strftime('%Y%m%d%H%M')}",
                    created_at=bar.timestamp,
                    symbol="NQ", timeframe="1m",
                    direction=Direction.SHORT,
                    model_type=ModelType.REVERSAL,
                    grade=SignalGrade.MECHANICAL,
                    entry_price=entry,
                    stop_type=StopType.SWING_STOP,
                    stop_price=stop,
                    target_price=targ,
                    break_even_trigger=entry - risk,
                    invalidation_price=sweep.sweep_candle.high,
                    expiry_time=None,
                    internal_level=il.price if il else 0.0,
                    risk_reward=(entry - targ) / risk,
                    momentum_score=(
                        abs(bar.close - bar.open) / (bar.high - bar.low)
                        if (bar.high - bar.low) > 0 else 0.0
                    ),
                    reasoning=(
                        f"HTF Sweep ({sweep.swept_level.quality}) + IFVG Bearish Inversion"
                    ),
                )

        return None
