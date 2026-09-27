"""Offline training for the analytical engine's XGBoost model, from either a
CSV of historical prices or a recorded live/paper session (the same sources
the backtester takes).

The label matches the bot's actual exit: 1 if price hits the profit target
before the stop within `label_horizon` ticks, else 0.

Usage:
    python -m algotrader.train --csv history.csv --out model.json
    python -m algotrader.train --csv history.csv --out model.json --walk-forward
    python -m algotrader.train --jsonl session.jsonl --out model.json
"""

import argparse
import logging

from .features import MIN_HISTORY, extract_features
from .models import XGBoostModel

logger = logging.getLogger(__name__)


def label_trade_outcome(
    entry: float,
    future: list[float],
    target: float,
    stop: float,
) -> int:
    """1 if price reaches +target before -stop within `future`, else 0."""
    for px in future:
        if px - entry >= target:
            return 1
        if entry - px >= stop:
            return 0
    return 0


def build_dataset(
    prices: list[float],
    label_horizon: int = 30,
    target: float = 0.5,
    stop: float = 0.5,
) -> tuple[list[list[float]], list[int]]:
    """Slide a window over `prices`, extract features, label by trade outcome."""
    X: list[list[float]] = []
    y: list[int] = []
    start = MIN_HISTORY - 1
    for i in range(start, len(prices) - label_horizon):
        features = extract_features(prices[: i + 1])
        if features is None:
            continue
        label = label_trade_outcome(
            prices[i], prices[i + 1 : i + 1 + label_horizon], target, stop
        )
        X.append(features)
        y.append(label)
    return X, y


def train_xgboost_model(
    prices: list[float],
    label_horizon: int = 30,
    target: float = 0.5,
    stop: float = 0.5,
) -> XGBoostModel:
    X, y = build_dataset(prices, label_horizon=label_horizon, target=target, stop=stop)
    logger.info("Built %d training examples from %d prices", len(X), len(prices))
    return XGBoostModel.train(X, y)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the analytical engine's XGBoost model offline")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", help="CSV file with a 'price' or 'close' column")
    source.add_argument("--jsonl", help="Recorded tick file from TickRecorder")
    parser.add_argument("--column", default="price", help="Column name to read prices from (--csv only)")
    parser.add_argument(
        "--label-horizon",
        type=int,
        default=30,
        help="Ticks ahead to watch for target/stop (should match the bot's exit window)",
    )
    parser.add_argument("--target", type=float, default=0.5, help="Profit target used for labeling")
    parser.add_argument("--stop", type=float, default=0.5, help="Stop distance used for labeling")
    parser.add_argument("--out", required=True, help="Where to save the trained model")
    parser.add_argument(
        "--eval-split",
        type=float,
        default=None,
        help="Hold out this fraction of prices (e.g. 0.2) for an out-of-sample "
        "backtest after training, instead of only reporting training performance",
    )
    parser.add_argument(
        "--walk-forward",
        action="store_true",
        help="Run an expanding-window walk-forward evaluation: retrain on a "
        "growing prefix, test on the next chunk, never training on test data.",
    )
    parser.add_argument(
        "--wf-train-frac",
        type=float,
        default=0.5,
        help="Fraction of prices used as the initial training window for --walk-forward",
    )
    parser.add_argument(
        "--wf-test-frac",
        type=float,
        default=0.1,
        help="Fraction of prices per test chunk in --walk-forward",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.csv:
        from .backtest import load_prices_from_csv

        prices = load_prices_from_csv(args.csv, column=args.column)
    else:
        from .recorder import load_ticks

        prices = list(load_ticks(args.jsonl))

    if args.walk_forward:
        from .backtest import run_walk_forward

        result = run_walk_forward(
            prices,
            train_frac=args.wf_train_frac,
            test_frac=args.wf_test_frac,
            label_horizon=args.label_horizon,
            target=args.target,
            stop=args.stop,
        )
        print(result)
        return

    if args.eval_split:
        if not 0 < args.eval_split < 1:
            raise ValueError("--eval-split must be between 0 and 1")
        split_idx = int(len(prices) * (1 - args.eval_split))
        train_prices, test_prices = prices[:split_idx], prices[split_idx:]
    else:
        train_prices, test_prices = prices, None

    model = train_xgboost_model(
        train_prices,
        label_horizon=args.label_horizon,
        target=args.target,
        stop=args.stop,
    )
    model.save(args.out)
    print(f"Trained on {len(train_prices)} prices, saved model to {args.out}")

    if test_prices:
        from .backtest import run_backtest
        from .config import Config

        eval_config = Config(
            api_key=None,
            secret_key=None,
            symbol="EVAL",
            base_profit_target=args.target,
            short_window=5,
            long_window=20,
            dry_run=True,
            model_path=args.out,
        )
        result = run_backtest(test_prices, eval_config)
        print(f"\nOut-of-sample evaluation ({len(test_prices)} held-out prices, never seen during training):")
        print(result)


if __name__ == "__main__":
    main()
