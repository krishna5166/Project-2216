import random

from algotrader.analytics import AnalyticalEngine, ConformalCalibrator, Vote


def test_abstains_with_insufficient_history():
    engine = AnalyticalEngine()
    vote, conf = engine.update(100.0)
    assert vote is Vote.ABSTAIN
    assert conf == 0.0


def test_abstains_until_calibrated_even_with_long_history():
    engine = AnalyticalEngine(calibration_window=200)
    random.seed(0)
    price = 100.0
    votes = []
    for _ in range(60):
        price += random.gauss(0, 0.5)
        vote, _ = engine.update(price)
        votes.append(vote)
    # Calibration window (200 resolved labels) can't fill from only 60 ticks.
    assert all(v is Vote.ABSTAIN for v in votes)


def test_conformal_calibrator_requires_min_samples():
    calibrator = ConformalCalibrator(window=200)
    assert calibrator.is_calibrated() is False
    for _ in range(30):
        calibrator.record(0.6, True)
        calibrator.record(0.4, False)
    assert calibrator.is_calibrated() is True


def test_conformal_prediction_set_for_confident_correct_model():
    calibrator = ConformalCalibrator(window=200, alpha=0.1)
    for _ in range(100):
        calibrator.record(0.95, True)
        calibrator.record(0.05, False)
    # A new strongly "up" prediction should land in {"up"} only.
    assert calibrator.prediction_set(0.95) == {"up"}
