from algotrader.risk import RiskEngine, RiskLevel


def test_starts_conservative_with_insufficient_data():
    engine = RiskEngine()
    level, mult = engine.update(100.0)
    assert level is RiskLevel.CONSERVATIVE
    assert mult == 0.25


def test_stable_prices_size_up():
    engine = RiskEngine()
    level = None
    mult = None
    for price in [100.0] * 10:
        level, mult = engine.update(price)
    assert level is RiskLevel.AGGRESSIVE
    assert mult == 1.25


def test_volatile_prices_size_down():
    engine = RiskEngine()
    level = None
    mult = None
    for price in [100, 105, 95, 110, 90, 115, 85, 120, 80]:
        level, mult = engine.update(price)
    assert level is RiskLevel.CONSERVATIVE
    assert mult == 0.25
