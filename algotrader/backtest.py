"""Replay prices through TradingBot._on_price. No sleep, no network.

Also provides walk-forward evaluation: an expanding training window is
retrained on a growing prefix of the series and tested on the next chunk,
so the model is never evaluated on data it trained on.
"""

import argparse
import csv
import logging
from dataclasses import dataclass, field

from .bot import TradingBot
from .config import Config
from .features import extract_features
from .metrics import PerformanceMetrics, compute_metrics
from .models import XGBoostModel
from .train import build_dataset, train_xgboost_model


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


@dataclass
class WalkForwardResult:
    folds: list[BacktestResult] = field(default_factory=list)
    combined_metrics: PerformanceMetrics | None = None

    def __str__(self) -> str:
        lines = [f"Walk-forward: {len(self.folds)} folds"]
        for i, fold in enumerate(self.folds):
            lines.append(f"  fold {i}: {fold}")
        if self.combined_metrics is not None:
            m = self.combined_metrics
            wr = f"{m.win_rate * 100:.0f}%" if m.win_rate is not None else "n/a"
            sh = f"{m.sharpe_ratio:.3f}" if m.sharpe_ratio is not None else "n/a"
            lines.append(
                f"  combined: trades={m.num_trades} win_rate={wr} "
                f"max_drawdown={m.max_drawdown_pct:.2f}% sharpe={sh}"
            )
        return "\n".join(lines)


def run_backtest(prices: list[float], config: Config | None = None) -> BacktestResult:
    if not prices:
        raise ValueError("prices must be non-empty")
    if config is None:
        from .config import load_config

        config = load_config(dry_run_override=True)
    if not config.dry_run:
        raise ValueError("backtesting requires a dry_run config (simulated execution)")
    bot = TradingBot(config)
    starting_equity = bot.execution.snapshot().cash
    equity_curve = [starting_equity]
    for price in prices:
        bot._on_price(config.symbol, price)
        equity_curve.append(bot.execution.snapshot().equity)
    final_equity = bot.execution.snapshot().equity
    return_pct = (final_equity - starting_equity) / starting_equity * 100
    metrics = compute_metrics(equity_curve, bot.execution.trade_log)
    return BacktestResult(
        starting_equity=starting_equity,
        final_equity=final_equity,
        return_pct=return_pct,
        ticks_processed=len(prices),
        metrics=metrics,
    )


def run_walk_forward(
    prices: list[float],
    train_frac: float = 0.5,
    test_frac: float = 0.1,
    label_horizon: int = 30,
    target: float = 0.5,
    stop: float = 0.5,
    config: Config | None = None,
) -> WalkForwardResult:
    """Expanding-window walk-forward.

    1. Train on prices[:train_end].
    2. Backtest on prices[train_end:test_end] with that frozen model.
    3. Advance: train_end = test_end, repeat until the series is exhausted.

    The model for fold N is trained only on data before fold N's test window,
    so there is no leakage.
    """
    if not 0 < train_frac < 1 or not 0 < test_frac < 1:
        raise ValueError("train_frac and test_frac must be in (0, 1)")
    n = len(prices)
    train_end = max(40, int(n * train_frac))
    test_size = max(20, int(n * test_frac))
    folds: list[BacktestResult] = []
    all_pnls: list[float] = []
    cursor = train_end
    fold_idx = 0
    while cursor + test_size <= n:
        train_prices = prices[:cursor]
        test_prices = prices[cursor : cursor + test_size]
        model = train_xgboost_model(
            train_prices, label_horizon=label_horizon, target=target, stop=stop
        )
        model_path = f".wf_model_fold{fold_idx}.json"
        model.save(model_path)
        fold_config = Config(
            api_key=None,
            secret_key=None,
            symbol=config.symbol if config else "WF",
            base_profit_target=target,
            short_window=5,
            long_window=20,
            dry_run=True,
            model_path=model_path,
        )
        result = run_backtest(test_prices, fold_config)
        folds.append(result)
        all_pnls.extend(
            bot_trade_log(test_prices, fold_config)
        )
        cursor += test_size
        fold_idx += 1
    combined = compute_metrics(
        _equity_curve_from_pnls(all_pnls),
        all_pnls,
    )
    return WalkForwardResult(folds=folds, combined_metrics=combined)


def bot_trade_log(prices: list[float], config: Config) -> list[float]:
    bot = TradingBot(config)
    for price in prices:
        bot._on_price(config.symbol, price)
    return list(bot.execution.trade_log)


def _equity_curve_from_pnls(pnls: list[float]) -> list[float]:
    curve = [0.0]
    for p in pnls:
        curve.append(curve[-1] + p)
    return curve


def load_prices_from_csv(path: str, column: str = "price") -> list[float]:
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
    source.add_argument("--csv")
    source.add_argument("--jsonl")
    parser.add_argument("--column", default="price")
    parser.add_argument("--walk-forward", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.csv:
        prices = load_prices_from_csv(args.csv, column=args.column)
    else:
        from .recorder import load_ticks

        prices = list(load_ticks(args.jsonl))
    if args.walk_forward:
        print(run_walk_forward(prices))
    else:
        print(run_backtest(prices))


if __name__ == "__main__":
    main()
