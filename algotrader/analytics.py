"""Analytical engine: an online-learning price-direction predictor with
conformal-calibrated confidence.

Two established techniques combined:
  1. Online logistic regression (SGD) predicting P(price up over next N ticks)
     from simple streaming features — no batch retraining needed.
  2. Split conformal prediction: instead of trusting the raw probability,
     we track how well past predictions matched outcomes and use that
     history to build a calibrated prediction *set* (could be {up}, {down},
     {up, down}, or {}) at a target confidence level. The engine only casts
     a directional vote when the set contains exactly one label — otherwise
     it abstains (HOLD) rather than guessing.

This gives statistically honest confidence instead of a hardcoded threshold,
and self-corrects online as more data arrives — most retail bots use a
static rule (like the SMA crossover) with no notion of calibrated confidence
or abstention.
"""

import math
from collections import deque
from enum import Enum


class Vote(Enum):
    UP = "up"
    DOWN = "down"
    ABSTAIN = "abstain"


def _sigmoid(z: float) -> float:
    if z < -50:
        return 0.0
    if z > 50:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


class _OnlineLogisticModel:
    """Binary logistic regression trained one example at a time via SGD."""

    def __init__(self, n_features: int, lr: float = 0.05):
        self.weights = [0.0] * n_features
        self.bias = 0.0
        self.lr = lr

    def predict_proba(self, features: list[float]) -> float:
        z = self.bias + sum(w * x for w, x in zip(self.weights, features))
        return _sigmoid(z)

    def update(self, features: list[float], label: int) -> None:
        p = self.predict_proba(features)
        error = p - label
        for i, x in enumerate(features):
            self.weights[i] -= self.lr * error * x
        self.bias -= self.lr * error


class ConformalCalibrator:
    """Split conformal prediction over a sliding window of past (p, outcome) pairs."""

    def __init__(self, window: int = 200, alpha: float = 0.15):
        self._up_scores: deque[float] = deque(maxlen=window)
        self._down_scores: deque[float] = deque(maxlen=window)
        self.alpha = alpha

    def record(self, predicted_p_up: float, actual_up: bool) -> None:
        # Nonconformity score for the label that actually occurred: 1 - p(true label).
        if actual_up:
            self._up_scores.append(1 - predicted_p_up)
        else:
            self._down_scores.append(1 - (1 - predicted_p_up))

    def is_calibrated(self, min_samples: int = 30) -> bool:
        return len(self._up_scores) >= min_samples and len(self._down_scores) >= min_samples

    def prediction_set(self, predicted_p_up: float) -> set[str]:
        """Which labels are statistically plausible at (1 - alpha) confidence."""
        threshold_up = self._quantile(self._up_scores, 1 - self.alpha)
        threshold_down = self._quantile(self._down_scores, 1 - self.alpha)

        result = set()
        if (1 - predicted_p_up) <= threshold_up:
            result.add("up")
        if predicted_p_up <= threshold_down:
            result.add("down")
        return result

    @staticmethod
    def _quantile(scores: deque, q: float) -> float:
        if not scores:
            return 1.0
        ordered = sorted(scores)
        idx = min(len(ordered) - 1, max(0, int(q * len(ordered))))
        return ordered[idx]


class AnalyticalEngine:
    """Streaming feature extraction + online model + conformal-calibrated vote."""

    def __init__(self, label_horizon: int = 5, calibration_window: int = 200):
        self._prices: deque[float] = deque(maxlen=20)
        self._label_horizon = label_horizon
        self._model = _OnlineLogisticModel(n_features=3)
        self._calibrator = ConformalCalibrator(window=calibration_window)
        # (features, predicted_p, price_at_prediction_time, ticks_remaining)
        self._pending: deque[tuple[list[float], float, float, int]] = deque()

    def _features(self) -> list[float] | None:
        if len(self._prices) < 10:
            return None
        prices = list(self._prices)
        ret_1 = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] else 0.0
        ret_5 = (prices[-1] - prices[-6]) / prices[-6] if prices[-6] else 0.0
        momentum = (prices[-1] - prices[-10]) / prices[-10] if prices[-10] else 0.0
        return [ret_1 * 100, ret_5 * 100, momentum * 100]

    def update(self, price: float) -> tuple[Vote, float]:
        self._prices.append(price)
        self._resolve_pending(price)

        features = self._features()
        if features is None:
            return Vote.ABSTAIN, 0.0

        predicted_p = self._model.predict_proba(features)
        self._pending.append((features, predicted_p, price, self._label_horizon))

        if not self._calibrator.is_calibrated():
            return Vote.ABSTAIN, 0.0

        labels = self._calibrator.prediction_set(predicted_p)
        if labels == {"up"}:
            return Vote.UP, 1 - self._calibrator.alpha
        if labels == {"down"}:
            return Vote.DOWN, 1 - self._calibrator.alpha
        return Vote.ABSTAIN, 0.0

    def _resolve_pending(self, current_price: float) -> None:
        still_pending = deque()
        while self._pending:
            features, predicted_p, price_at_t, ticks_remaining = self._pending.popleft()
            ticks_remaining -= 1
            if ticks_remaining <= 0:
                actual_up = current_price > price_at_t
                self._model.update(features, int(actual_up))
                self._calibrator.record(predicted_p, actual_up)
            else:
                still_pending.append((features, predicted_p, price_at_t, ticks_remaining))
        self._pending = still_pending
