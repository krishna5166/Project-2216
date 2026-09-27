"""Last checkpoint before an order. Can only say no."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone


@dataclass
class RiskGate:
    max_daily_loss_fraction: float = 0.05
    max_position_fraction: float = 0.25

    def __post_init__(self):
        self._start_of_session_equity: float | None = None
        self._daily_realized_pnl = 0.0
        self._tripped = False
        self._trip_reason: str | None = None
        self._session_date: date | None = None

    def snapshot_state(self) -> dict:
        return {
            "start_of_session_equity": self._start_of_session_equity,
            "daily_realized_pnl": self._daily_realized_pnl,
            "tripped": self._tripped,
            "trip_reason": self._trip_reason,
            "session_date": self._session_date.isoformat() if self._session_date else None,
        }

    def load_state(self, state: dict) -> None:
        self._start_of_session_equity = state.get("start_of_session_equity")
        self._daily_realized_pnl = float(state.get("daily_realized_pnl") or 0.0)
        self._tripped = bool(state.get("tripped"))
        self._trip_reason = state.get("trip_reason")
        raw = state.get("session_date")
        self._session_date = date.fromisoformat(raw) if raw else None

    def start_session(self, equity: float) -> None:
        self._start_of_session_equity = equity
        self._daily_realized_pnl = 0.0
        self._tripped = False
        self._trip_reason = None
        self._session_date = self._today()

    def record_trade_result(self, pnl: float) -> None:
        self._daily_realized_pnl += pnl
        if self._start_of_session_equity is None:
            return
        loss_limit = self.max_daily_loss_fraction * self._start_of_session_equity
        if self._daily_realized_pnl <= -loss_limit:
            self._tripped = True
            self._trip_reason = (
                f"Daily loss limit breached: realized_pnl={self._daily_realized_pnl:.2f} "
                f"limit=-{loss_limit:.2f}"
            )

    @staticmethod
    def _today() -> date:
        return datetime.now(timezone.utc).date()

    @staticmethod
    def _manual_kill_switch_active() -> bool:
        return os.environ.get("KILL_SWITCH", "").lower() in ("1", "true", "yes")

    def allow(self, equity: float, qty: float, price: float) -> tuple[bool, str | None]:
        if self._session_date is not None and self._today() != self._session_date:
            self.start_session(equity)
        if self._tripped:
            return False, self._trip_reason
        if self._manual_kill_switch_active():
            return False, "Manual kill switch active (KILL_SWITCH env var)"
        position_value = qty * price
        max_position_value = self.max_position_fraction * equity
        if position_value > max_position_value:
            return False, (
                f"Position value {position_value:.2f} exceeds max allowed "
                f"{max_position_value:.2f} ({self.max_position_fraction:.0%} of equity)"
            )
        return True, None
