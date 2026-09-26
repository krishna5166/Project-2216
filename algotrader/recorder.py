"""Tick recorder: appends every price the bot sees to a JSONL file, so live
(or paper) sessions can later be replayed through the backtester to check
that live behavior matches what the strategy/analytics/meta-controller would
have done on the same data — catching the backtest-to-live gap.

One JSON object per line: {"ts": <unix time>, "price": <float>}.
"""

import json
import time
from pathlib import Path
from typing import Iterator


class TickRecorder:
    def __init__(self, path: str):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self._path, "a")

    def record(self, price: float) -> None:
        line = json.dumps({"ts": time.time(), "price": price})
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def load_ticks(path: str) -> Iterator[float]:
    """Read back a recorded session, yielding prices in order."""
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)["price"]
