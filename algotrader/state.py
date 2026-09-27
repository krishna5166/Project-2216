"""Tiny JSON snapshot so a restart does not wipe meta weights or the daily gate."""

from __future__ import annotations

import json
from pathlib import Path


class StateStore:
    def __init__(self, path: str | None):
        self._path = Path(path) if path else None

    def load(self) -> dict:
        if self._path is None or not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text())
        except (OSError, json.JSONDecodeError):
            return {}

    def save(self, payload: dict) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload))
        tmp.replace(self._path)
