import pytest

from algotrader.metrics import compute_metrics


def test_no_trades_gives_none_win_rate_and_sharpe():
    metrics = compute_metrics(equity_curve=[1000.0], trade_log=[])
    assert metrics.num_trades == 0
    assert metrics.win_rate is None
    assert metrics.total_pnl == 0.0


def test_win_rate_and_total_pnl():
    metrics = compute_metrics(equity_curve=[1000, 1010, 1005, 1015], trade_log=[10, -5, 10])
    assert metrics.num_trades == 3
    assert metrics.win_rate == pytest.approx(2 / 3)
    assert metrics.total_pnl == 15


def test_max_drawdown_detects_peak_to_trough():
    # equity rises to 1100, falls to 900 -> drawdown of 200/1100 ~= 18.18%
    equity_curve = [1000, 1100, 1000, 900, 950]
    metrics = compute_metrics(equity_curve, trade_log=[])
    assert metrics.max_drawdown_pct == pytest.approx(200 / 1100 * 100)


def test_max_drawdown_zero_for_monotonic_gains():
    metrics = compute_metrics(equity_curve=[1000, 1010, 1020, 1030], trade_log=[])
    assert metrics.max_drawdown_pct == 0.0


def test_sharpe_none_with_insufficient_data():
    assert compute_metrics(equity_curve=[1000.0], trade_log=[]).sharpe_ratio is None
    assert compute_metrics(equity_curve=[1000.0, 1010.0], trade_log=[]).sharpe_ratio is None


def test_sharpe_positive_for_steady_gains():
    equity_curve = [1000 * (1.001**i) for i in range(50)]
    metrics = compute_metrics(equity_curve, trade_log=[])
    assert metrics.sharpe_ratio > 0


def test_sharpe_none_for_zero_variance_returns():
    metrics = compute_metrics(equity_curve=[1000.0, 1000.0, 1000.0], trade_log=[])
    assert metrics.sharpe_ratio is None
