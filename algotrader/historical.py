"""Pulls historical daily/minute bars from Alpaca for backtesting.

Requires real ALPACA_API_KEY / ALPACA_SECRET_KEY — historical market data is
part of Alpaca's standard API, not something dry-run can simulate
meaningfully. Not exercised in this environment (no keys available here);
written so it's ready to run once real credentials are configured.
"""

import argparse
import csv
from datetime import datetime

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


def fetch_historical_closes(
    api_key: str,
    secret_key: str,
    symbol: str,
    start: datetime,
    end: datetime,
    timeframe: TimeFrame = TimeFrame.Minute,
) -> list[float]:
    client = StockHistoricalDataClient(api_key, secret_key)
    request = StockBarsRequest(symbol_or_symbols=symbol, timeframe=timeframe, start=start, end=end)
    bars = client.get_stock_bars(request)
    return [bar.close for bar in bars[symbol]]


def save_closes_to_csv(closes: list[float], path: str) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["price"])
        for price in closes:
            writer.writerow([price])


def main() -> None:
    from .config import load_config

    parser = argparse.ArgumentParser(description="Fetch historical bars from Alpaca into a CSV for backtesting")
    parser.add_argument("--symbol", default=None, help="Defaults to SYMBOL from .env")
    parser.add_argument("--start", required=True, help="ISO date, e.g. 2024-01-01")
    parser.add_argument("--end", required=True, help="ISO date, e.g. 2024-06-01")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    config = load_config(dry_run_override=False)
    symbol = args.symbol or config.symbol

    closes = fetch_historical_closes(
        config.api_key,
        config.secret_key,
        symbol,
        start=datetime.fromisoformat(args.start),
        end=datetime.fromisoformat(args.end),
    )
    save_closes_to_csv(closes, args.out)
    print(f"Wrote {len(closes)} closes for {symbol} to {args.out}")


if __name__ == "__main__":
    main()
