"""Backtester: replays a sequence of prices through the exact same decision
pipeline the live bot uses (risk engine, decision engine, analytical engine,
meta-controller, risk gate) with the in-memory simulated execution layer, no
sleeping, no network calls.

Reuses TradingBot directly rather than duplicating its logic: `run()` is
never called (that's the async live loop), instead `_on_price` is called
synchronously for each historical price. Since dry_run always builds a
SimulatedExecutionLayer, this works whether the source prices are a CSV of
real historical bars or a recorded live/paper session.
"""

import argparse
import csv
import logging
from dataclasses import dataclass

from .bot import TradingBot
from .config import Config
from .metrics import PerformanceMetrics, compute_metrics


@dataclass
class BacktestResult:
    starting_equity: float
    final_equity: float
    return_pct: float
    ticks_processed: int
    metrics: PerformanceMetrics

    def __str__(self) -> str:
        m = self.metrics
        win_rate_str = f"{m.win_rate * 100:.0f}%" if m.win_rate is not None else "n/a"
        sharpe_str = f"{m.sharpe_ratio:.3f}" if m.sharpe_ratio is not None else "n/a"
        return (
            f"Backtest: {self.ticks_processed} ticks, "
            f"equity {self.starting_equity:.2f} -> {self.final_equity:.2f} "
            f"({self.return_pct:+.2f}%)\n"
            f"  trades={m.num_trades} win_rate={win_rate_str} "
            f"max_drawdown={m.max_drawdown_pct:.2f}% sharpe={sharpe_str}"
        )


def run_backtest(prices: list[float], config: Config | None = None) -> BacktestResult:
    if not prices:
        raise ValueError("prices must be non-empty")

    if config is None:
        from .config import load_config

        # dry_run_override=True: never require live API keys for a backtest.
        # Still picks up MODEL_PATH, SHORT_WINDOW, etc. from the environment.
        config = load_config(dry_run_override=True)
    if not config.dry_run:
        raise ValueError("backtesting requires a dry_run config (simulated execution)")

    bot = TradingBot(config)
    starting_equity = bot.execution.get_equity()
    equity_curve = [starting_equity]

    for price in prices:
        bot._on_price(config.symbol, price)
        equity_curve.append(bot.execution.get_equity())

    final_equity = bot.execution.get_equity()
    return_pct = (final_equity - starting_equity) / starting_equity * 100
    metrics = compute_metrics(equity_curve, bot.execution.trade_log)

    return BacktestResult(
        starting_equity=starting_equity,
        final_equity=final_equity,
        return_pct=return_pct,
        ticks_processed=len(prices),
        metrics=metrics,
    )


def load_prices_from_csv(path: str, column: str = "price") -> list[float]:
    """Reads a CSV with a `price` (or `close`) column of historical prices."""
    prices = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        col = column if column in (reader.fieldnames or []) else "close"
        for row in reader:
            prices.append(float(row[col]))
    return prices


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the trading bot against historical prices")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", help="CSV file with a 'price' or 'close' column (historical data)")
    source.add_argument("--jsonl", help="Recorded tick file from TickRecorder (a live/paper session)")
    parser.add_argument("--column", default="price", help="Column name to read prices from (--csv only)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.csv:
        prices = load_prices_from_csv(args.csv, column=args.column)
    else:
        from .recorder import load_ticks

        prices = list(load_ticks(args.jsonl))

    result = run_backtest(prices)
    print(result)


if __name__ == "__main__":
    main()
