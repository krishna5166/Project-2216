from algotrader.risk import RiskEngine, RiskLevel


def test_starts_conservative_with_insufficient_data():
    engine = RiskEngine()
    level, mult = engine.update(100.0)
    assert level is RiskLevel.CONSERVATIVE
    assert mult == 0.5


def test_stable_prices_stay_conservative():
    engine = RiskEngine()
    level = None
    for price in [100.0] * 10:
        level, _ = engine.update(price)
    assert level is RiskLevel.CONSERVATIVE


def test_volatile_prices_escalate_to_aggressive():
    engine = RiskEngine()
    level = None
    prices = [100, 105, 95, 110, 90, 115, 85, 120, 80]
    for price in prices:
        level, _ = engine.update(price)
    assert level is RiskLevel.AGGRESSIVE
