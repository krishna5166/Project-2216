"""Push-based last-trade feed. No REST on the tick path.

Uses the public StockDataStream.run() inside a worker thread instead of the
private _run_forever(), so a library bump cannot break the feed.

The stream thread owns its own event loop (run() calls asyncio.run internally).
Trade callbacks therefore cannot touch an asyncio.Queue bound to the bot loop.
A thread-safe queue.Queue is the bridge; prices() drains it on the bot loop.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading

from alpaca.data.live import StockDataStream

logger = logging.getLogger(__name__)


class DataFeed:
    def __init__(self, api_key: str, secret_key: str, symbol: str):
        self._symbol = symbol
        self._stream = StockDataStream(api_key, secret_key)
        self._buf: queue.Queue[float] = queue.Queue(maxsize=1024)
        self._thread: threading.Thread | None = None
        self._closed = False
        self._stream.subscribe_trades(self._on_trade, symbol)

    def _put_price(self, price: float) -> None:
        try:
            self._buf.put_nowait(price)
        except queue.Full:
            try:
                self._buf.get_nowait()
            except queue.Empty:
                pass
            try:
                self._buf.put_nowait(price)
            except queue.Full:
                logger.warning("Dropping tick; queue still full")

    async def _on_trade(self, trade) -> None:
        self._put_price(float(trade.price))

    def _run_stream(self) -> None:
        try:
            self._stream.run()
        except Exception:
            logger.exception("StockDataStream.run() exited")

    async def prices(self):
        self._thread = threading.Thread(target=self._run_stream, daemon=True, name="alpaca-stream")
        self._thread.start()
        try:
            while not self._closed:
                try:
                    price = await asyncio.to_thread(self._buf.get, True, 1.0)
                except queue.Empty:
                    if self._thread is not None and not self._thread.is_alive() and not self._closed:
                        raise RuntimeError("Data stream thread died")
                    continue
                yield price
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        self._closed = True
        try:
            await self._stream.close()
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
