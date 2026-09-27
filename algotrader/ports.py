"""Ports: the only surface the bot loop is allowed to talk to.

Live Alpaca adapters and the in-memory simulator both implement these.
The bot never imports a broker SDK. That is what keeps backtest == live
decision logic and what stops REST calls from leaking onto every tick.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol

from .domain import AccountSnapshot, Fill, Position, Side


class MarketDataPort(Protocol):
    async def prices(self) -> AsyncIterator[float]:
        """Yield last trade prices. Must not block the caller on REST."""
        ...

    async def aclose(self) -> None:
        """Release the stream. Safe to call more than once."""
        ...


class OrderEvent:
    """A fill or reject reported by the broker, decoupled from the request.

    Instead of polling REST after submit/flatten, the execution layer can
    push these events (Alpaca trade updates, or the simulator firing them
    instantly). The bot consumes them to confirm fills without blocking the
    tick loop on synchronous sleeps.
    """

    def __init__(
        self,
        symbol: str,
        side: Side,
        qty: float,
        price: float,
        realized_pl: float = 0.0,
        accepted: bool = True,
    ):
        self.symbol = symbol
        self.side = side
        self.qty = qty
        self.price = price
        self.realized_pl = realized_pl
        self.accepted = accepted

    def as_fill(self) -> Fill | None:
        if not self.accepted:
            return None
        return Fill(
            symbol=self.symbol,
            side=self.side,
            qty=self.qty,
            price=self.price,
            realized_pl=self.realized_pl,
        )


class OrderEventPort(Protocol):
    """Optional push-based fill confirmation on top of ExecutionPort."""

    def drain_events(self) -> list[OrderEvent]:
        """Return and clear any events the broker has reported since last call."""
        ...


class ExecutionPort(Protocol):
    """Local-state execution.

    `snapshot()` and `mark()` are in-memory after startup reconcile.
    Broker IO happens only in `reconcile`, `submit`, and `flatten`.
    """

    def mark(self, price: float) -> None:
        ...

    def snapshot(self) -> AccountSnapshot:
        ...

    def position(self, symbol: str) -> Position | None:
        ...

    def submit(self, symbol: str, side: Side, qty: float, price: float) -> Fill | None:
        """Open or add. Returns a fill or None if the broker rejected."""
        ...

    def flatten(self, symbol: str, price: float) -> Fill | None:
        """Close the local (and remote) position. Fill.realized_pl is cash PnL."""
        ...

    def reconcile(self, symbol: str) -> AccountSnapshot:
        """Pull broker truth once (startup / after disconnect)."""
        ...
