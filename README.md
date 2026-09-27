# Project-2216 — Algorithmic Trading Bot

![Tests](https://github.com/krishna5166/Project-2216/actions/workflows/tests.yml/badge.svg)

Command-line-only automated trading bot. No visual interface, by design.

## Architecture

Ports and adapters. The tick loop never imports a broker SDK.

```
MarketDataPort.prices()  ──►  TradingBot._on_price
                                 │
                                 ├─ mark()              in-memory
                                 ├─ snapshot()          in-memory
                                 ├─ strategy / analytics / external / risk
                                 ├─ meta.combine
                                 ├─ risk_gate.allow
                                 └─ submit() / flatten()   broker IO only here
                                        │
                                        └─ OrderEventPort.drain_events()  (push-based fills)
```

- `algotrader/domain.py` — one `Signal`, `Side`, `Position`, `Fill`, `AccountSnapshot`
- `algotrader/ports.py` — `MarketDataPort` + `ExecutionPort` + `OrderEventPort`
- Live Alpaca and the simulator both implement those ports
- Backtest calls the same `_on_price` as live
- Hot path is CPU + memory. REST happens on startup reconcile, fills, and reconnects
- Vol targeting sizes *down* when realized vol is high
- `STATE_PATH` persists meta weights and the daily risk gate across restarts
- External AI signals stay behind a cache (`get()` is never a network call)

Live fills are confirmed by reconcile. A rejected order cannot look like an open position. 404 “no position” is distinguished from real broker errors.

## Status: MVP + edge-validation layer

SMA-crossover + conformal analytical engine + Hedge meta-controller + risk gate, runnable against Alpaca paper or fully simulated.

**New in this branch (steps 1–5 of the edge plan):**

1. **Walk-forward backtest** — `python -m algotrader.train --csv history.csv --walk-forward` retrains on a growing prefix and tests on the next chunk. No leakage.
2. **Trade-outcome labels** — the model is now trained on “did this trade hit target before stop?”, matching the bot's actual exit, not “up in 5 ticks”.
3. **Richer features** — 6 features (4 returns + realized vol + range) instead of 3 raw returns.
4. **Order-event port** — `OrderEventPort.drain_events()` lets fills arrive as events instead of blocking the tick loop on REST polls.
5. **Public stream runner** — data feed uses `StockDataStream.run()` in a thread instead of the private `_run_forever()`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
```

## Run

```bash
.venv/bin/python main.py --dry-run
.venv/bin/python main.py          # needs Alpaca keys; paper=True unless PAPER=false
```

Record: `RECORD_PATH=session.jsonl .venv/bin/python main.py --dry-run`
Persist ensemble/gate: `STATE_PATH=state.json`

## Backtest / train / tests

```bash
.venv/bin/python -m algotrader.backtest --csv history.csv
.venv/bin/python -m algotrader.train --csv history.csv --out model.json --walk-forward
.venv/bin/python -m algotrader.train --csv history.csv --out model.json --eval-split 0.2
.venv/bin/python -m pytest
```

## What is still not “done”

Predictive value of the analytical engine on real market data is unproven — run `--walk-forward` on real bars to find out. External signals are still a stub. The order-event port exists but Alpaca's public API still can't nest `run()` in the main loop, so live fills are confirmed via the poll fallback until a true streaming update handler is wired.
