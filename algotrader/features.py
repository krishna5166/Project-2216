"""Feature extraction shared between the live analytical engine (streaming,
one price at a time) and offline training (a full historical price series).
Keeping this in one place means the model always sees the same features it
was trained on.

Six features (was three raw returns):
  ret_1, ret_5, ret_10, ret_20  - returns over 1/5/10/20 ticks
  realized_vol                 - std of the last 10 one-tick returns
  range                        - (max - min) / last over the lookback window
"""

import math

N_FEATURES = 6
# ret(20) indexes window[-1-20] = window[-21], so we need 21 prices.
MIN_HISTORY = 21


def extract_features(prices: list[float]) -> list[float] | None:
    """`prices` must end with the price to extract features for, and needs at
    least MIN_HISTORY points. Returns None if there isn't enough history.
    """
    if len(prices) < MIN_HISTORY:
        return None
    window = prices[-MIN_HISTORY:]
    last = window[-1]
    if not last:
        return None

    def ret(n: int) -> float:
        base = window[-1 - n]
        return (last - base) / base if base else 0.0

    r1 = ret(1)
    r5 = ret(5)
    r10 = ret(10)
    r20 = ret(20)

    rets = [
        (window[i] - window[i - 1]) / window[i - 1]
        for i in range(1, len(window))
        if window[i - 1]
    ]
    if rets:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / len(rets)
        vol = math.sqrt(var)
    else:
        vol = 0.0

    rng = (max(window) - min(window)) / last
    return [r1 * 100, r5 * 100, r10 * 100, r20 * 100, vol * 100, rng * 100]
