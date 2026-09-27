import asyncio

from algotrader.domain import Side
from algotrader.simulation import SimulatedDataFeed, SimulatedExecutionLayer


def test_simulated_execution_tracks_long_pnl():
    execution = SimulatedExecutionLayer(starting_equity=1000.0)
    execution.open_long("AAPL", qty=2, price=100.0)
    execution.mark(105.0)
    position = execution.position("AAPL")
    assert execution.unrealized_pl(position) == 10.0
    execution.close_position("AAPL")
    assert execution.position("AAPL") is None
    assert execution.get_equity() == 1010.0


def test_simulated_execution_tracks_short_pnl():
    execution = SimulatedExecutionLayer(starting_equity=1000.0)
    execution.open_short("AAPL", qty=2, price=100.0)
    execution.mark(95.0)
    assert execution.unrealized_pl(execution.position("AAPL")) == 10.0


def test_submit_refuses_second_position():
    execution = SimulatedExecutionLayer()
    assert execution.submit("AAPL", Side.LONG, 1, 100.0) is not None
    assert execution.submit("AAPL", Side.LONG, 1, 100.0) is None


def test_simulated_data_feed_yields_prices():
    async def collect():
        feed = SimulatedDataFeed(start_price=100.0, tick_delay=0)
        prices = []
        async for price in feed.prices():
            prices.append(price)
            if len(prices) >= 5:
                break
        await feed.aclose()
        return prices

    prices = asyncio.run(collect())
    assert len(prices) == 5
    assert all(p > 0 for p in prices)
