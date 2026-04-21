"""
NinjaTrader execution bridge.

Architecture
------------
Python is the TCP SERVER.  NinjaTrader (PythonSignalStrategy.cs) is the CLIENT
that connects on startup.

    NinjaTrader  ──────BAR JSON──────►  Python (this file)
    NinjaTrader  ◄────SIGNAL JSON──────  Python (this file)

Protocol (newline-delimited JSON, UTF-8):

  NT → Python (bar update, sent on every 1-minute bar close):
    {"type":"BAR","ts":"2025-06-01T14:30:00Z","open":21000.0,"high":21010.5,
     "low":20995.0,"close":21005.25}

  Python → NT (open a trade):
    {"type":"SIGNAL","action":"LONG","entry":21000.50,"stop":20992.25,
     "target":21032.00,"qty":1,"id":"L-REV-202506011030"}

  Python → NT (close active trade at market):
    {"type":"CLOSE"}

Usage
-----
    cd dodgy
    python -m live.run_live

Environment variables (or .env file + python-dotenv):
    NINJA_HOST        listen address (default "127.0.0.1")
    NINJA_PORT        listen port    (default "6789")
    RITHMIC_CONTRACTS contracts      (default "1")
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from src.core import Candle
from src.execution import Direction

from live.engine import ActiveTrade, LiveEngine, Signal, POINT_VALUE

logger = logging.getLogger(__name__)

ET = ZoneInfo("America/New_York")


class NinjaBridge(LiveEngine):
    """
    LiveEngine subclass that:
      - Runs an asyncio TCP server waiting for NinjaTrader to connect
      - Receives 1-minute bar JSON from NinjaTrader → feeds LiveEngine
      - Sends SIGNAL / CLOSE JSON to NinjaTrader when trades open/close
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6789,
        contracts: int = 1,
        max_daily_loss: float = -2000.0,
    ) -> None:
        super().__init__(contracts=contracts)
        self._host = host
        self._port = port
        self._writer: Optional[asyncio.StreamWriter] = None
        self._last_date: Optional[str] = None

        # ── Prop Firm Safety Guard ─────────────────────────────────────────
        self._max_daily_loss = max_daily_loss  # negative USD threshold
        self._daily_pnl_usd: float = 0.0
        self._daily_pnl_date: Optional[str] = None  # "YYYY-MM-DD" ET
        self._guard_triggered: bool = False

    @classmethod
    def from_env(cls) -> "NinjaBridge":
        return cls(
            host=os.environ.get("NINJA_HOST", "127.0.0.1"),
            port=int(os.environ.get("NINJA_PORT", "6789")),
            contracts=int(os.environ.get("RITHMIC_CONTRACTS", "1")),
            max_daily_loss=float(os.environ.get("MAX_DAILY_LOSS", "-2000")),
        )

    # ── LiveEngine hooks ──────────────────────────────────────────────────────

    def on_trade_opened(self, signal: Signal) -> None:
        # ── Prop Firm Guard gate ───────────────────────────────────────────
        if self._guard_triggered:
            logger.critical(
                "GUARD ACTIVE — Signal SUPPRESSED (%s). Daily P&L: $%.0f (limit: $%.0f)",
                signal.setup.setup_id, self._daily_pnl_usd, self._max_daily_loss,
            )
            # Undo the trade that LiveEngine just opened
            self._trade = None
            return

        super().on_trade_opened(signal)
        if self._writer:
            asyncio.ensure_future(self._send_signal(signal))
        else:
            logger.warning("Signal fired but no NinjaTrader connection — order not sent.")

    def on_trade_closed(
        self, trade: ActiveTrade, exit_category: str, pnl_points: float
    ) -> None:
        super().on_trade_closed(trade, exit_category, pnl_points)

        # ── Prop Firm Guard: accumulate daily P&L ──────────────────────────
        pnl_usd = pnl_points * POINT_VALUE * trade.contracts
        self._daily_pnl_usd += pnl_usd
        logger.info(
            "Daily P&L updated: $%.0f (trade: $%.0f, limit: $%.0f)",
            self._daily_pnl_usd, pnl_usd, self._max_daily_loss,
        )
        if self._daily_pnl_usd <= self._max_daily_loss:
            self._guard_triggered = True
            logger.critical(
                "🛑 PROP FIRM GUARD TRIGGERED — Daily loss $%.0f exceeds limit $%.0f. "
                "NO MORE TRADES TODAY.",
                self._daily_pnl_usd, self._max_daily_loss,
            )

        # Only send CLOSE if exit was detected by our bar logic first.
        # If NT filled the exchange-side SL/TP it will have already closed the
        # position on its side — sending CLOSE is harmless (NT ignores it when flat).
        if self._writer:
            asyncio.ensure_future(self._send_close())

    # ── TCP send helpers ──────────────────────────────────────────────────────

    async def _send(self, msg: dict) -> None:
        if self._writer is None:
            return
        try:
            self._writer.write((json.dumps(msg) + "\n").encode())
            await self._writer.drain()
        except Exception as exc:
            logger.error("Send failed: %s", exc)
            self._writer = None

    async def _send_signal(self, signal: Signal) -> None:
        setup   = signal.setup
        is_long = setup.direction == Direction.LONG
        await self._send({
            "type":   "SIGNAL",
            "action": "LONG" if is_long else "SHORT",
            "entry":  setup.entry_price,
            "stop":   setup.stop_price,
            "target": setup.target_price,
            "qty":    self._contracts,
            "id":     setup.setup_id,
        })

    async def _send_close(self) -> None:
        await self._send({"type": "CLOSE"})

    # ── Bar / day processing ──────────────────────────────────────────────────

    async def _process_message(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Unparseable message: %r", raw)
            return

        if msg.get("type") != "BAR":
            logger.debug("Ignoring non-BAR message: %s", msg.get("type"))
            return

        try:
            ts = datetime.fromisoformat(msg["ts"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (KeyError, ValueError) as exc:
            logger.error("Bad timestamp in BAR message: %s", exc)
            return

        # Day-open GEX refresh (runs in executor so yfinance doesn't block the loop)
        date_et = ts.astimezone(ET).strftime("%Y-%m-%d")
        if date_et != self._last_date:
            self._last_date = date_et
            # ── Prop Firm Guard: reset daily P&L on new trading day ────────
            if self._daily_pnl_date and self._daily_pnl_date != date_et:
                logger.info(
                    "New trading day %s — resetting daily P&L (prev: $%.0f)",
                    date_et, self._daily_pnl_usd,
                )
                self._daily_pnl_usd = 0.0
                self._guard_triggered = False
            self._daily_pnl_date = date_et

            nq_price = float(msg["close"])
            logger.info("New trading day %s — fetching GEX (NQ=%.2f)…", date_et, nq_price)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.on_day_open, nq_price)

        bar = Candle(
            timestamp=ts,
            open=float(msg["open"]),
            high=float(msg["high"]),
            low=float(msg["low"]),
            close=float(msg["close"]),
        )
        # on_bar() is synchronous; it calls on_trade_opened/closed internally
        # which schedule async sends via ensure_future
        self.on_bar(bar)

    # ── TCP server ────────────────────────────────────────────────────────────

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        logger.info("NinjaTrader connected from %s", peer)
        self._writer = writer

        try:
            async for raw_bytes in reader:
                line = raw_bytes.decode().strip()
                if line:
                    await self._process_message(line)
        except asyncio.IncompleteReadError:
            pass
        except Exception as exc:
            logger.exception("Client handler error: %s", exc)
        finally:
            logger.warning("NinjaTrader disconnected.")
            self._writer = None
            writer.close()

    async def run(self) -> None:
        server = await asyncio.start_server(
            self._handle_client, self._host, self._port
        )
        addr = server.sockets[0].getsockname()
        logger.info(
            "Waiting for NinjaTrader on %s:%s …\n"
            "  → Start PythonSignalStrategy on your NQ chart in NinjaTrader.",
            addr[0], addr[1],
        )
        async with server:
            await server.serve_forever()
