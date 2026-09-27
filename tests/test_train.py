import random

from algotrader.train import build_dataset, train_xgboost_model


def test_build_dataset_shapes_match():
    prices = [100.0 + i * 0.1 for i in range(50)]
    X, y = build_dataset(prices, label_horizon=5)
    assert len(X) == len(y)
    assert len(X) > 0
    assert all(len(row) == 3 for row in X)
    assert all(label in (0, 1) for label in y)


def test_build_dataset_labels_uptrend_as_up():
    prices = [100.0 + i for i in range(50)]  # strictly increasing
    _, y = build_dataset(prices, label_horizon=5)
    assert all(label == 1 for label in y)


def test_train_xgboost_model_on_synthetic_prices():
    random.seed(2)
    price = 100.0
    prices = []
    for _ in range(300):
        price = max(0.01, price + random.gauss(0, 0.3))
        prices.append(price)

    model = train_xgboost_model(prices, label_horizon=5)
    # Just needs to produce a usable probability, not any specific accuracy
    # claim — real predictive value is unverified until trained on real data.
    p = model.predict_proba([1.0, 1.0, 1.0])
    assert 0.0 <= p <= 1.0
