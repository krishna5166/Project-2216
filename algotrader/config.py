import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    api_key: str
    secret_key: str
    symbol: str
    base_profit_target: float
    short_window: int
    long_window: int
    paper: bool = True


def load_config() -> Config:
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        raise RuntimeError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set (see .env.example)"
        )

    return Config(
        api_key=api_key,
        secret_key=secret_key,
        symbol=os.environ.get("SYMBOL", "AAPL"),
        base_profit_target=float(os.environ.get("BASE_PROFIT_TARGET", "1.0")),
        short_window=int(os.environ.get("SHORT_WINDOW", "5")),
        long_window=int(os.environ.get("LONG_WINDOW", "20")),
    )
