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
