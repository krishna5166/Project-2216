from algotrader.bot import dynamic_profit_target, position_qty


def test_target_scales_with_equity():
    assert dynamic_profit_target(1.0, 1000.0) == 1.0
    assert dynamic_profit_target(1.0, 2000.0) == 2.0
    assert dynamic_profit_target(1.0, 500.0) == 0.5


def test_position_qty_scales_with_size_multiplier():
    equity = 1000.0
    price = 100.0
    conservative_qty = position_qty(equity, price, size_multiplier=0.5)
    aggressive_qty = position_qty(equity, price, size_multiplier=1.5)
    assert aggressive_qty > conservative_qty
