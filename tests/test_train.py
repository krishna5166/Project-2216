import random

from algotrader.features import N_FEATURES
from algotrader.train import build_dataset, label_trade_outcome, train_xgboost_model


def test_label_trade_outcome_hits_target_before_stop():
    # Price drifts up past target first.
    future = [100.1, 100.2, 100.6, 100.3]
    assert label_trade_outcome(100.0, future, target=0.5, stop=0.5) == 1


def test_label_trade_outcome_hits_stop_before_target():
    future = [99.9, 99.8, 99.4, 99.7]
    assert label_trade_outcome(100.0, future, target=0.5, stop=0.5) == 0


def test_label_trade_outcome_neither_within_horizon():
    future = [100.1, 100.2, 100.1, 100.0]
    assert label_trade_outcome(100.0, future, target=0.5, stop=0.5) == 0


def test_build_dataset_shapes_match():
    prices = [100.0 + i * 0.1 for i in range(60)]
    X, y = build_dataset(prices, label_horizon=5)
    assert len(X) == len(y)
    assert len(X) > 0
    assert all(len(row) == N_FEATURES for row in X)
    assert all(label in (0, 1) for label in y)


def test_build_dataset_uptrend_labels_mostly_up():
    prices = [100.0 + i * 0.1 for i in range(60)]
    _, y = build_dataset(prices, label_horizon=5, target=0.2, stop=0.2)
    assert sum(y) > len(y) * 0.8


def test_train_xgboost_model_on_synthetic_prices():
    random.seed(2)
    price = 100.0
    prices = []
    for _ in range(300):
        price = max(0.01, price + random.gauss(0, 0.3))
        prices.append(price)

    model = train_xgboost_model(prices, label_horizon=5, target=0.2, stop=0.2)
    p = model.predict_proba([0.0] * N_FEATURES)
    assert 0.0 <= p <= 1.0
