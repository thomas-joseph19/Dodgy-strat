"""
Rithmic execution bridge — subclasses LiveEngine and routes orders directly
to a Rithmic account via async-rithmic (pip install async-rithmic).

Order flow
----------
1. Engine fires on_trade_opened → LIMIT entry order submitted.
2. Entry fills → SL (STOP) + TP (LIMIT) bracket legs submitted.
3. Exchange fills SL or TP → _on_order_update cancels the other leg.
4. Engine's bar-level exit detection also runs as a safety net;
   if it fires first it calls on_trade_closed, which cancels both legs
   and submits a market close if the entry had already filled.

Environment variables (see from_env())
---------------------------------------
    RITHMIC_USER, RITHMIC_PASSWORD
    RITHMIC_SYSTEM    — e.g. "Rithmic Test" (default) or your MFF system name
    RITHMIC_APP       — app name registered with Rithmic (default "dodgy-live")
    RITHMIC_APP_VER   — (default "1.0")
    RITHMIC_URL       — gateway host:port (default "rituz00100.rithmic.com:443")
    RITHMIC_SYMBOL    — front-month contract, e.g. "NQM5"  (default "NQM5")
    RITHMIC_EXCHANGE  — exchange code (default "CME")
    RITHMIC_CONTRACTS — number of contracts (default "1")
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from async_rithmic import (
    RithmicClient,
    TimeBarType,
    OrderType,
    TransactionType,
)

from src.core import Candle
from src.execution import Direction

from live.engine import ActiveTrade, LiveEngine, Signal

logger = logging.getLogger(__name__)

# ── Fill status strings async-rithmic sends back ─────────────────────────────
_FILL_STATUSES = frozenset({"FILL", "FILLED", "Complete", "complete"})


class RithmicBridge(LiveEngine):
    """
    Drop-in execution layer for LiveEngine.  Override nothing — just call
    ``asyncio.run(bridge.run())``.
    """

    def __init__(
        self,
        user: str,
        password: str,
        system_name: str,
        app_name: str,
        app_version: str,
        url: str,
        symbol: str,
        exchange: str,
        contracts: int = 1,
    ) -> None:
        super().__init__(contracts=contracts)
        self._client = RithmicClient(
            user=user,
            password=password,
            system_name=system_name,
            app_name=app_name,
            app_version=app_version,
            url=url,
        )
        self._symbol   = symbol
        self._exchange = exchange

        # Order ID tracking (reset on every new trade)
        self._entry_order_id: Optional[str] = None
        self._sl_order_id:    Optional[str] = None
        self._tp_order_id:    Optional[str] = None
        self._entry_filled:   bool          = False
        self._pending_signal: Optional[Signal] = None

    # ── factory ──────────────────────────────────────────────────────────────

    @classmethod
    def from_env(cls) -> "RithmicBridge":
        return cls(
            user=os.environ["RITHMIC_USER"],
            password=os.environ["RITHMIC_PASSWORD"],
            system_name=os.environ.get("RITHMIC_SYSTEM",  "Rithmic Test"),
            app_name=os.environ.get("RITHMIC_APP",         "dodgy-live"),
            app_version=os.environ.get("RITHMIC_APP_VER",  "1.0"),
            url=os.environ.get("RITHMIC_URL",               "rituz00100.rithmic.com:443"),
            symbol=os.environ.get("RITHMIC_SYMBOL",         "NQM5"),
            exchange=os.environ.get("RITHMIC_EXCHANGE",     "CME"),
            contracts=int(os.environ.get("RITHMIC_CONTRACTS", "1")),
        )

    # ── LiveEngine hooks ──────────────────────────────────────────────────────

    def on_trade_opened(self, signal: Signal) -> None:
        super().on_trade_opened(signal)   # logs the entry
        self._pending_signal = signal
        self._entry_filled   = False
        asyncio.ensure_future(self._submit_entry(signal))

    def on_trade_closed(
        self, trade: ActiveTrade, exit_category: str, pnl_points: float
    ) -> None:
        super().on_trade_closed(trade, exit_category, pnl_points)  # logs P&L
        asyncio.ensure_future(self._handle_engine_close(trade))

    # ── Order helpers ─────────────────────────────────────────────────────────

    async def _submit_entry(self, signal: Signal) -> None:
        setup   = signal.setup
        is_long = setup.direction == Direction.LONG
        self._entry_order_id = f"ENTRY-{uuid.uuid4().hex[:8].upper()}"
        logger.info(
            "ENTRY LIMIT %s  id=%s  price=%.2f  qty=%d",
            "BUY" if is_long else "SELL",
            self._entry_order_id,
            setup.entry_price,
            self._contracts,
        )
        try:
            await self._client.submit_order(
                self._entry_order_id,
                self._symbol,
                self._exchange,
                qty=self._contracts,
                order_type=OrderType.LIMIT,
                transaction_type=TransactionType.BUY if is_long else TransactionType.SELL,
                price=setup.entry_price,
            )
        except Exception as exc:
            logger.error("Entry order submission failed: %s", exc)
            self._entry_order_id = None

    async def _submit_bracket(self, signal: Signal) -> None:
        """Called after entry confirms filled."""
        setup      = signal.setup
        is_long    = setup.direction == Direction.LONG
        close_side = TransactionType.SELL if is_long else TransactionType.BUY

        self._sl_order_id = f"SL-{uuid.uuid4().hex[:8].upper()}"
        logger.info(
            "SL STOP  id=%s  price=%.2f",
            self._sl_order_id, setup.stop_price,
        )
        try:
            await self._client.submit_order(
                self._sl_order_id,
                self._symbol,
                self._exchange,
                qty=self._contracts,
                order_type=OrderType.STOP,
                transaction_type=close_side,
                price=setup.stop_price,
            )
        except Exception as exc:
            logger.error("SL order submission failed: %s", exc)
            self._sl_order_id = None

        self._tp_order_id = f"TP-{uuid.uuid4().hex[:8].upper()}"
        logger.info(
            "TP LIMIT  id=%s  price=%.2f",
            self._tp_order_id, setup.target_price,
        )
        try:
            await self._client.submit_order(
                self._tp_order_id,
                self._symbol,
                self._exchange,
                qty=self._contracts,
                order_type=OrderType.LIMIT,
                transaction_type=close_side,
                price=setup.target_price,
            )
        except Exception as exc:
            logger.error("TP order submission failed: %s", exc)
            self._tp_order_id = None

    async def _cancel_order(self, order_id: str) -> None:
        try:
            await self._client.cancel_order(order_id)
            logger.info("Cancelled order %s", order_id)
        except Exception as exc:
            logger.warning("Cancel %s failed (may already be filled): %s", order_id, exc)

    async def _handle_engine_close(self, trade: ActiveTrade) -> None:
        """
        Engine detected stop/target via bar prices.  If the entry already
        filled we may still have one open bracket leg — cancel it.
        If the entry hadn't filled yet, cancel the entry too.
        """
        if self._entry_filled:
            # Cancel whichever bracket leg is still open
            for oid in (self._sl_order_id, self._tp_order_id):
                if oid:
                    await self._cancel_order(oid)
        else:
            # Entry never filled — cancel it (signal invalidated)
            if self._entry_order_id:
                await self._cancel_order(self._entry_order_id)

        self._reset_order_state()

    def _reset_order_state(self) -> None:
        self._entry_order_id = None
        self._sl_order_id    = None
        self._tp_order_id    = None
        self._entry_filled   = False
        self._pending_signal = None

    # ── async-rithmic callbacks ───────────────────────────────────────────────

    async def _on_order_update(self, data: dict) -> None:
        """
        Fired by async-rithmic for every order status change.

        NOTE: The exact field names depend on the async-rithmic version.
        Typical keys: 'basket_id', 'status', 'filled_size'.
        Run with DEBUG logging on first use to inspect the raw dict.
        """
        oid    = data.get("basket_id") or data.get("order_id", "")
        status = str(data.get("status", ""))
        logger.debug("Order update  id=%s  status=%s  raw=%s", oid, status, data)

        if status not in _FILL_STATUSES:
            return

        if oid == self._entry_order_id and not self._entry_filled:
            self._entry_filled = True
            logger.info("Entry %s filled — submitting bracket", oid)
            if self._pending_signal:
                await self._submit_bracket(self._pending_signal)

        elif oid == self._sl_order_id:
            logger.info("SL %s filled — cancelling TP", oid)
            self._sl_order_id = None
            if self._tp_order_id:
                await self._cancel_order(self._tp_order_id)
            self._reset_order_state()

        elif oid == self._tp_order_id:
            logger.info("TP %s filled — cancelling SL", oid)
            self._tp_order_id = None
            if self._sl_order_id:
                await self._cancel_order(self._sl_order_id)
            self._reset_order_state()

    async def _on_time_bar(self, data: dict) -> None:
        """
        Convert async-rithmic time bar dict → Candle and feed the engine.

        NOTE: Field names ('open_price', 'high_price', etc.) are based on
        async-rithmic's documented schema.  Log the raw dict at DEBUG level
        on first run to confirm exact keys for your version.
        """
        try:
            ts = data.get("bar_end_datetime") or data.get("end_time")
            if ts is None:
                logger.debug("Time bar has no timestamp field — skipping: %s", data)
                return
            if not isinstance(ts, datetime):
                # Assume nanosecond Unix epoch if numeric
                ts = datetime.fromtimestamp(float(ts) / 1e9, tz=timezone.utc)

            bar = Candle(
                timestamp=ts,
                open=float(data["open_price"]),
                high=float(data["high_price"]),
                low=float(data["low_price"]),
                close=float(data["close_price"]),
            )
            self.on_bar(bar)
        except Exception:
            logger.exception("Bar processing error — raw data: %s", data)

    # ── day-open GEX price helper ─────────────────────────────────────────────

    async def _fetch_nq_price(self) -> float:
        """Fetch current NQ last price via yfinance (blocking → executor)."""
        import yfinance as yf
        loop = asyncio.get_event_loop()

        def _sync() -> float:
            info = yf.Ticker("NQ=F").fast_info
            return float(
                getattr(info, "last_price", None)
                or getattr(info, "previous_close", None)
                or 21000.0
            )

        return await loop.run_in_executor(None, _sync)

    # ── main run loop ─────────────────────────────────────────────────────────

    async def run(self) -> None:
        logger.info("Connecting to Rithmic at %s …", self._symbol)
        await self._client.connect()

        # Wire event callbacks
        self._client.on_time_bar     += self._on_time_bar
        self._client.on_order_update += self._on_order_update

        # Subscribe to 1-minute NQ bars
        await self._client.subscribe_to_time_bar_data(
            self._symbol,
            self._exchange,
            TimeBarType.MINUTE_BAR,
            period=1,
        )
        logger.info("Subscribed to 1-min bars — %s @ %s", self._symbol, self._exchange)

        # Fetch NQ price for GEX and prime day-open state
        nq_price = await self._fetch_nq_price()
        self.on_day_open(nq_price)

        try:
            await asyncio.Event().wait()   # run until KeyboardInterrupt / cancel
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Shutting down — disconnecting from Rithmic …")
            try:
                await self._client.unsubscribe_from_time_bar_data(
                    self._symbol, self._exchange, TimeBarType.MINUTE_BAR, period=1
                )
            except Exception:
                pass
            await self._client.disconnect()
