"""Analytical engine: a price-direction predictor with conformal-calibrated
confidence, using a pluggable underlying model.

Two established techniques combined:
  1. A direction-prediction model — either an online logistic regression
     (SGD, learns live, zero setup) or an XGBoost classifier trained offline
     on recorded/historical data (see algotrader/models.py, algotrader/train.py).
  2. Split conformal prediction: instead of trusting the raw probability,
     we track how well past predictions matched outcomes and use that
     history to build a calibrated prediction *set* (could be {up}, {down},
     {up, down}, or {}) at a target confidence level. The engine only casts
     a directional vote when the set contains exactly one label — otherwise
     it abstains (HOLD) rather than guessing.

This gives statistically honest confidence instead of a hardcoded threshold.
The calibrator wraps whichever model is plugged in identically — it only
cares whether predictions matched outcomes, not how the model works
internally.
"""

from collections import deque
from enum import Enum

from .features import extract_features
from .models import OnlineLogisticModel


class Vote(Enum):
    UP = "up"
    DOWN = "down"
    ABSTAIN = "abstain"


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
    """Streaming feature extraction + pluggable model + conformal-calibrated vote."""

    def __init__(self, model=None, label_horizon: int = 5, calibration_window: int = 200):
        self._prices: deque[float] = deque(maxlen=20)
        self._label_horizon = label_horizon
        self._model = model or OnlineLogisticModel(n_features=3)
        self._calibrator = ConformalCalibrator(window=calibration_window)
        # (features, predicted_p, price_at_prediction_time, ticks_remaining)
        self._pending: deque[tuple[list[float], float, float, int]] = deque()

    def update(self, price: float) -> tuple[Vote, float]:
        self._prices.append(price)
        self._resolve_pending(price)

        features = extract_features(list(self._prices))
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
                if getattr(self._model, "trainable_online", False):
                    self._model.update(features, int(actual_up))
                self._calibrator.record(predicted_p, actual_up)
            else:
                still_pending.append((features, predicted_p, price_at_t, ticks_remaining))
        self._pending = still_pending
