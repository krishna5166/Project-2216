import random

from algotrader.backtest import (
    DEFAULT_STARTING_EQUITY,
    _equity_curve_from_pnls,
    run_backtest,
    run_walk_forward,
)
from algotrader.config import Config
from algotrader.metrics import compute_metrics


def _config():
    return Config(
        api_key=None,
        secret_key=None,
        symbol="TEST",
        base_profit_target=1.0,
        short_window=2,
        long_window=4,
        dry_run=True,
    )


def test_run_backtest_on_synthetic_prices():
    random.seed(0)
    prices = [100.0]
    for _ in range(200):
        prices.append(max(0.01, prices[-1] + random.gauss(0, 0.3)))
    result = run_backtest(prices, _config())
    assert result.ticks_processed == len(prices)
    assert result.starting_equity > 0


def test_run_walk_forward_returns_folds():
    random.seed(1)
    prices = [100.0]
    for _ in range(400):
        prices.append(max(0.01, prices[-1] + random.gauss(0, 0.3)))
    result = run_walk_forward(prices, train_frac=0.5, test_frac=0.1)
    assert len(result.folds) >= 1
    assert result.combined_metrics is not None
    assert result.combined_metrics.num_trades == sum(f.metrics.num_trades for f in result.folds)
    # Combined drawdown is a fraction of starting capital, never > 100%.
    assert 0.0 <= result.combined_metrics.max_drawdown_pct <= 100.0


def test_equity_curve_from_pnls_seeds_starting_capital():
    curve = _equity_curve_from_pnls([1.2, -1.0], starting_equity=1000.0)
    assert curve[0] == 1000.0
    assert curve[-1] == 1000.2
    metrics = compute_metrics(curve, [1.2, -1.0])
    assert metrics.max_drawdown_pct < 1.0


def test_equity_curve_from_pnls_default_is_sim_starting_equity():
    curve = _equity_curve_from_pnls([-1.2])
    assert curve[0] == DEFAULT_STARTING_EQUITY
