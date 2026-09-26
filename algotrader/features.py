"""Feature extraction shared between the live analytical engine (streaming,
one price at a time) and offline training (a full historical price series).
Keeping this in one place means the model always sees the same features it
was trained on.
"""


def extract_features(prices: list[float]) -> list[float] | None:
    """`prices` must end with the price to extract features for for, and
    needs at least 10 points of history before it. Returns None if there
    isn't enough history yet.
    """
    if len(prices) < 10:
        return None
    window = prices[-10:]
    ret_1 = (window[-1] - window[-2]) / window[-2] if window[-2] else 0.0
    ret_5 = (window[-1] - window[-6]) / window[-6] if window[-6] else 0.0
    momentum = (window[-1] - window[0]) / window[0] if window[0] else 0.0
    return [ret_1 * 100, ret_5 * 100, momentum * 100]
