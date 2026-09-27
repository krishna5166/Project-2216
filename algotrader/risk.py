"""Volatility targeting: size inverse to realized vol. High vol → smaller."""

from collections import deque
from enum import Enum
from statistics import pstdev


class RiskLevel(Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


_TARGET_VOL = 0.002
_MIN_MULT = 0.25
_MAX_MULT = 1.25
_CONSERVATIVE_MIN_VOL = 0.004
_MODERATE_MIN_VOL = 0.0015


class RiskEngine:
    def __init__(self, window: int = 20):
        self._prices: deque[float] = deque(maxlen=window + 1)

    def update(self, price: float) -> tuple[RiskLevel, float]:
        self._prices.append(price)
        vol = self._realized_vol()
        if vol is None:
            return RiskLevel.CONSERVATIVE, _MIN_MULT

        raw = _TARGET_VOL / max(vol, 1e-12)
        mult = min(_MAX_MULT, max(_MIN_MULT, raw))

        if vol >= _CONSERVATIVE_MIN_VOL:
            level = RiskLevel.CONSERVATIVE
        elif vol >= _MODERATE_MIN_VOL:
            level = RiskLevel.MODERATE
        else:
            level = RiskLevel.AGGRESSIVE
        return level, mult

    def _realized_vol(self) -> float | None:
        if len(self._prices) < 3:
            return None
        returns = []
        prev = None
        for price in self._prices:
            if prev and prev != 0:
                returns.append((price - prev) / prev)
            prev = price
        if len(returns) < 2:
            return None
        return pstdev(returns)
