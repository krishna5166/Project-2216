import pytest

from algotrader.config import load_config


def test_dry_run_does_not_require_api_keys(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    config = load_config(dry_run_override=True)
    assert config.dry_run is True
    assert config.api_key is None
    assert config.paper is True


def test_live_mode_requires_api_keys(monkeypatch):
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        load_config(dry_run_override=False)
