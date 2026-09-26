import argparse
import asyncio
import logging

from .config import Config
from .risk import RiskEngine
from .strategy import SmaCrossoverStrategy, Signal

logger = logging.getLogger(__name__)

# Reference equity the base profit target was calibrated against; the actual
# target scales proportionally with current equity from here.
_REFERENCE_EQUITY = 1000.0

# Fraction of equity (adjusted by the risk engine's size multiplier) to commit
# to a single position.
_BASE_POSITION_FRACTION = 0.1

# Backoff schedule (seconds) for reconnecting the live data feed after a drop.
_RECONNECT_BACKOFF = [1, 2, 5, 10, 30]


def dynamic_profit_target(base_target: float, equity: float) -> float:
    return base_target * (equity / _REFERENCE_EQUITY)


def position_qty(equity: float, price: float, size_multiplier: float) -> float:
    dollars = equity * _BASE_POSITION_FRACTION * size_multiplier
    qty = dollars / price
    return round(qty, 4)


class TradingBot:
    def __init__(self, config: Config):
        self.config = config
        self.risk_engine = RiskEngine()
        self.strategy = SmaCrossoverStrategy(config.short_window, config.long_window)

        if config.dry_run:
            from .simulation import SimulatedDataFeed, SimulatedExecutionLayer

            logger.info("Running in DRY-RUN mode: simulated prices and orders, no API calls")
            self.execution = SimulatedExecutionLayer()
            self._make_data_feed = lambda: SimulatedDataFeed()
        else:
            from .data_feed import DataFeed
            from .execution import ExecutionLayer

            self.execution = ExecutionLayer(config.api_key, config.secret_key, paper=config.paper)
            self._make_data_feed = lambda: DataFeed(config.api_key, config.secret_key, config.symbol)

        self.data_feed = self._make_data_feed()

    async def run(self) -> None:
        symbol = self.config.symbol
        logger.info("Starting bot for %s (paper=%s, dry_run=%s)", symbol, self.config.paper, self.config.dry_run)

        attempt = 0
        while True:
            try:
                async for price in self.data_feed.prices():
                    attempt = 0
                    self._on_price(symbol, price)
            except asyncio.CancelledError:
                raise
            except Exception:
                delay = _RECONNECT_BACKOFF[min(attempt, len(_RECONNECT_BACKOFF) - 1)]
                logger.exception("Data feed error; reconnecting in %ss", delay)
                attempt += 1
                await asyncio.sleep(delay)
                self.data_feed = self._make_data_feed()

    def _on_price(self, symbol: str, price: float) -> None:
        self.execution.mark_price(price)
        risk_level, size_multiplier = self.risk_engine.update(price)
        signal = self.strategy.update(price)

        position = self.execution.get_open_position(symbol)
        if position is not None:
            self._check_hard_exit(position, symbol)
            return

        if signal is Signal.HOLD:
            return

        equity = self.execution.get_equity()
        qty = position_qty(equity, price, size_multiplier)
        if qty <= 0:
            return

        logger.info(
            "Signal=%s risk=%s size_mult=%.2f qty=%s price=%.2f",
            signal.value,
            risk_level.value,
            size_multiplier,
            qty,
            price,
        )
        if signal is Signal.LONG:
            self.execution.open_long(symbol, qty, price)
        elif signal is Signal.SHORT:
            self.execution.open_short(symbol, qty, price)

    def _check_hard_exit(self, position, symbol: str) -> None:
        """Hard exit rule: once the dynamic profit target is hit, close immediately."""
        equity = self.execution.get_equity()
        target = dynamic_profit_target(self.config.base_profit_target, equity)
        pnl = self.execution.unrealized_pl(position)

        if pnl >= target:
            logger.info(
                "Profit target hit on %s: pnl=%.2f target=%.2f -> closing",
                symbol,
                pnl,
                target,
            )
            self.execution.close_position(symbol)


def main() -> None:
    from .config import load_config

    parser = argparse.ArgumentParser(description="Algorithmic trading bot")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Run with simulated prices and orders; no API keys or network calls needed",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config(dry_run_override=args.dry_run)
    bot = TradingBot(config)
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Shutting down")
