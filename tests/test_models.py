import random

import pytest

from algotrader.features import N_FEATURES
from algotrader.models import OnlineLogisticModel, XGBoostModel


def test_online_logistic_learns_a_simple_pattern():
    model = OnlineLogisticModel(n_features=1)
    # feature > 0 always means "up" (label=1), feature < 0 means "down" (label=0).
    random.seed(0)
    for _ in range(500):
        x = random.uniform(-1, 1)
        label = int(x > 0)
        model.update([x], label)

    assert model.predict_proba([0.8]) > 0.6
    assert model.predict_proba([-0.8]) < 0.4


def test_online_logistic_trainable_online_flag():
    assert OnlineLogisticModel().trainable_online is True


def test_online_logistic_default_feature_count():
    assert len(OnlineLogisticModel().weights) == N_FEATURES


def test_xgboost_not_trainable_online():
    assert XGBoostModel().trainable_online is False


def test_xgboost_untrained_predicts_neutral():
    model = XGBoostModel()
    assert model.predict_proba([0.1] * N_FEATURES) == 0.5


def test_xgboost_requires_minimum_training_examples():
    with pytest.raises(ValueError):
        XGBoostModel.train([[0.0] * N_FEATURES] * 5, [0, 1, 0, 1, 0])


def test_xgboost_train_predict_save_load(tmp_path):
    random.seed(1)
    X, y = [], []
    for _ in range(200):
        x = random.uniform(-1, 1)
        X.append([x, 0.0, 0.0, 0.0, 0.0, 0.0])
        y.append(int(x > 0))

    model = XGBoostModel.train(X, y)
    assert model.predict_proba([0.9, 0.0, 0.0, 0.0, 0.0, 0.0]) > 0.6
    assert model.predict_proba([-0.9, 0.0, 0.0, 0.0, 0.0, 0.0]) < 0.4

    path = str(tmp_path / "model.json")
    model.save(path)
    loaded = XGBoostModel.load(path)
    assert loaded.predict_proba([0.9, 0.0, 0.0, 0.0, 0.0, 0.0]) == pytest.approx(
        model.predict_proba([0.9, 0.0, 0.0, 0.0, 0.0, 0.0])
    )
