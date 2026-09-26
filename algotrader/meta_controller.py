"""Meta-controller: combines multiple engines' votes via adaptive multiplicative
weights (the Hedge / weighted-majority algorithm from online learning), instead
of trusting any single engine or a fixed rule.

Each engine casts a vote (LONG / SHORT / HOLD) with a confidence in [0, 1].
Votes are combined into a weighted score; the sign and magnitude decide the
final signal. After each closed trade, every engine that voted gets rewarded
or penalized based on whether its vote matched the trade's actual outcome,
and its weight is adjusted multiplicatively. Engines that abstained are left
unchanged. Over time, engines that are actually predictive earn more say —
the ensemble's mix isn't fixed in code, it's learned from live results.
"""

import math
from enum import Enum


class Signal(Enum):
    LONG = "long"
    SHORT = "short"
    HOLD = "hold"


_DIRECTION = {Signal.LONG: 1, Signal.SHORT: -1, Signal.HOLD: 0}


class MetaController:
    def __init__(self, engine_names: list[str], learning_rate: float = 0.3, decision_threshold: float = 0.3):
        self._weights = {name: 1.0 / len(engine_names) for name in engine_names}
        self._lr = learning_rate
        self._threshold = decision_threshold

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def combine(self, votes: dict[str, tuple[Signal, float]]) -> Signal:
        """votes: {engine_name: (signal, confidence)} -> final Signal."""
        score = 0.0
        for name, (signal, confidence) in votes.items():
            score += self._weights.get(name, 0.0) * _DIRECTION[signal] * confidence

        if score > self._threshold:
            return Signal.LONG
        if score < -self._threshold:
            return Signal.SHORT
        return Signal.HOLD

    def update_weights(self, votes: dict[str, tuple[Signal, float]], trade_direction: Signal) -> None:
        """Reward engines whose vote matched the trade's direction, penalize the rest.

        `trade_direction` is the direction that turned out profitable (LONG if
        the closed trade made money going long, etc.) — the ground truth for
        this round.
        """
        outcome = _DIRECTION[trade_direction]
        for name, (signal, confidence) in votes.items():
            if signal is Signal.HOLD or confidence == 0.0:
                continue
            agreement = _DIRECTION[signal] * outcome  # +1 matched, -1 opposed
            reward = agreement * confidence
            self._weights[name] *= math.exp(self._lr * reward)

        total = sum(self._weights.values())
        if total > 0:
            for name in self._weights:
                self._weights[name] /= total
