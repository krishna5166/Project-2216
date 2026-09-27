from types import SimpleNamespace

from algotrader.domain import Side
from algotrader.execution import ExecutionLayer


class _Missing(Exception):
    status_code = 404


class DelayedBroker:
    """Broker that 404s N times after submit, and keeps a position N times after close."""

    def __init__(self, open_404s: int = 2, close_still_open: int = 2):
        self.open_404s = open_404s
        self.close_still_open = close_still_open
        self._lookups = 0
        self._close_lookups = 0
        self._pending_open = False
        self._pending_close = False
        self._raw = None
        self.submit_calls = 0
        self.close_calls = 0

    def get_account(self):
        return SimpleNamespace(cash=1000.0)

    def submit_order(self, order):
        self.submit_calls += 1
        self._pending_open = True
        self._lookups = 0

    def close_position(self, symbol):
        self.close_calls += 1
        self._pending_close = True
        self._close_lookups = 0

    def get_open_position(self, symbol):
        if self._pending_close:
            self._close_lookups += 1
            if self._close_lookups <= self.close_still_open and self._raw is not None:
                return self._raw
            self._raw = None
            self._pending_close = False
            raise _Missing("position not found")
        if self._pending_open:
            self._lookups += 1
            if self._lookups <= self.open_404s:
                raise _Missing("position not found")
            self._raw = SimpleNamespace(
                qty=1.0,
                side="long",
                avg_entry_price=100.5,
                current_price=100.5,
            )
            self._pending_open = False
            return self._raw
        if self._raw is None:
            raise _Missing("position not found")
        return self._raw


def _layer(broker, delays=(0.0, 0.0, 0.0)):
    return ExecutionLayer(client=broker, sleep=lambda _d: None, poll_delays=delays)


def test_submit_polls_through_initial_404s_and_does_not_double_send():
    broker = DelayedBroker(open_404s=2, close_still_open=0)
    exe = _layer(broker)
    fill = exe.submit("AAPL", Side.LONG, 1.0, 100.0)
    assert fill is not None
    assert fill.price == 100.5
    assert exe.position("AAPL") is not None
    assert broker.submit_calls == 1
    assert exe.submit("AAPL", Side.LONG, 1.0, 100.0) is None
    assert broker.submit_calls == 1


def test_submit_keeps_reservation_if_broker_never_shows_position():
    broker = DelayedBroker(open_404s=99, close_still_open=0)
    exe = _layer(broker, delays=(0.0,))
    fill = exe.submit("AAPL", Side.LONG, 1.0, 100.0)
    assert fill is not None
    assert exe.position("AAPL") is not None
    assert exe.submit("AAPL", Side.LONG, 1.0, 101.0) is None
    assert broker.submit_calls == 1


def test_flatten_polls_until_position_gone_before_recording_fill():
    broker = DelayedBroker(open_404s=0, close_still_open=2)
    exe = _layer(broker)
    assert exe.submit("AAPL", Side.LONG, 1.0, 100.0) is not None
    fill = exe.flatten("AAPL", 101.0)
    assert fill is not None
    assert fill.realized_pl == 0.5
    assert exe.position("AAPL") is None
    assert broker.close_calls == 1


def test_flatten_does_not_record_fill_if_position_still_open():
    broker = DelayedBroker(open_404s=0, close_still_open=99)
    exe = _layer(broker, delays=(0.0,))
    exe.submit("AAPL", Side.LONG, 1.0, 100.0)
    fill = exe.flatten("AAPL", 101.0)
    assert fill is None
    assert exe.position("AAPL") is not None
    assert broker.close_calls == 1
