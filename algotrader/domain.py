"""Single domain model for the whole system.

Every engine, the meta-controller, execution, and tests speak these types.
No per-module Signal enums, no mapping dicts on the hot path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Signal(Enum):
    LONG = "long"
    SHORT = "short"
    HOLD = "hold"

    @property
    def direction(self) -> int:
        if self is Signal.LONG:
            return 1
        if self is Signal.SHORT:
            return -1
        return 0

    def opposite(self) -> Signal:
        if self is Signal.LONG:
            return Signal.SHORT
        if self is Signal.SHORT:
            return Signal.LONG
        return Signal.HOLD


class Vote:
    """Analytical-engine names for the same three signals."""

    UP = Signal.LONG
    DOWN = Signal.SHORT
    ABSTAIN = Signal.HOLD


class Side(Enum):
    LONG = "long"
    SHORT = "short"

    def as_signal(self) -> Signal:
        return Signal.LONG if self is Side.LONG else Signal.SHORT


@dataclass(slots=True)
class Position:
    symbol: str
    side: Side
    qty: float
    entry_price: float
    mark_price: float

    @property
    def unrealized_pl(self) -> float:
        signed = 1.0 if self.side is Side.LONG else -1.0
        return signed * (self.mark_price - self.entry_price) * self.qty

    @property
    def notional(self) -> float:
        return self.qty * self.mark_price


@dataclass(slots=True, frozen=True)
class Fill:
    symbol: str
    side: Side
    qty: float
    price: float
    realized_pl: float = 0.0


@dataclass(slots=True, frozen=True)
class AccountSnapshot:
    cash: float
    equity: float
    position: Position | None
