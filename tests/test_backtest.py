import random

import pytest

from algotrader.backtest import load_prices_from_csv, run_backtest


def test_run_backtest_requires_nonempty_prices():
    with pytest.raises(ValueError):
        run_backtest([])


def test_run_backtest_returns_result_over_random_walk():
    random.seed(42)
    price = 100.0
    prices = []
    for _ in range(200):
        price = max(0.01, price + random.gauss(0, 0.3))
        prices.append(round(price, 2))

    result = run_backtest(prices)
    assert result.ticks_processed == 200
    assert result.starting_equity == 1000.0
    assert isinstance(result.final_equity, float)
    assert result.return_pct == pytest.approx(
        (result.final_equity - result.starting_equity) / result.starting_equity * 100
    )


def test_load_prices_from_csv_price_column(tmp_path):
    path = tmp_path / "prices.csv"
    path.write_text("price\n100.0\n101.5\n99.2\n")
    assert load_prices_from_csv(str(path)) == [100.0, 101.5, 99.2]


def test_load_prices_from_csv_falls_back_to_close_column(tmp_path):
    path = tmp_path / "bars.csv"
    path.write_text("date,close\n2024-01-01,100.0\n2024-01-02,102.3\n")
    assert load_prices_from_csv(str(path)) == [100.0, 102.3]
