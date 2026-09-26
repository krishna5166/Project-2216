from collections import deque
from enum import Enum


class Signal(Enum):
    LONG = "long"
    SHORT = "short"
    HOLD = "hold"


class SmaCrossoverStrategy:
    """Classic short/long SMA crossover: golden cross -> long, death cross -> short.

    Only emits a signal on the tick where the crossover actually happens, so the
    bot doesn't repeatedly try to open a position it already holds.
    """

    def __init__(self, short_window: int, long_window: int):
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window")
        self.short_window = short_window
        self.long_window = long_window
        self._prices: deque[float] = deque(maxlen=long_window)
        self._prev_short_above_long: bool | None = None

    def update(self, price: float) -> Signal:
        self._prices.append(price)
        if len(self._prices) < self.long_window:
            return Signal.HOLD

        prices = list(self._prices)
        short_sma = sum(prices[-self.short_window :]) / self.short_window
        long_sma = sum(prices) / self.long_window
        short_above_long = short_sma > long_sma

        signal = Signal.HOLD
        if self._prev_short_above_long is not None:
            if short_above_long and not self._prev_short_above_long:
                signal = Signal.LONG
            elif not short_above_long and self._prev_short_above_long:
                signal = Signal.SHORT

        self._prev_short_above_long = short_above_long
        return signal
