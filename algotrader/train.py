"""Offline training for the analytical engine's XGBoost model, from either a
CSV of historical prices or a recorded live/paper session (the same sources
the backtester takes).

Usage:
    python -m algotrader.train --csv history.csv --out model.json
    python -m algotrader.train --jsonl session.jsonl --out model.json
"""

import argparse
import logging

from .features import extract_features
from .models import XGBoostModel

logger = logging.getLogger(__name__)


def build_dataset(prices: list[float], label_horizon: int = 5) -> tuple[list[list[float]], list[int]]:
    """Slides a window over `prices`, extracting features at each point and
    labeling whether price was higher `label_horizon` ticks later.
    """
    X: list[list[float]] = []
    y: list[int] = []
    for i in range(9, len(prices) - label_horizon):
        features = extract_features(prices[: i + 1])
        if features is None:
            continue
        future_up = prices[i + label_horizon] > prices[i]
        X.append(features)
        y.append(int(future_up))
    return X, y


def train_xgboost_model(prices: list[float], label_horizon: int = 5) -> XGBoostModel:
    X, y = build_dataset(prices, label_horizon=label_horizon)
    logger.info("Built %d training examples from %d prices", len(X), len(prices))
    return XGBoostModel.train(X, y)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the analytical engine's XGBoost model offline")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--csv", help="CSV file with a 'price' or 'close' column")
    source.add_argument("--jsonl", help="Recorded tick file from TickRecorder")
    parser.add_argument("--column", default="price", help="Column name to read prices from (--csv only)")
    parser.add_argument("--label-horizon", type=int, default=5, help="Ticks ahead to label up/down")
    parser.add_argument("--out", required=True, help="Where to save the trained model")
    parser.add_argument(
        "--eval-split",
        type=float,
        default=None,
        help="Hold out this fraction of prices (e.g. 0.2) for an out-of-sample "
        "backtest after training, instead of only reporting training performance",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.csv:
        from .backtest import load_prices_from_csv

        prices = load_prices_from_csv(args.csv, column=args.column)
    else:
        from .recorder import load_ticks

        prices = list(load_ticks(args.jsonl))

    if args.eval_split:
        if not 0 < args.eval_split < 1:
            raise ValueError("--eval-split must be between 0 and 1")
        split_idx = int(len(prices) * (1 - args.eval_split))
        train_prices, test_prices = prices[:split_idx], prices[split_idx:]
    else:
        train_prices, test_prices = prices, None

    model = train_xgboost_model(train_prices, label_horizon=args.label_horizon)
    model.save(args.out)
    print(f"Trained on {len(train_prices)} prices, saved model to {args.out}")

    if test_prices:
        from .backtest import run_backtest
        from .config import Config

        eval_config = Config(
            api_key=None,
            secret_key=None,
            symbol="EVAL",
            base_profit_target=1.0,
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
