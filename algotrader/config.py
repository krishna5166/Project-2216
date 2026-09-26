import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    api_key: str | None
    secret_key: str | None
    symbol: str
    base_profit_target: float
    short_window: int
    long_window: int
    paper: bool = True
    dry_run: bool = False


def load_config(dry_run_override: bool | None = None) -> Config:
    """Load settings from environment / .env.

    Real Alpaca credentials are only required when not running in dry-run mode,
    so the whole strategy/risk/bot loop can be exercised with zero API keys.
    """
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    env_dry_run = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")
    dry_run = env_dry_run if dry_run_override is None else dry_run_override

    if not dry_run and (not api_key or not secret_key):
        raise RuntimeError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set (see .env.example), "
            "or run with --dry-run / DRY_RUN=true to use simulated data and orders."
        )

    return Config(
        api_key=api_key,
        secret_key=secret_key,
        symbol=os.environ.get("SYMBOL", "AAPL"),
        base_profit_target=float(os.environ.get("BASE_PROFIT_TARGET", "1.0")),
        short_window=int(os.environ.get("SHORT_WINDOW", "5")),
        long_window=int(os.environ.get("LONG_WINDOW", "20")),
        dry_run=dry_run,
    )
