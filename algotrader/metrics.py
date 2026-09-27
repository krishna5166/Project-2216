"""Performance metrics for a backtest run: the numbers that actually decide
whether a result means anything, beyond "equity went up".
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PerformanceMetrics:
    num_trades: int
    win_rate: float | None  # None if num_trades == 0
    total_pnl: float
    max_drawdown_pct: float
    sharpe_ratio: float | None  # None if fewer than 2 equity samples


def compute_metrics(equity_curve: list[float], trade_log: list[float]) -> PerformanceMetrics:
    """`equity_curve` is equity sampled at every tick (or at least at every
    trade close); `trade_log` is realized pnl per closed trade, in order.
    """
    num_trades = len(trade_log)
    win_rate = (sum(1 for pnl in trade_log if pnl > 0) / num_trades) if num_trades else None
    total_pnl = sum(trade_log)

    max_drawdown_pct = _max_drawdown_pct(equity_curve)
    sharpe_ratio = _sharpe_ratio(equity_curve)

    return PerformanceMetrics(
        num_trades=num_trades,
        win_rate=win_rate,
        total_pnl=total_pnl,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_ratio=sharpe_ratio,
    )


def _max_drawdown_pct(equity_curve: list[float]) -> float:
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            drawdown = (peak - equity) / peak
            max_dd = max(max_dd, drawdown)
    return max_dd * 100


def _sharpe_ratio(equity_curve: list[float]) -> float | None:
    """Annualization-free Sharpe over per-tick returns (mean / stdev of
    returns). Comparable across runs on the same tick frequency; not
    comparable to a textbook annualized Sharpe.
    """
    if len(equity_curve) < 3:
        return None

    returns = []
    for prev, curr in zip(equity_curve, equity_curve[1:]):
        if prev > 0:
            returns.append((curr - prev) / prev)

    if len(returns) < 2:
        return None

    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    stdev = math.sqrt(variance)

    if stdev == 0:
        return None
    return mean / stdev
