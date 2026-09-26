import argparse
import asyncio
import logging

from .analytics import AnalyticalEngine, Vote
from .config import Config
from .external_signals import ExternalSignalCache
from .meta_controller import MetaController, Signal
from .risk import RiskEngine
from .risk_gate import RiskGate
from .strategy import SmaCrossoverStrategy
from .strategy import Signal as StrategySignal

logger = logging.getLogger(__name__)

# Reference equity the base profit target was calibrated against; the actual
# target scales proportionally with current equity from here.
_REFERENCE_EQUITY = 1000.0

# Fraction of equity (adjusted by the risk engine's size multiplier) to commit
# to a single position.
_BASE_POSITION_FRACTION = 0.1

# Backoff schedule (seconds) for reconnecting the live data feed after a drop.
_RECONNECT_BACKOFF = [1, 2, 5, 10, 30]

_STRATEGY_TO_SIGNAL = {
    StrategySignal.LONG: Signal.LONG,
    StrategySignal.SHORT: Signal.SHORT,
    StrategySignal.HOLD: Signal.HOLD,
}
_VOTE_TO_SIGNAL = {
    Vote.UP: Signal.LONG,
    Vote.DOWN: Signal.SHORT,
    Vote.ABSTAIN: Signal.HOLD,
}


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
        self.analytics = AnalyticalEngine()
        self.external_signals = ExternalSignalCache()
        self.meta = MetaController(engine_names=["decision", "analytical", "external"])
        self.risk_gate = RiskGate()
        self._last_votes: dict | None = None
        self._last_signal: Signal | None = None
        self._session_started = False

        self._recorder = None
        if config.record_path:
            from .recorder import TickRecorder

            self._recorder = TickRecorder(config.record_path)
            logger.info("Recording ticks to %s", config.record_path)

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
        if self._recorder is not None:
            self._recorder.record(price)

        self.execution.mark_price(price)
        if not self._session_started:
            self.risk_gate.start_session(self.execution.get_equity())
            self._session_started = True

        risk_level, size_multiplier = self.risk_engine.update(price)

        decision_signal = _STRATEGY_TO_SIGNAL[self.strategy.update(price)]
        decision_conf = 1.0 if decision_signal is not Signal.HOLD else 0.0

        analytical_vote, analytical_conf = self.analytics.update(price)
        analytical_signal = _VOTE_TO_SIGNAL[analytical_vote]

        # Not wired to a real Jev/LLM backend yet (see external_signals.py) —
        # confidence is 0 until one is, so this never moves the combined vote.
        external = self.external_signals.get()
        external_signal = Signal.HOLD if external.confidence == 0 else (Signal.LONG if external.value > 0 else Signal.SHORT)

        votes = {
            "decision": (decision_signal, decision_conf),
            "analytical": (analytical_signal, analytical_conf),
            "external": (external_signal, external.confidence),
        }
        final_signal = self.meta.combine(votes)

        position = self.execution.get_open_position(symbol)
        if position is not None:
            self._check_hard_exit(position, symbol)
            return

        if final_signal is Signal.HOLD:
            return

        equity = self.execution.get_equity()
        qty = position_qty(equity, price, size_multiplier)
        if qty <= 0:
            return

        allowed, reason = self.risk_gate.allow(equity, qty, price)
        if not allowed:
            logger.warning("Risk gate blocked %s order for %s: %s", final_signal.value, symbol, reason)
            return

        logger.info(
            "Final=%s (decision=%s analytical=%s weights=%s) risk=%s size_mult=%.2f qty=%s price=%.2f",
            final_signal.value,
            decision_signal.value,
            analytical_signal.value,
            {k: round(v, 2) for k, v in self.meta.weights.items()},
            risk_level.value,
            size_multiplier,
            qty,
            price,
        )
        self._last_votes = votes
        self._last_signal = final_signal
        if final_signal is Signal.LONG:
            self.execution.open_long(symbol, qty, price)
        elif final_signal is Signal.SHORT:
            self.execution.open_short(symbol, qty, price)

    def _check_hard_exit(self, position, symbol: str) -> None:
        """Hard exit rule: once the dynamic profit target is hit, close immediately.

        Also enforces a symmetric stop-loss. Without it, positions would only
        ever close on a win, so the meta-controller would never see a losing
        outcome to learn from — the adaptive weighting needs both signs of
        feedback to mean anything.
        """
        equity = self.execution.get_equity()
        target = dynamic_profit_target(self.config.base_profit_target, equity)
        pnl = self.execution.unrealized_pl(position)

        if pnl >= target:
            logger.info("Profit target hit on %s: pnl=%.2f target=%.2f -> closing", symbol, pnl, target)
        elif pnl <= -target:
            logger.info("Stop-loss hit on %s: pnl=%.2f target=-%.2f -> closing", symbol, pnl, target)
        else:
            return

        self.execution.close_position(symbol)
        self.risk_gate.record_trade_result(pnl)
        if self._last_votes is not None and self._last_signal is not None:
            # The trade was profitable iff we stayed in the direction we opened;
            # a loss means that direction was the wrong call.
            outcome = self._last_signal if pnl >= target else self._opposite(self._last_signal)
            self.meta.update_weights(self._last_votes, trade_direction=outcome)
            self._last_votes = None
            self._last_signal = None

    @staticmethod
    def _opposite(signal: Signal) -> Signal:
        return Signal.SHORT if signal is Signal.LONG else Signal.LONG


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
