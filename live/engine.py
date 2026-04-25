"""
Unified live signal engine — NY ORB + Dodgy, one trade at a time.

Usage
-----
    engine = LiveEngine()
    engine.on_day_open(nq_price)   # call once before first bar each day

    for bar in your_bar_feed:      # Candle objects, 1-minute bars
        signal = engine.on_bar(bar)
        if signal:
            # signal.source   → "ORB" | "DODGY"
            # signal.setup    → TradeSetup (entry, stop, target, direction)
            submit_order(signal)

    # Per bar, also check if the active trade hit stop/target:
    engine.check_exits(bar)        # fires engine.on_trade_closed() internally

Interface
---------
Subclass LiveEngine and override on_trade_opened / on_trade_closed to hook
into your order submission layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.core import Candle
from src.execution import Direction, TradeSetup

from live.dodgy_processor import DodgyProcessor
from live.gex_live import fetch_gex_profile
from live.orb_processor import OrbProcessor

logger = logging.getLogger(__name__)

TICK        = 0.25
POINT_VALUE = 20.0  # NQ: $20/point


@dataclass
class Signal:
    source: str        # "ORB" | "DODGY"
    setup:  TradeSetup


@dataclass
class ActiveTrade:
    signal:          Signal
    current_stop:    float
    be_triggered:    bool = False
    contracts:       int  = 1


class LiveEngine:
    """
    Processes live 1-minute NQ bars.  Only one trade is open at a time —
    whichever strategy fires first owns the slot until the trade closes.
    """

    def __init__(self, contracts: int = 1) -> None:
        self._orb   = OrbProcessor()
        self._dodgy = DodgyProcessor()
        self._trade: Optional[ActiveTrade] = None
        self._contracts = contracts

    # ── Day lifecycle ───────────────────────────────────────────────────────

    def on_day_open(self, nq_price: float) -> None:
        """
        Call once before the first bar of each trading day.
        Fetches fresh GEX from yfinance and injects it into the Dodgy processor.
        """
        logger.info("Fetching GEX profile for day open (NQ=%.2f)…", nq_price)
        gex = fetch_gex_profile(nq_price)
        if gex:
            logger.info("GEX flip=%.2f  clusters=%s", gex["gex_flip"], gex["gamma_clusters"])
        else:
            logger.warning("GEX unavailable — Dodgy gamma levels will be empty today.")
        self._dodgy.set_gex_profile(gex)

    # ── Bar processing ──────────────────────────────────────────────────────

    def on_bar(self, bar: Candle) -> Optional[Signal]:
        """
        Feed one 1-minute bar.  Returns a Signal if a new trade should be entered,
        None otherwise.  Also manages break-even moves on the active trade.
        """
        # ── Manage active trade ────────────────────────────────────────────
        if self._trade:
            self._manage_trade(bar)
            # Check exits — if still open, don't look for new signals
            if self._trade:
                return None

        # ── Gate open: ask both strategies ────────────────────────────────
        orb_setup   = self._orb.on_bar(bar)
        dodgy_setup = self._dodgy.on_bar(bar)

        signal = None
        if orb_setup:
            signal = Signal(source="ORB", setup=orb_setup)
        elif dodgy_setup:
            signal = Signal(source="DODGY", setup=dodgy_setup)

        if signal:
            self._trade = ActiveTrade(
                signal=signal,
                current_stop=signal.setup.stop_price,
                contracts=self._contracts,
            )
            self.on_trade_opened(signal)

        return signal

    def check_exits(self, bar: Candle) -> None:
        """
        Explicit exit check — call this if you want stop/target evaluation
        decoupled from on_bar() (e.g. when using a faster tick feed for exits).
        """
        if self._trade:
            self._manage_trade(bar)

    # ── Hooks (override in subclass) ────────────────────────────────────────

    def on_trade_opened(self, signal: Signal) -> None:
        """Called immediately when a new trade is entered."""
        logger.info(
            "\n╔══════════════════════════════════════════════════════╗\n"
            "║  🔔 NEW TRADE — %s %s                              ║\n"
            "╠══════════════════════════════════════════════════════╣\n"
            "║  Entry:  %.2f                                       ║\n"
            "║  Stop:   %.2f                                       ║\n"
            "║  Target: %.2f                                       ║\n"
            "║  ID:     %s                                         ║\n"
            "╚══════════════════════════════════════════════════════╝",
            signal.source,
            signal.setup.direction.value.upper(),
            signal.setup.entry_price,
            signal.setup.stop_price,
            signal.setup.target_price,
            signal.setup.setup_id,
        )

    def on_trade_closed(self, trade: ActiveTrade, exit_category: str, pnl_points: float) -> None:
        """Called when a trade is closed (stop, target, or EOD)."""
        pnl_usd = pnl_points * POINT_VALUE * trade.contracts
        if pnl_usd > 0:
            result = "✅ WIN"
        elif pnl_usd < 0:
            result = "❌ LOSS"
        else:
            result = "➖ SCRATCH"
            
        logger.info(
            "\n╔══════════════════════════════════════════════════════╗\n"
            "║  %s — %s %s                                      ║\n"
            "╠══════════════════════════════════════════════════════╣\n"
            "║  P&L:    %+.2f pts  ($%+.0f)                        ║\n"
            "║  Reason: %s                                         ║\n"
            "╚══════════════════════════════════════════════════════╝",
            result,
            trade.signal.source,
            trade.signal.setup.direction.value.upper(),
            pnl_points,
            pnl_usd,
            exit_category,
        )

    # ── internals ───────────────────────────────────────────────────────────

    def _manage_trade(self, bar: Candle) -> None:
        trade  = self._trade
        setup  = trade.signal.setup
        is_long = setup.direction == Direction.LONG

        # ── Break-even trigger ─────────────────────────────────────────────
        if not trade.be_triggered:
            be = setup.break_even_trigger
            if (is_long and bar.high >= be) or (not is_long and bar.low <= be):
                trade.current_stop = setup.entry_price
                trade.be_triggered = True
                logger.debug("Break-even activated for %s", setup.setup_id)

        stop = trade.current_stop

        # ── Stop hit ───────────────────────────────────────────────────────
        if (is_long and bar.low <= stop) or (not is_long and bar.high >= stop):
            pnl = (stop - setup.entry_price) if is_long else (setup.entry_price - stop)
            self._close("STOP_LOSS", pnl, bar)
            return

        # ── Target hit ────────────────────────────────────────────────────
        tp = setup.target_price
        if (is_long and bar.high >= tp) or (not is_long and bar.low <= tp):
            pnl = (tp - setup.entry_price) if is_long else (setup.entry_price - tp)
            self._close("TARGET_HIT", pnl, bar)

    def _close(self, category: str, pnl_points: float, bar: Candle) -> None:
        trade = self._trade
        if trade is None:
            return
        # Notify individual processors so they can reset state
        if trade.signal.source == "ORB":
            self._orb.notify_closed(category, pnl_points, bar.timestamp)
        self.on_trade_closed(trade, category, pnl_points)
        self._trade = None

    # ── introspection ────────────────────────────────────────────────────────

    @property
    def has_open_trade(self) -> bool:
        return self._trade is not None

    @property
    def active_trade(self) -> Optional[ActiveTrade]:
        return self._trade
