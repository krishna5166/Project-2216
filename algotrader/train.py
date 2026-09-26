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
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.csv:
        from .backtest import load_prices_from_csv

        prices = load_prices_from_csv(args.csv, column=args.column)
    else:
        from .recorder import load_ticks

        prices = list(load_ticks(args.jsonl))

    model = train_xgboost_model(prices, label_horizon=args.label_horizon)
    model.save(args.out)
    print(f"Trained on {len(prices)} prices, saved model to {args.out}")


if __name__ == "__main__":
    main()
