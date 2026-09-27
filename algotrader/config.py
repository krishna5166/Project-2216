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
    record_path: str | None = None
    model_path: str | None = None
    state_path: str | None = None
    slip_bps: float = 0.0
    require_engine_agreement: bool = True


def _truthy(name: str, default: str = "") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


def load_config(dry_run_override: bool | None = None) -> Config:
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    env_dry_run = _truthy("DRY_RUN")
    dry_run = env_dry_run if dry_run_override is None else dry_run_override

    if not dry_run and (not api_key or not secret_key):
        raise RuntimeError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set (see .env.example), "
            "or run with --dry-run / DRY_RUN=true to use simulated data and orders."
        )

    agreement_default = "true"
    return Config(
        api_key=api_key,
        secret_key=secret_key,
        symbol=os.environ.get("SYMBOL", "AAPL"),
        base_profit_target=float(os.environ.get("BASE_PROFIT_TARGET", "1.0")),
        short_window=int(os.environ.get("SHORT_WINDOW", "5")),
        long_window=int(os.environ.get("LONG_WINDOW", "20")),
        paper=_truthy("PAPER", "true"),
        dry_run=dry_run,
        record_path=os.environ.get("RECORD_PATH") or None,
        model_path=os.environ.get("MODEL_PATH") or None,
        state_path=os.environ.get("STATE_PATH") or None,
        slip_bps=float(os.environ.get("SLIP_BPS", "0") or 0),
        require_engine_agreement=_truthy("REQUIRE_ENGINE_AGREEMENT", agreement_default),
    )
