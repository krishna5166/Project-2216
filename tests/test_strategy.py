from algotrader.strategy import SmaCrossoverStrategy
from algotrader.domain import Signal


def test_holds_until_window_filled():
    strategy = SmaCrossoverStrategy(short_window=2, long_window=4)
    for price in [10, 10, 10]:
        assert strategy.update(price) is Signal.HOLD


def test_golden_cross_emits_long():
    strategy = SmaCrossoverStrategy(short_window=2, long_window=4)
    for price in [10, 10, 10, 10]:
        strategy.update(price)
    assert strategy.update(20) is Signal.LONG


def test_death_cross_emits_short():
    strategy = SmaCrossoverStrategy(short_window=2, long_window=4)
    for price in [10, 10, 10, 10, 30, 1]:
        strategy.update(price)
    assert strategy.update(1) is Signal.SHORT


def test_no_repeated_signal_without_new_cross():
    strategy = SmaCrossoverStrategy(short_window=2, long_window=4)
    for price in [10, 10, 10, 10]:
        strategy.update(price)
    strategy.update(20)
    assert strategy.update(21) is Signal.HOLD
