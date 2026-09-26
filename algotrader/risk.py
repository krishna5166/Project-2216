from collections import deque
from enum import Enum
from statistics import pstdev


class RiskLevel(Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


# Rule-based thresholds on trailing return volatility (stddev of pct changes).
# Placeholder values to tune once paper-trading data is available; the notes
# call for this to become AI-driven later, but this rule-based version
# unblocks the rest of the loop first.
_CONSERVATIVE_MAX = 0.0015
_MODERATE_MAX = 0.004

_SIZE_MULTIPLIER = {
    RiskLevel.CONSERVATIVE: 0.5,
    RiskLevel.MODERATE: 1.0,
    RiskLevel.AGGRESSIVE: 1.5,
}


class RiskEngine:
    """Scores trailing volatility and maps it to a risk level and position-size multiplier."""

    def __init__(self, window: int = 20):
        self._prices: deque[float] = deque(maxlen=window + 1)

    def update(self, price: float) -> tuple[RiskLevel, float]:
        self._prices.append(price)
        level = self._score()
        return level, _SIZE_MULTIPLIER[level]

    def _score(self) -> RiskLevel:
        if len(self._prices) < 3:
            return RiskLevel.CONSERVATIVE

        returns = [
            (b - a) / a
            for a, b in zip(self._prices, list(self._prices)[1:])
            if a != 0
        ]
        if not returns:
            return RiskLevel.CONSERVATIVE

        volatility = pstdev(returns)
        if volatility <= _CONSERVATIVE_MAX:
            return RiskLevel.CONSERVATIVE
        if volatility <= _MODERATE_MAX:
            return RiskLevel.MODERATE
        return RiskLevel.AGGRESSIVE
