"""Push-based last-trade feed. No REST on the tick path.

Uses the public StockDataStream.run() inside a worker thread instead of the
private _run_forever(), so a library bump cannot break the feed. The thread
bridges alpaca-py's internal event loop to this module's asyncio queue.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from alpaca.data.live import StockDataStream

logger = logging.getLogger(__name__)


class DataFeed:
    def __init__(self, api_key: str, secret_key: str, symbol: str):
        self._symbol = symbol
        self._stream = StockDataStream(api_key, secret_key)
        self._queue: asyncio.Queue[float] = asyncio.Queue(maxsize=1024)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._closed = False
        self._stream.subscribe_trades(self._on_trade, symbol)

    async def _on_trade(self, trade) -> None:
        price = float(trade.price)
        try:
            self._queue.put_nowait(price)
        except asyncio.QueueFull:
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self._queue.put_nowait(price)
            except asyncio.QueueFull:
                logger.warning("Dropping tick; queue still full")

    def _run_stream(self) -> None:
        # StockDataStream.run() owns its own event loop; run it in a thread.
        try:
            self._stream.run()
        except Exception:
            logger.exception("StockDataStream.run() exited")

    async def prices(self):
        self._loop = asyncio.get_running_loop()
        self._thread = threading.Thread(target=self._run_stream, daemon=True)
        self._thread.start()
        try:
            while not self._closed:
                try:
                    price = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    if self._thread is not None and not self._thread.is_alive():
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
