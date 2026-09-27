from algotrader.features import N_FEATURES, extract_features


def test_extract_features_needs_twenty_points():
    assert extract_features([100.0] * 19) is None
    feats = extract_features([100.0 + i * 0.1 for i in range(20)])
    assert feats is not None
    assert len(feats) == N_FEATURES == 6


def test_extract_features_uptrend_positive_returns():
    feats = extract_features([100.0 + i for i in range(30)])
    assert feats[0] > 0  # ret_1
    assert feats[3] > 0  # ret_20


def test_extract_features_flat_is_near_zero():
    feats = extract_features([100.0] * 30)
    assert all(abs(x) < 1e-9 for x in feats)
