import asyncio
import logging

from .config import Config
from .data_feed import DataFeed
from .execution import ExecutionLayer
from .risk import RiskEngine
from .strategy import SmaCrossoverStrategy, Signal

logger = logging.getLogger(__name__)

# Reference equity the base profit target was calibrated against; the actual
# target scales proportionally with current equity from here.
_REFERENCE_EQUITY = 1000.0

# Fraction of equity (adjusted by the risk engine's size multiplier) to commit
# to a single position.
_BASE_POSITION_FRACTION = 0.1


def dynamic_profit_target(base_target: float, equity: float) -> float:
    return base_target * (equity / _REFERENCE_EQUITY)


def position_qty(equity: float, price: float, size_multiplier: float) -> float:
    dollars = equity * _BASE_POSITION_FRACTION * size_multiplier
    qty = dollars / price
    return round(qty, 4)


class TradingBot:
    def __init__(self, config: Config):
        self.config = config
        self.execution = ExecutionLayer(config.api_key, config.secret_key, paper=config.paper)
        self.risk_engine = RiskEngine()
        self.strategy = SmaCrossoverStrategy(config.short_window, config.long_window)
        self.data_feed = DataFeed(config.api_key, config.secret_key, config.symbol)

    async def run(self) -> None:
        symbol = self.config.symbol
        logger.info("Starting bot for %s (paper=%s)", symbol, self.config.paper)

        async for price in self.data_feed.prices():
            risk_level, size_multiplier = self.risk_engine.update(price)
            signal = self.strategy.update(price)

            position = self.execution.get_open_position(symbol)
            if position is not None:
                self._check_hard_exit(position, symbol)
                continue

            if signal is Signal.HOLD:
                continue

            equity = self.execution.get_equity()
            qty = position_qty(equity, price, size_multiplier)
            if qty <= 0:
                continue

            logger.info(
                "Signal=%s risk=%s size_mult=%.2f qty=%s price=%.2f",
                signal.value,
                risk_level.value,
                size_multiplier,
                qty,
                price,
            )
            if signal is Signal.LONG:
                self.execution.open_long(symbol, qty)
            elif signal is Signal.SHORT:
                self.execution.open_short(symbol, qty)

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

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = load_config()
    bot = TradingBot(config)
    asyncio.run(bot.run())
