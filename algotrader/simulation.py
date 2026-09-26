"""In-process stand-ins for the data feed and execution layer.

Let the full strategy/risk/bot loop run and be demoed with zero API keys.
Same call surface as DataFeed / ExecutionLayer so bot.py doesn't need to
branch on dry-run beyond picking which one to construct.
"""

import asyncio
import logging
import random
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class SimulatedDataFeed:
    """Random-walk price generator standing in for the live websocket feed."""

    def __init__(self, start_price: float = 100.0, tick_delay: float = 0.2):
        self._price = start_price
        self._tick_delay = tick_delay

    async def prices(self):
        while True:
            await asyncio.sleep(self._tick_delay)
            move = random.gauss(mu=0, sigma=self._price * 0.003)
            self._price = max(0.01, self._price + move)
            yield round(self._price, 2)


@dataclass
class _SimPosition:
    qty: float
    side: str  # "long" or "short"
    entry_price: float
    current_price: float

    @property
    def unrealized_pl(self) -> float:
        direction = 1 if self.side == "long" else -1
        return direction * (self.current_price - self.entry_price) * self.qty


class SimulatedExecutionLayer:
    """In-memory paper-paper trading: no network calls, tracks one position at a time."""

    def __init__(self, starting_equity: float = 1000.0):
        self._equity = starting_equity
        self._position: _SimPosition | None = None

    def get_equity(self) -> float:
        return self._equity

    def get_open_position(self, symbol: str):
        return self._position

    def unrealized_pl(self, position: _SimPosition) -> float:
        return position.unrealized_pl

    def mark_price(self, price: float) -> None:
        if self._position is not None:
            self._position.current_price = price

    def open_long(self, symbol: str, qty: float, price: float) -> None:
        logger.info("[SIM] opening long %s qty=%s @ %.2f", symbol, qty, price)
        self._position = _SimPosition(qty=qty, side="long", entry_price=price, current_price=price)

    def open_short(self, symbol: str, qty: float, price: float) -> None:
        logger.info("[SIM] opening short %s qty=%s @ %.2f", symbol, qty, price)
        self._position = _SimPosition(qty=qty, side="short", entry_price=price, current_price=price)

    def close_position(self, symbol: str) -> None:
        if self._position is not None:
            self._equity += self._position.unrealized_pl
            logger.info(
                "[SIM] closing %s pnl=%.2f new_equity=%.2f",
                symbol,
                self._position.unrealized_pl,
                self._equity,
            )
        self._position = None
