from algotrader.external_signals import ExternalSignalCache


def test_defaults_to_neutral_zero_confidence():
    cache = ExternalSignalCache()
    signal = cache.get()
    assert signal.value == 0.0
    assert signal.confidence == 0.0
    assert signal.stale is True


def test_returns_set_value_when_fresh():
    cache = ExternalSignalCache(max_age_seconds=300)
    cache.set(value=0.8, confidence=0.9)
    signal = cache.get()
    assert signal.value == 0.8
    assert signal.confidence == 0.9
    assert signal.stale is False


def test_clamps_out_of_range_values():
    cache = ExternalSignalCache()
    cache.set(value=5.0, confidence=2.0)
    signal = cache.get()
    assert signal.value == 1.0
    assert signal.confidence == 1.0


def test_stale_signal_reports_zero_confidence():
    cache = ExternalSignalCache(max_age_seconds=0)
    cache.set(value=0.5, confidence=0.9)
    signal = cache.get()
    assert signal.stale is True
    assert signal.confidence == 0.0
