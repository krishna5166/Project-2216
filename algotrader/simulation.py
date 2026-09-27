"""In-process MarketDataPort + ExecutionPort (+ OrderEventPort).
Instant fill at mark ± slip; events fire immediately."""

from __future__ import annotations

import asyncio
import logging
import random

from .domain import AccountSnapshot, Fill, Position, Side
from .ports import OrderEvent

logger = logging.getLogger(__name__)


class SimulatedDataFeed:
    def __init__(self, start_price: float = 100.0, tick_delay: float = 0.2):
        self._price = start_price
        self._tick_delay = tick_delay
        self._closed = False

    async def prices(self):
        while not self._closed:
            if self._tick_delay:
                await asyncio.sleep(self._tick_delay)
            move = random.gauss(mu=0, sigma=self._price * 0.003)
            self._price = max(0.01, self._price + move)
            yield round(self._price, 2)

    async def aclose(self) -> None:
        self._closed = True


class SimulatedExecutionLayer:
    """One position, local cash, fill at the decision price plus slip_bps."""

    def __init__(self, starting_equity: float = 1000.0, slip_bps: float = 0.0):
        self._cash = starting_equity
        self._position: Position | None = None
        self._last_price = 0.0
        self._slip_bps = slip_bps
        self.trade_log: list[float] = []
        self._events: list[OrderEvent] = []

    def _fill_price(self, side: Side, price: float) -> float:
        if self._slip_bps <= 0:
            return price
        slip = price * (self._slip_bps / 10_000.0)
        return price + slip if side is Side.LONG else price - slip

    # -- OrderEventPort -------------------------------------------------------
    def drain_events(self) -> list[OrderEvent]:
        events, self._events = self._events, []
        return events

    def _emit(self, event: OrderEvent) -> None:
        self._events.append(event)

    # -- ExecutionPort --------------------------------------------------------
    def mark(self, price: float) -> None:
        self._last_price = price
        if self._position is not None:
            self._position.mark_price = price

    def snapshot(self) -> AccountSnapshot:
        unreal = self._position.unrealized_pl if self._position else 0.0
        return AccountSnapshot(cash=self._cash, equity=self._cash + unreal, position=self._position)

    def position(self, symbol: str) -> Position | None:
        return self._position

    def submit(self, symbol: str, side: Side, qty: float, price: float) -> Fill | None:
        if self._position is not None or qty <= 0:
            return None
        px = self._fill_price(side, price)
        self._position = Position(symbol=symbol, side=side, qty=qty, entry_price=px, mark_price=px)
        event = OrderEvent(symbol, side, qty, px, accepted=True)
        self._emit(event)
        logger.info("[SIM] fill %s %s qty=%s @ %.4f", side.value, symbol, qty, px)
        return event.as_fill()

    def flatten(self, symbol: str, price: float) -> Fill | None:
        pos = self._position
        if pos is None:
            return None
        close_side = Side.SHORT if pos.side is Side.LONG else Side.LONG
        px = self._fill_price(close_side, price)
        signed = 1.0 if pos.side is Side.LONG else -1.0
        pnl = signed * (px - pos.entry_price) * pos.qty
        self._cash += pnl
        self.trade_log.append(pnl)
        self._position = None
        event = OrderEvent(symbol, close_side, pos.qty, px, realized_pl=pnl, accepted=True)
        self._emit(event)
        logger.info("[SIM] flatten %s pnl=%.2f cash=%.2f", symbol, pnl, self._cash)
        return event.as_fill()

    def reconcile(self, symbol: str) -> AccountSnapshot:
        return self.snapshot()

    def mark_price(self, price: float) -> None:
        self.mark(price)

    def get_equity(self) -> float:
        return self.snapshot().equity

    def get_open_position(self, symbol: str):
        return self.position(symbol)

    def unrealized_pl(self, position: Position) -> float:
        return position.unrealized_pl

    def open_long(self, symbol: str, qty: float, price: float) -> None:
        self.submit(symbol, Side.LONG, qty, price)

    def open_short(self, symbol: str, qty: float, price: float) -> None:
        self.submit(symbol, Side.SHORT, qty, price)

    def close_position(self, symbol: str) -> None:
        self.flatten(symbol, self._last_price or (self._position.mark_price if self._position else 0.0))
