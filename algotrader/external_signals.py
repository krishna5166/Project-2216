"""Cache boundary for slow / async AI inputs — a Jev regime classifier, an
LLM news-sentiment scorer, or anything else that talks to a network API.

The hot path (bot._on_price) only ever calls get(), which is synchronous,
in-memory, and instant. A cold-path worker (not implemented yet — see below)
would call set() on its own schedule and never touch the per-tick loop.

Not wired to a real provider yet:
  - Jev/TypeSafe: no API access confirmed available; wiring this against an
    unverified API would just be guessing.
  - LLM news sentiment: needs its own API key and a cost budget decision,
    deferred per the project owner's call to configure that later.

Until one of those is wired up, get() returns a neutral signal with zero
confidence, so it's safe for the decision layer to read today — a zero
confidence vote never moves the meta-controller's combined score — and
swapping in a real cold-path refresher later is a pure addition here, not a
change to any call site.
"""

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalSignal:
    value: float  # -1 (bearish) .. +1 (bullish)
    confidence: float  # 0 (no signal) .. 1 (fully confident)
    stale: bool


class ExternalSignalCache:
    def __init__(self, max_age_seconds: float = 300.0):
        self._value = 0.0
        self._confidence = 0.0
        self._last_updated: float | None = None
        self._max_age_seconds = max_age_seconds

    def get(self) -> ExternalSignal:
        stale = self._last_updated is None or (time.time() - self._last_updated) > self._max_age_seconds
        return ExternalSignal(value=self._value, confidence=0.0 if stale else self._confidence, stale=stale)

    def set(self, value: float, confidence: float) -> None:
        """Called by a cold-path worker (e.g. a Jev poll loop or LLM sentiment poll loop)."""
        self._value = max(-1.0, min(1.0, value))
        self._confidence = max(0.0, min(1.0, confidence))
        self._last_updated = time.time()
