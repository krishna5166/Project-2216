from algotrader.domain import Side
from algotrader.ports import OrderEvent


def test_order_event_as_fill_when_accepted():
    event = OrderEvent("AAPL", Side.LONG, 1.0, 100.5, realized_pl=0.0, accepted=True)
    fill = event.as_fill()
    assert fill is not None
    assert fill.symbol == "AAPL"
    assert fill.side is Side.LONG
    assert fill.price == 100.5


def test_order_event_as_fill_none_when_rejected():
    event = OrderEvent("AAPL", Side.LONG, 1.0, 100.5, accepted=False)
    assert event.as_fill() is None
