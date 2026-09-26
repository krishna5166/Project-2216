import asyncio
import logging

from alpaca.data.live import StockDataStream

logger = logging.getLogger(__name__)


class DataFeed:
    """Push-based live price feed over Alpaca's websocket stream (no polling)."""

    def __init__(self, api_key: str, secret_key: str, symbol: str):
        self._symbol = symbol
        self._stream = StockDataStream(api_key, secret_key)
        self._queue: asyncio.Queue[float] = asyncio.Queue()
        self._stream.subscribe_trades(self._on_trade, symbol)

    async def _on_trade(self, trade) -> None:
        await self._queue.put(float(trade.price))

    async def prices(self):
        """Async generator yielding each new trade price as it arrives."""
        # alpaca-py only exposes a blocking run() (asyncio.run(_run_forever())).
        # We're already inside an event loop, so we drive _run_forever() directly.
        run_task = asyncio.create_task(self._stream._run_forever())
        try:
            while True:
                price = await self._queue.get()
                yield price
        finally:
            run_task.cancel()
            await self._stream.close()
