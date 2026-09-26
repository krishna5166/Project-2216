from algotrader.bot import TradingBot
from algotrader.config import Config
from algotrader.recorder import load_ticks


def test_bot_records_ticks_when_record_path_set(tmp_path):
    path = tmp_path / "session.jsonl"
    config = Config(
        api_key=None,
        secret_key=None,
        symbol="AAPL",
        base_profit_target=1.0,
        short_window=5,
        long_window=20,
        dry_run=True,
        record_path=str(path),
    )
    bot = TradingBot(config)
    for price in [100.0, 100.5, 101.0]:
        bot._on_price(config.symbol, price)
    bot._recorder.close()

    assert list(load_ticks(str(path))) == [100.0, 100.5, 101.0]


def test_bot_does_not_record_by_default():
    config = Config(
        api_key=None,
        secret_key=None,
        symbol="AAPL",
        base_profit_target=1.0,
        short_window=5,
        long_window=20,
        dry_run=True,
    )
    bot = TradingBot(config)
    assert bot._recorder is None
