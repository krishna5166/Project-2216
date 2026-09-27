"""Alpaca ExecutionPort. Broker IO only on reconcile / submit / flatten."""

from __future__ import annotations

import logging

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from .domain import AccountSnapshot, Fill, Position, Side

logger = logging.getLogger(__name__)


def _is_missing_position(exc: APIError) -> bool:
    status = getattr(exc, "status_code", None)
    if status == 404:
        return True
    return "not found" in str(exc).lower()


class ExecutionLayer:
    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self._client = TradingClient(api_key, secret_key, paper=paper)
        self._cash = 0.0
        self._position: Position | None = None
        self._last_price = 0.0

    def mark(self, price: float) -> None:
        self._last_price = price
        if self._position is not None:
            self._position.mark_price = price

    def snapshot(self) -> AccountSnapshot:
        unreal = self._position.unrealized_pl if self._position else 0.0
        return AccountSnapshot(cash=self._cash, equity=self._cash + unreal, position=self._position)

    def position(self, symbol: str) -> Position | None:
        return self._position

    def submit(self, symbol: str, side: Side, qty: float, price: float) -> Fill | None:
        if self._position is not None or qty <= 0:
            return None
        order_side = OrderSide.BUY if side is Side.LONG else OrderSide.SELL
        logger.info("Submitting %s %s qty=%s", order_side.value, symbol, qty)
        self._client.submit_order(
            MarketOrderRequest(symbol=symbol, qty=qty, side=order_side, time_in_force=TimeInForce.DAY)
        )
        snap = self.reconcile(symbol)
        if snap.position is None:
            logger.warning("Order submitted but no position after reconcile — treating as reject")
            return None
        fill_px = snap.position.entry_price
        return Fill(symbol=symbol, side=side, qty=snap.position.qty, price=fill_px)

    def flatten(self, symbol: str, price: float) -> Fill | None:
        if self._position is None:
            return None
        side = self._position.side
        qty = self._position.qty
        entry = self._position.entry_price
        logger.info("Closing position in %s", symbol)
        try:
            self._client.close_position(symbol)
        except APIError as exc:
            if not _is_missing_position(exc):
                raise
        self.reconcile(symbol)
        fill_px = price
        signed = 1.0 if side is Side.LONG else -1.0
        pnl = signed * (fill_px - entry) * qty
        close_side = Side.SHORT if side is Side.LONG else Side.LONG
        return Fill(symbol=symbol, side=close_side, qty=qty, price=fill_px, realized_pl=pnl)

    def reconcile(self, symbol: str) -> AccountSnapshot:
        account = self._client.get_account()
        self._cash = float(account.cash)
        raw = None
        try:
            raw = self._client.get_open_position(symbol)
        except APIError as exc:
            if not _is_missing_position(exc):
                raise
        if raw is None:
            self._position = None
        else:
            qty = abs(float(raw.qty))
            raw_side = str(getattr(raw, "side", "")).lower()
            side = Side.SHORT if raw_side == "short" or float(raw.qty) < 0 else Side.LONG
            entry = float(raw.avg_entry_price)
            mark = float(getattr(raw, "current_price", None) or self._last_price or entry)
            self._position = Position(symbol=symbol, side=side, qty=qty, entry_price=entry, mark_price=mark)
        return self.snapshot()
