import logging

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

logger = logging.getLogger(__name__)


class ExecutionLayer:
    """Thin wrapper around Alpaca's trading API for the order lifecycle we need."""

    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self._client = TradingClient(api_key, secret_key, paper=paper)

    def get_equity(self) -> float:
        return float(self._client.get_account().equity)

    def get_open_position(self, symbol: str):
        try:
            return self._client.get_open_position(symbol)
        except Exception:
            return None

    def unrealized_pl(self, position) -> float:
        return float(position.unrealized_pl)

    def mark_price(self, price: float) -> None:
        """No-op for live trading; Alpaca tracks unrealized P/L itself.

        Kept so bot.py can treat live and simulated execution identically.
        """

    def open_long(self, symbol: str, qty: float, price: float) -> None:
        self._submit(symbol, qty, OrderSide.BUY)

    def open_short(self, symbol: str, qty: float, price: float) -> None:
        self._submit(symbol, qty, OrderSide.SELL)

    def close_position(self, symbol: str) -> None:
        logger.info("Closing position in %s", symbol)
        self._client.close_position(symbol)

    def _submit(self, symbol: str, qty: float, side: OrderSide) -> None:
        logger.info("Submitting %s order: %s qty=%s", side.value, symbol, qty)
        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        self._client.submit_order(order)
