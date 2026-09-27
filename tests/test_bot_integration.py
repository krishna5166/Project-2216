from algotrader.bot import TradingBot
from algotrader.config import Config
from algotrader.domain import Side


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
    for price in [10, 10, 10, 10]:
        bot._on_price(symbol, price)
    assert bot.execution.position(symbol) is None
    weights_before = bot.meta.weights
    bot._on_price(symbol, 20)
    position = bot.execution.position(symbol)
    assert position is not None
    assert position.side is Side.LONG
    bot._on_price(symbol, 22)
    assert bot.execution.position(symbol) is None
    assert len(bot.execution.trade_log) == 1
    assert bot.execution.trade_log[0] > 0
    assert bot.meta.weights["decision"] > weights_before["decision"]


def test_full_pipeline_opens_and_closes_a_losing_trade_and_reweights_down():
    bot = _make_bot()
    symbol = bot.config.symbol
    for price in [10, 10, 10, 10, 20]:
        bot._on_price(symbol, price)
    assert bot.execution.position(symbol) is not None
    weights_before = bot.meta.weights
    bot._on_price(symbol, 15)
    assert bot.execution.position(symbol) is None
    assert len(bot.execution.trade_log) == 1
    assert bot.execution.trade_log[0] < 0
    assert bot.meta.weights["decision"] < weights_before["decision"]


def test_kill_switch_blocks_orders_through_the_full_pipeline(monkeypatch):
    monkeypatch.setenv("KILL_SWITCH", "true")
    bot = _make_bot()
    symbol = bot.config.symbol
    for price in [10, 10, 10, 10, 20]:
        bot._on_price(symbol, price)
    assert bot.execution.position(symbol) is None
    assert bot.execution.trade_log == []


def test_daily_loss_limit_trip_blocks_further_trades_same_session():
    bot = _make_bot()
    symbol = bot.config.symbol
    bot.risk_gate.max_daily_loss_fraction = 0.001
    for price in [10, 10, 10, 10, 20]:
        bot._on_price(symbol, price)
    assert bot.execution.position(symbol) is not None
    bot._on_price(symbol, 15)
    assert bot.execution.trade_log[-1] < 0
    for price in [15, 15, 15, 15, 30]:
        bot._on_price(symbol, price)
    assert bot.execution.position(symbol) is None
    assert len(bot.execution.trade_log) == 1
