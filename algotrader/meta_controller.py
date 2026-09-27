"""Hedge / weighted-majority over engine votes. No I/O."""

from __future__ import annotations

import math

from .domain import Signal


class MetaController:
    def __init__(
        self,
        engine_names: list[str],
        learning_rate: float = 0.3,
        decision_threshold: float = 0.3,
    ):
        n = max(1, len(engine_names))
        self._weights = {name: 1.0 / n for name in engine_names}
        self._lr = learning_rate
        self._threshold = decision_threshold

    @property
    def weights(self) -> dict[str, float]:
        return dict(self._weights)

    def load_weights(self, weights: dict[str, float]) -> None:
        merged = {name: self._weights.get(name, 0.0) for name in self._weights}
        for name, value in weights.items():
            if name in merged and value > 0:
                merged[name] = value
        total = sum(merged.values())
        if total > 0:
            self._weights = {k: v / total for k, v in merged.items()}

    def combine(self, votes: dict[str, tuple[Signal, float]]) -> Signal:
        score = 0.0
        for name, (signal, confidence) in votes.items():
            score += self._weights.get(name, 0.0) * signal.direction * confidence
        if score > self._threshold:
            return Signal.LONG
        if score < -self._threshold:
            return Signal.SHORT
        return Signal.HOLD

    def update_weights(self, votes: dict[str, tuple[Signal, float]], trade_direction: Signal) -> None:
        outcome = trade_direction.direction
        for name, (signal, confidence) in votes.items():
            if signal is Signal.HOLD or confidence == 0.0:
                continue
            agreement = signal.direction * outcome
            self._weights[name] *= math.exp(self._lr * agreement * confidence)

        total = sum(self._weights.values())
        if total > 0:
            for name in self._weights:
                self._weights[name] /= total
