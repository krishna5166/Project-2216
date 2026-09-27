"""SMA crossover on incremental running sums — O(1) per tick."""

from collections import deque

from .domain import Signal


class SmaCrossoverStrategy:
    """Golden cross -> long, death cross -> short. Emits only on the cross tick."""

    def __init__(self, short_window: int, long_window: int):
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window")
        self.short_window = short_window
        self.long_window = long_window
        self._prices: deque[float] = deque()
        self._long_sum = 0.0
        self._short_sum = 0.0
        self._prev_short_above_long: bool | None = None

    def update(self, price: float) -> Signal:
        self._prices.append(price)
        self._long_sum += price
        self._short_sum += price

        if len(self._prices) > self.long_window:
            dropped = self._prices.popleft()
            self._long_sum -= dropped

        n = len(self._prices)
        if n > self.short_window:
            aged = self._prices[-self.short_window - 1]
            self._short_sum -= aged

        if n < self.long_window:
            return Signal.HOLD

        short_sma = self._short_sum / self.short_window
        long_sma = self._long_sum / self.long_window
        short_above_long = short_sma > long_sma

        signal = Signal.HOLD
        if self._prev_short_above_long is not None:
            if short_above_long and not self._prev_short_above_long:
                signal = Signal.LONG
            elif not short_above_long and self._prev_short_above_long:
                signal = Signal.SHORT

        self._prev_short_above_long = short_above_long
        return signal
