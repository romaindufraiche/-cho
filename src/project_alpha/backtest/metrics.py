"""Backtest metrics (section 9): CAGR, alpha, win rate, average win/loss,
expectancy, profit factor, max drawdown, volatility, Sharpe/Sortino.

All functions are pure and operate on plain pandas Series / lists of trade
P&Ls, so they can be tested without running a full backtest and reused by
both the historical backtest and the paper-trading track record (V6).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


@dataclass
class Trade:
    ticker: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float

    @property
    def return_pct(self) -> float:
        return (self.exit_price - self.entry_price) / self.entry_price


def cagr(equity_curve: pd.Series) -> float:
    if len(equity_curve) < 2 or equity_curve.iloc[0] <= 0:
        return 0.0
    n_years = (equity_curve.index[-1] - equity_curve.index[0]).days / 365.25
    if n_years <= 0:
        return 0.0
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0]
    return round(total_return ** (1 / n_years) - 1, 4)


def max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1
    return round(float(drawdown.min()), 4)


def volatility(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    return round(float(daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)), 4)


def sharpe(daily_returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    if daily_returns.empty or daily_returns.std() == 0:
        return 0.0
    excess = daily_returns - risk_free_rate / TRADING_DAYS_PER_YEAR
    return round(float(excess.mean() / daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)), 4)


def sortino(daily_returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    if daily_returns.empty:
        return 0.0
    downside = daily_returns[daily_returns < 0]
    downside_std = downside.std()
    if not downside_std or np.isnan(downside_std):
        return 0.0
    excess = daily_returns.mean() - risk_free_rate / TRADING_DAYS_PER_YEAR
    return round(float(excess / downside_std * np.sqrt(TRADING_DAYS_PER_YEAR)), 4)


def win_rate(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t.return_pct > 0)
    return round(wins / len(trades), 4)


def avg_win_loss(trades: list[Trade]) -> tuple[float, float]:
    wins = [t.return_pct for t in trades if t.return_pct > 0]
    losses = [t.return_pct for t in trades if t.return_pct <= 0]
    avg_win = round(sum(wins) / len(wins), 4) if wins else 0.0
    avg_loss = round(sum(losses) / len(losses), 4) if losses else 0.0
    return avg_win, avg_loss


def expectancy(trades: list[Trade]) -> float:
    if not trades:
        return 0.0
    wr = win_rate(trades)
    avg_win, avg_loss = avg_win_loss(trades)
    return round(wr * avg_win + (1 - wr) * avg_loss, 4)


def profit_factor(trades: list[Trade]) -> float:
    gross_profit = sum(t.return_pct for t in trades if t.return_pct > 0)
    gross_loss = abs(sum(t.return_pct for t in trades if t.return_pct < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return round(gross_profit / gross_loss, 4)


def alpha_vs_benchmark(strategy_cagr: float, benchmark_equity_curve: pd.Series) -> float:
    return round(strategy_cagr - cagr(benchmark_equity_curve), 4)
