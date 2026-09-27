"""Integration tests for TradingBot._on_price: the individual engines (risk,
decision, analytical, meta-controller, risk gate) all have unit tests, but
until now nothing exercised them wired together the way the live bot and
backtester actually run them. These lock in that the full pipeline produces
a trade, closes it, updates the meta-controller's weights, and that the risk
gate can actually veto an order end to end.
"""

import pytest

from algotrader.bot import TradingBot
from algotrader.config import Config


def _make_bot(**overrides) -> TradingBot:
    config = Config(
        api_key=None,
        secret_key=None,
        symbol="TEST",
        base_profit_target=1.0,
        short_window=2,
        long_window=4,
        dry_run=True,
        **overrides,
    )
    return TradingBot(config)


def test_full_pipeline_opens_and_closes_a_winning_trade_and_reweights():
    bot = _make_bot()
    symbol = bot.config.symbol

    # Flat prices build up the SMA window with no crossover yet.
    for price in [10, 10, 10, 10]:
        bot._on_price(symbol, price)
    assert bot.execution.get_open_position(symbol) is None

    weights_before = bot.meta.weights

    # A sharp jump triggers a golden cross -> decision engine votes LONG,
    # which is enough on its own to clear the meta-controller's threshold
    # this early (analytical/external engines are still abstaining).
    bot._on_price(symbol, 20)
    position = bot.execution.get_open_position(symbol)
    assert position is not None
    assert position.side == "long"

    # Price keeps rising until the dynamic profit target is hit.
    bot._on_price(symbol, 20.5)

    assert bot.execution.get_open_position(symbol) is None
    assert len(bot.execution.trade_log) == 1
    assert bot.execution.trade_log[0] > 0

    # The decision engine called it correctly, so its share of the vote
    # should have grown relative to before the trade closed.
    assert bot.meta.weights["decision"] > weights_before["decision"]


def test_full_pipeline_opens_and_closes_a_losing_trade_and_reweights_down():
    bot = _make_bot()
    symbol = bot.config.symbol

    for price in [10, 10, 10, 10, 20]:
        bot._on_price(symbol, price)
    assert bot.execution.get_open_position(symbol) is not None
    weights_before = bot.meta.weights

    # Price now falls hard enough to trip the symmetric stop-loss instead.
    bot._on_price(symbol, 15)

    assert bot.execution.get_open_position(symbol) is None
    assert len(bot.execution.trade_log) == 1
    assert bot.execution.trade_log[0] < 0
    assert bot.meta.weights["decision"] < weights_before["decision"]


def test_kill_switch_blocks_orders_through_the_full_pipeline(monkeypatch):
    monkeypatch.setenv("KILL_SWITCH", "true")
    bot = _make_bot()
    symbol = bot.config.symbol

    # Same golden-cross setup that opens a position in the tests above.
    for price in [10, 10, 10, 10, 20]:
        bot._on_price(symbol, price)

    assert bot.execution.get_open_position(symbol) is None
    assert bot.execution.trade_log == []


def test_daily_loss_limit_trip_blocks_further_trades_same_session():
    bot = _make_bot()
    symbol = bot.config.symbol
    bot.risk_gate.max_daily_loss_fraction = 0.001  # trip on the very first loss

    for price in [10, 10, 10, 10, 20]:
        bot._on_price(symbol, price)
    assert bot.execution.get_open_position(symbol) is not None

    bot._on_price(symbol, 15)  # stop-loss closes at a loss, trips the gate
    assert bot.execution.trade_log[-1] < 0

    # Even a fresh, otherwise-valid golden cross should now be blocked.
    for price in [15, 15, 15, 15, 30]:
        bot._on_price(symbol, price)
    assert bot.execution.get_open_position(symbol) is None
    assert len(bot.execution.trade_log) == 1
