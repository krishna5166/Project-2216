"""Orchestrator: one hot path, no broker calls except through ExecutionPort."""

from __future__ import annotations

import argparse
import asyncio
import logging

from .analytics import AnalyticalEngine
from .config import Config
from .domain import Signal, Side
from .external_signals import ExternalSignalCache
from .meta_controller import MetaController
from .risk import RiskEngine
from .risk_gate import RiskGate
from .sizing import dynamic_profit_target, position_qty
from .state import StateStore
from .strategy import SmaCrossoverStrategy

logger = logging.getLogger(__name__)

_RECONNECT_BACKOFF = (1, 2, 5, 10, 30)


class TradingBot:
    def __init__(self, config: Config):
        self.config = config
        self.risk_engine = RiskEngine()
        self.strategy = SmaCrossoverStrategy(config.short_window, config.long_window)

        analytical_model = None
        if config.model_path:
            from .models import XGBoostModel

            analytical_model = XGBoostModel.load(config.model_path)
            logger.info("Loaded trained analytical model from %s", config.model_path)
        self.analytics = AnalyticalEngine(model=analytical_model)
        self.external_signals = ExternalSignalCache()
        self.meta = MetaController(engine_names=["decision", "analytical", "external"])
        self.risk_gate = RiskGate()
        self._last_votes: dict | None = None
        self._last_signal: Signal | None = None
        self._session_started = False
        self._store = StateStore(config.state_path)
        self._restore_state()

        self._recorder = None
        if config.record_path:
            from .recorder import TickRecorder

            self._recorder = TickRecorder(config.record_path)
            logger.info("Recording ticks to %s", config.record_path)

        if config.dry_run:
            from .simulation import SimulatedDataFeed, SimulatedExecutionLayer

            logger.info("Running in DRY-RUN mode: simulated prices and orders, no API calls")
            self.execution = SimulatedExecutionLayer(slip_bps=config.slip_bps)
            self._make_data_feed = lambda: SimulatedDataFeed()
        else:
            from .data_feed import DataFeed
            from .execution import ExecutionLayer

            self.execution = ExecutionLayer(config.api_key, config.secret_key, paper=config.paper)
            self._make_data_feed = lambda: DataFeed(config.api_key, config.secret_key, config.symbol)

        self.data_feed = self._make_data_feed()

    def _restore_state(self) -> None:
        payload = self._store.load()
        if not payload:
            return
        if "weights" in payload:
            self.meta.load_weights(payload["weights"])
        if "risk_gate" in payload:
            self.risk_gate.load_state(payload["risk_gate"])
            self._session_started = self.risk_gate._session_date is not None

    def _persist_state(self) -> None:
        self._store.save({"weights": self.meta.weights, "risk_gate": self.risk_gate.snapshot_state()})

    async def run(self) -> None:
        symbol = self.config.symbol
        logger.info("Starting bot for %s (paper=%s, dry_run=%s)", symbol, self.config.paper, self.config.dry_run)
        try:
            self.execution.reconcile(symbol)
        except Exception:
            logger.exception("Startup reconcile failed; continuing with empty local book")

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
                try:
                    await self.data_feed.aclose()
                except Exception:
                    pass
                self.data_feed = self._make_data_feed()
                try:
                    self.execution.reconcile(symbol)
                except Exception:
                    logger.exception("Reconcile after reconnect failed")

    def _on_price(self, symbol: str, price: float) -> None:
        if self._recorder is not None:
            self._recorder.record(price)

        self.execution.mark(price)
        snap = self.execution.snapshot()

        if not self._session_started:
            self.risk_gate.start_session(snap.equity)
            self._session_started = True
            self._persist_state()

        risk_level, size_multiplier = self.risk_engine.update(price)
        decision_signal = self.strategy.update(price)
        decision_conf = 1.0 if decision_signal is not Signal.HOLD else 0.0
        analytical_signal, analytical_conf = self.analytics.update(price)

        external = self.external_signals.get()
        if external.confidence == 0:
            external_signal = Signal.HOLD
        elif external.value > 0:
            external_signal = Signal.LONG
        else:
            external_signal = Signal.SHORT

        votes = {
            "decision": (decision_signal, decision_conf),
            "analytical": (analytical_signal, analytical_conf),
            "external": (external_signal, external.confidence),
        }

        position = snap.position
        if position is not None:
            self._check_hard_exit(position, symbol, price)
            return

        final_signal = self.meta.combine(votes)
        if final_signal is Signal.HOLD:
            return

        qty = position_qty(snap.equity, price, size_multiplier)
        if qty <= 0:
            return

        allowed, reason = self.risk_gate.allow(snap.equity, qty, price)
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
        side = Side.LONG if final_signal is Signal.LONG else Side.SHORT
        fill = self.execution.submit(symbol, side, qty, price)
        if fill is None:
            logger.warning("Submit returned no fill; not tracking votes for %s", symbol)
            return
        self._last_votes = votes
        self._last_signal = final_signal

    def _check_hard_exit(self, position, symbol: str, price: float) -> None:
        equity = self.execution.snapshot().equity
        target = dynamic_profit_target(self.config.base_profit_target, equity)
        pnl = position.unrealized_pl

        if pnl >= target:
            logger.info("Profit target hit on %s: pnl=%.2f target=%.2f -> closing", symbol, pnl, target)
        elif pnl <= -target:
            logger.info("Stop-loss hit on %s: pnl=%.2f target=-%.2f -> closing", symbol, pnl, target)
        else:
            return

        fill = self.execution.flatten(symbol, price)
        realized = fill.realized_pl if fill is not None else pnl
        self.risk_gate.record_trade_result(realized)
        if self._last_votes is not None and self._last_signal is not None:
            outcome = self._last_signal if realized >= 0 else self._last_signal.opposite()
            self.meta.update_weights(self._last_votes, trade_direction=outcome)
            self._last_votes = None
            self._last_signal = None
        self._persist_state()


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
