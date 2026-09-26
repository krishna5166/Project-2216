# Project-2216 — Algorithmic Trading Bot

Command-line-only automated trading bot. No visual interface, by design, to
minimize latency and complexity.

## Status: MVP

SMA-crossover strategy connected end to end, runnable either against Alpaca
**paper trading** or fully simulated with zero API keys:

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
- **Bot loop** (`algotrader/bot.py`): ties it together, enforces the hard exit
  rule — once the dynamic profit target (scaled with account equity) is hit,
  the position is closed immediately — and reconnects the live data feed with
  backoff if it drops.
- **Simulation mode** (`algotrader/simulation.py`): an in-memory random-walk
  price feed and paper-paper execution layer with the same interface as the
  real ones, so the whole loop can be demoed and tested without any
  credentials or network access.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
# edit .env with your Alpaca paper trading API key/secret (only needed for --dry-run=false)
```

Get free paper trading keys at https://app.alpaca.markets/paper/dashboard/overview.
`.env` is gitignored — keys never get committed. `.env.example` is the config
template; nothing in this repo depends on real keys being present.

## Run

Fully simulated, no API keys required:

```bash
.venv/bin/python main.py --dry-run
```

Against Alpaca paper trading (needs `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` in `.env`):

```bash
.venv/bin/python main.py
```

`DRY_RUN=true` in `.env` works the same as passing `--dry-run`. Live trading
isn't wired up — `paper=True` is hardcoded in `Config` until the strategy is
proven out on paper first.

## Tests

```bash
.venv/bin/python -m pytest
```

Covers the pure-logic pieces (strategy signal generation, risk scoring,
position sizing / dynamic profit target math, dry-run config, and the
simulated data feed / execution layer) — none need a live API connection.

## Next steps

- Backtest the SMA crossover against historical data before trusting live
  paper-trading results.
- Replace rule-based risk thresholds with a model trained on historical
  volatility once enough paper-trading data exists.
- Add sentiment/news scoring and a fast decision-layer model as separate,
  optional inputs to the strategy layer — keep the core loop working without
  them first.
- Exercise the real Alpaca websocket/trading API against a real paper
  account (not yet done in this environment — no keys available here).
