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
```

- `algotrader/domain.py` — one `Signal`, `Side`, `Position`, `Fill`, `AccountSnapshot`
- `algotrader/ports.py` — `MarketDataPort` + `ExecutionPort`
- Live Alpaca and the simulator both implement those ports
- Backtest calls the same `_on_price` as live
- Hot path is CPU + memory. REST happens on startup reconcile, fills, and reconnects
- Vol targeting sizes *down* when realized vol is high
- `STATE_PATH` persists meta weights and the daily risk gate across restarts
- External AI signals stay behind a cache (`get()` is never a network call)

Live fills are confirmed by reconcile. A rejected order cannot look like an open position. 404 “no position” is distinguished from real broker errors.

## Status: MVP

SMA-crossover + conformal analytical engine + Hedge meta-controller + risk gate, runnable against Alpaca paper or fully simulated.

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
.venv/bin/python -m algotrader.train --csv history.csv --out model.json --eval-split 0.2
.venv/bin/python -m pytest
```

## What is still not “done”

Predictive value of the analytical engine on real market data is unproven. External signals are still a stub. Live websocket still uses alpaca-py’s internal `_run_forever` because the public `run()` calls `asyncio.run` and cannot nest.
