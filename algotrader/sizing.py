"""Position sizing and exit targets. Pure functions, no I/O."""

_REFERENCE_EQUITY = 1000.0
_BASE_POSITION_FRACTION = 0.1


def dynamic_profit_target(base_target: float, equity: float) -> float:
    if equity <= 0:
        return base_target
    return base_target * (equity / _REFERENCE_EQUITY)


def position_qty(equity: float, price: float, size_multiplier: float) -> float:
    if price <= 0 or equity <= 0:
        return 0.0
    dollars = equity * _BASE_POSITION_FRACTION * size_multiplier
    return round(dollars / price, 4)
