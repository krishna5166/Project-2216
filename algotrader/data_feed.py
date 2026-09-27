"""Push-based last-trade feed. No REST on the tick path."""

from __future__ import annotations

import asyncio
import logging

from alpaca.data.live import StockDataStream

logger = logging.getLogger(__name__)


class DataFeed:
    def __init__(self, api_key: str, secret_key: str, symbol: str):
        self._symbol = symbol
        self._stream = StockDataStream(api_key, secret_key)
        self._queue: asyncio.Queue[float] = asyncio.Queue(maxsize=1024)
        self._stream.subscribe_trades(self._on_trade, symbol)
        self._run_task: asyncio.Task | None = None

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

    async def prices(self):
        self._run_task = asyncio.create_task(self._stream._run_forever())
        try:
            while True:
                yield await self._queue.get()
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        if self._run_task is not None:
            self._run_task.cancel()
            self._run_task = None
        await self._stream.close()
