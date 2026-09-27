from algotrader.sizing import dynamic_profit_target, position_qty


def test_target_scales_with_equity():
    assert dynamic_profit_target(1.0, 1000.0) == 1.0
    assert dynamic_profit_target(1.0, 2000.0) == 2.0
    assert dynamic_profit_target(1.0, 500.0) == 0.5


def test_position_qty_scales_with_size_multiplier():
    assert position_qty(1000.0, 100.0, 1.5) > position_qty(1000.0, 100.0, 0.5)
