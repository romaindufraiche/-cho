"""Backtest engine (section 9, V2 of the roadmap).

This is a deliberately simple, auditable event-driven simulator: given a
price history and a list of (entry_date, exit_date) trades already decided
by the signal engine, it produces an equity curve and trade list that the
`metrics` module can score. Costs (fees, spread, slippage) are modeled as a
flat basis-point haircut per round trip, applied on entry and exit.

Walk-forward validation (avoiding look-ahead bias) is provided as a split
generator: callers train/tune scoring thresholds on the train window and
evaluate only on the held-out test window, never the reverse.
"""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd

from project_alpha.backtest.metrics import Trade
from project_alpha.data.models import BacktestMetrics
from project_alpha.backtest import metrics as m

DEFAULT_COST_BPS = 10  # fees + spread + slippage, per side, in basis points


def simulate_trades(
    ticker: str, prices: pd.DataFrame, trade_windows: list[tuple[pd.Timestamp, pd.Timestamp]],
    cost_bps: float = DEFAULT_COST_BPS,
) -> list[Trade]:
    """`trade_windows` is a list of (entry_date, exit_date) pairs already
    decided upstream (e.g. by replaying the signal engine day by day)."""
    trades: list[Trade] = []
    cost_factor = cost_bps / 10_000
    for entry_date, exit_date in trade_windows:
        if entry_date not in prices.index or exit_date not in prices.index:
            continue
        entry_price = float(prices.loc[entry_date, "close"]) * (1 + cost_factor)
        exit_price = float(prices.loc[exit_date, "close"]) * (1 - cost_factor)
        trades.append(
            Trade(
                ticker=ticker,
                entry_date=entry_date,
                exit_date=exit_date,
                entry_price=entry_price,
                exit_price=exit_price,
            )
        )
    return trades


def equity_curve_from_trades(
    trades: list[Trade], starting_capital: float = 100_000.0, risk_pct_per_trade: float = 0.01
) -> pd.Series:
    """Builds a simplified sequential equity curve assuming one trade at a
    time, each risking `risk_pct_per_trade` of capital at that point. This
    is intentionally conservative/simple; a full concurrent-positions
    simulator is a natural V2 extension once the portfolio manager feeds
    real overlapping trade windows."""
    if not trades:
        return pd.Series(dtype=float)

    ordered = sorted(trades, key=lambda t: t.entry_date)
    capital = starting_capital
    dates = [ordered[0].entry_date]
    values = [capital]
    for t in ordered:
        capital *= 1 + risk_pct_per_trade * t.return_pct
        dates.append(t.exit_date)
        values.append(capital)
    return pd.Series(values, index=pd.DatetimeIndex(dates)).sort_index()


def compute_backtest_metrics(
    trades: list[Trade],
    equity_curve: pd.Series,
    benchmark_equity_curve: pd.Series | None = None,
    benchmark_name: str | None = None,
) -> BacktestMetrics:
    daily_returns = equity_curve.pct_change().dropna() if not equity_curve.empty else pd.Series(dtype=float)
    strategy_cagr = m.cagr(equity_curve)
    avg_win, avg_loss = m.avg_win_loss(trades)

    return BacktestMetrics(
        start=(equity_curve.index[0].date() if not equity_curve.empty else pd.Timestamp.today().date()),
        end=(equity_curve.index[-1].date() if not equity_curve.empty else pd.Timestamp.today().date()),
        cagr=strategy_cagr,
        alpha_vs_benchmark=(
            m.alpha_vs_benchmark(strategy_cagr, benchmark_equity_curve)
            if benchmark_equity_curve is not None
            else None
        ),
        win_rate=m.win_rate(trades),
        avg_win_pct=avg_win,
        avg_loss_pct=avg_loss,
        expectancy=m.expectancy(trades),
        profit_factor=m.profit_factor(trades),
        max_drawdown=m.max_drawdown(equity_curve),
        volatility=m.volatility(daily_returns),
        sharpe=m.sharpe(daily_returns),
        sortino=m.sortino(daily_returns),
        n_trades=len(trades),
        benchmark=benchmark_name,
    )


def walk_forward_splits(
    dates: pd.DatetimeIndex, train_days: int, test_days: int
) -> Iterator[tuple[pd.DatetimeIndex, pd.DatetimeIndex]]:
    """Yields (train_index, test_index) rolling windows, train always
    strictly before test, so scoring thresholds tuned on `train` are only
    ever evaluated on the unseen `test` window (no look-ahead bias)."""
    dates = dates.sort_values()
    start = 0
    while start + train_days + test_days <= len(dates):
        train_idx = dates[start : start + train_days]
        test_idx = dates[start + train_days : start + train_days + test_days]
        yield train_idx, test_idx
        start += test_days
