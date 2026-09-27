"""Pluggable direction-prediction models for the analytical engine.

Both implement `predict_proba(features) -> P(up)`. `OnlineLogisticModel`
also supports per-tick `update()` (trainable_online=True) so the engine can
learn live with zero setup. `XGBoostModel` is trained offline in a batch
(trainable_online=False) — stronger predictive power from a real ensemble
model, at the cost of needing a training run against recorded/historical
data before it's useful; see algotrader/train.py.

The conformal calibrator in analytics.py wraps either one identically —
calibration is based on how well predictions matched outcomes, not on how
the model works internally.
"""

import math

from .features import N_FEATURES


def _sigmoid(z: float) -> float:
    if z < -50:
        return 0.0
    if z > 50:
        return 1.0
    return 1.0 / (1.0 + math.exp(-z))


class OnlineLogisticModel:
    """Binary logistic regression trained one example at a time via SGD."""

    trainable_online = True

    def __init__(self, n_features: int = N_FEATURES, lr: float = 0.05):
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


class XGBoostModel:
    """Gradient-boosted classifier trained offline on a batch of (features, label) pairs."""

    trainable_online = False

    def __init__(self, booster=None):
        self._booster = booster

    def predict_proba(self, features: list[float]) -> float:
        if self._booster is None:
            return 0.5
        import xgboost as xgb

        dmatrix = xgb.DMatrix([features])
        return float(self._booster.predict(dmatrix)[0])

    @classmethod
    def train(cls, X: list[list[float]], y: list[int], **params) -> "XGBoostModel":
        import xgboost as xgb

        if len(X) < 20:
            raise ValueError(f"need at least 20 training examples, got {len(X)}")

        dtrain = xgb.DMatrix(X, label=y)
        booster_params = {
            "objective": "binary:logistic",
            "max_depth": 3,
            "eta": 0.1,
            "eval_metric": "logloss",
            **params,
        }
        booster = xgb.train(booster_params, dtrain, num_boost_round=50)
        return cls(booster)

    def save(self, path: str) -> None:
        if self._booster is None:
            raise ValueError("cannot save an untrained model")
        self._booster.save_model(path)

    @classmethod
    def load(cls, path: str) -> "XGBoostModel":
        import xgboost as xgb

        booster = xgb.Booster()
        booster.load_model(path)
        return cls(booster)
