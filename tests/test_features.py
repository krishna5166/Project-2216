from algotrader.features import MIN_HISTORY, N_FEATURES, extract_features


def test_extract_features_needs_min_history():
    assert extract_features([100.0] * (MIN_HISTORY - 1)) is None
    feats = extract_features([100.0 + i * 0.1 for i in range(MIN_HISTORY)])
    assert feats is not None
    assert len(feats) == N_FEATURES == 6


def test_extract_features_ret20_does_not_indexerror_on_exact_window():
    prices = [100.0 + i for i in range(MIN_HISTORY)]
    feats = extract_features(prices)
    assert feats is not None
    # last = 100+20 = 120, 20 ticks back = 100, ret_20 = 20/100*100 = 20
    assert feats[3] == 20.0


def test_extract_features_uptrend_positive_returns():
    feats = extract_features([100.0 + i for i in range(30)])
    assert feats[0] > 0
    assert feats[3] > 0


def test_extract_features_flat_is_near_zero():
    feats = extract_features([100.0] * 30)
    assert all(abs(x) < 1e-9 for x in feats)
