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
- **Analytical engine** (`algotrader/analytics.py`): an online logistic-
  regression price-direction predictor calibrated via split conformal
  prediction — abstains unless statistically confident instead of guessing
  every tick.
- **Meta-controller** (`algotrader/meta_controller.py`): combines the SMA
  decision engine's vote and the analytical engine's vote via multiplicative
  weights (Hedge algorithm); whichever engine is actually right over time
  earns more say in the combined decision.
- **Risk gate** (`algotrader/risk_gate.py`): the last checkpoint before an
  order goes out — hard daily-loss limit, a cap on how much of the account
  a single position can use, and a kill switch (`KILL_SWITCH=true` env var,
  or auto-tripped once the daily loss limit is breached). Separate from the
  risk *engine*, which only sizes positions — this can only ever say no.
- **External signal cache** (`algotrader/external_signals.py`): the slot for
  a future Jev regime classifier or LLM news-sentiment score. The decision
  loop only ever reads a cached value — instant, synchronous, never a
  network call — so a slow AI API can be added later without touching the
  per-tick hot path. Currently stubbed: returns a neutral signal with zero
  confidence until a real backend is wired in (no Jev API access confirmed
  yet, and LLM sentiment needs its own key/cost budget decision).
- **Recorder** (`algotrader/recorder.py`): appends every price the bot sees
  to a JSONL file (`RECORD_PATH=path/to/session.jsonl`), so a live or
  paper-trading session can be replayed later.
- **Backtester** (`algotrader/backtest.py`): replays a list of prices
  through the exact same pipeline the live bot uses (all engines, the
  meta-controller, the risk gate) with simulated execution — from a CSV of
  historical bars or a recorded session — with no sleeping, no network
  calls.
- **Historical data fetcher** (`algotrader/historical.py`): pulls real bars
  from Alpaca into a CSV for the backtester. Needs real API keys — not
  exercised in this environment, written so it's ready once configured.

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

Record a session for later replay: `RECORD_PATH=session.jsonl .venv/bin/python main.py --dry-run`

## Backtest

Against real historical data (needs Alpaca keys — see `algotrader/historical.py`):

```bash
.venv/bin/python -m algotrader.historical --start 2024-01-01 --end 2024-06-01 --out history.csv
.venv/bin/python -m algotrader.backtest --csv history.csv
```

Against a recorded live/paper session, to check live behavior matches backtest behavior:

```bash
.venv/bin/python -m algotrader.backtest --jsonl session.jsonl
```

## Tests

```bash
.venv/bin/python -m pytest
```

Covers the pure-logic pieces (strategy signal generation, risk scoring,
position sizing / dynamic profit target math, dry-run config, and the
simulated data feed / execution layer) — none need a live API connection.

## Next steps

- Actually run the backtester against real Alpaca historical data (needs
  keys not available in this environment) — so far only exercised against a
  synthetic random walk and a recorded dry-run session, so real predictive
  value on genuine market data is still unverified.
- Swap the analytical engine's online logistic model for XGBoost trained
  offline on recorded/historical data, keeping the conformal-calibration
  wrapper (it's model-agnostic).
- Wire a real backend into `external_signals.py` — a Jev regime classifier
  and/or an LLM news-sentiment scorer, running as a cold-path background
  worker that calls `.set()` on its own schedule. Needs API keys/access
  decisions the project owner hasn't made yet.
- Exercise the real Alpaca websocket/trading API against a real paper
  account (not yet done in this environment — no keys available here).
