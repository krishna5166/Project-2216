import asyncio
import queue
from types import SimpleNamespace

from algotrader.data_feed import DataFeed


def test_put_price_is_thread_safe_queue_not_asyncio_queue():
    feed = DataFeed.__new__(DataFeed)
    feed._buf = queue.Queue(maxsize=2)
    feed._put_price(1.0)
    feed._put_price(2.0)
    feed._put_price(3.0)  # full -> drop oldest
    assert feed._buf.get_nowait() == 2.0
    assert feed._buf.get_nowait() == 3.0


def test_on_trade_writes_to_thread_safe_buffer():
    feed = DataFeed.__new__(DataFeed)
    feed._buf = queue.Queue(maxsize=8)
    asyncio.run(feed._on_trade(SimpleNamespace(price=101.25)))
    assert feed._buf.get_nowait() == 101.25
