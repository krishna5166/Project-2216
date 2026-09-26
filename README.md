# Project-2216 — Algorithmic Trading Bot

Command-line-only automated trading bot. No visual interface, by design, to
minimize latency and complexity.

## Status: v1 prototype

SMA-crossover strategy on Alpaca **paper trading**, connected end to end:

- **Data layer** (`algotrader/data_feed.py`): live trade prices via Alpaca's
  websocket stream (push-based, no polling).
- **Risk engine** (`algotrader/risk.py`): rule-based volatility scoring
  (conservative / moderate / aggressive) that scales position size. Placeholder
  thresholds — tune with real paper-trading data. AI-driven version is a later
  step.
- **Strategy layer** (`algotrader/strategy.py`): short/long SMA crossover
  (golden cross → long, death cross → short).
- **Execution layer** (`algotrader/execution.py`): submits market orders and
  force-closes positions via Alpaca's trading API.
- **Bot loop** (`algotrader/bot.py`): ties it together and enforces the hard
  exit rule — once the dynamic profit target (scaled with account equity) is
  hit, the position is closed immediately, no exceptions.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
# edit .env with your Alpaca paper trading API key/secret
```

Get free paper trading keys at https://app.alpaca.markets/paper/dashboard/overview.

## Run

```bash
.venv/bin/python main.py
```

Runs against Alpaca **paper trading** only (`paper=True` is hardcoded in
`Config` until this is proven out — do not point this at a live account yet).

## Tests

```bash
.venv/bin/python -m pytest
```

Covers the pure-logic pieces (strategy signal generation, risk scoring,
position sizing / dynamic profit target math) that don't need a live API
connection.

## Next steps

- Backtest the SMA crossover against historical data before trusting live
  paper-trading results.
- Replace rule-based risk thresholds with a model trained on historical
  volatility once enough paper-trading data exists.
- Add sentiment/news scoring and a fast decision-layer model as separate,
  optional inputs to the strategy layer — keep the core loop working without
  them first.
- Add graceful handling for API rate limits / websocket disconnects.
