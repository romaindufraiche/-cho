import pandas as pd
import pytest

from project_alpha.backtest.metrics import (
    Trade,
    avg_win_loss,
    cagr,
    expectancy,
    max_drawdown,
    profit_factor,
    signal_precision,
    target_hit_rate,
    win_rate,
)


def _trade(entry, exit_, days=30, exit_reason="") -> Trade:
    entry_date = pd.Timestamp("2024-01-01")
    return Trade(
        ticker="TEST",
        entry_date=entry_date,
        exit_date=entry_date + pd.Timedelta(days=days),
        entry_price=entry,
        exit_price=exit_,
        exit_reason=exit_reason,
    )


def test_win_rate_counts_positive_trades():
    trades = [_trade(100, 110), _trade(100, 90), _trade(100, 120)]
    assert win_rate(trades) == pytest.approx(2 / 3, abs=1e-4)


def test_avg_win_loss():
    trades = [_trade(100, 110), _trade(100, 90)]
    avg_win, avg_loss = avg_win_loss(trades)
    assert avg_win == pytest.approx(0.10)
    assert avg_loss == pytest.approx(-0.10)


def test_expectancy_combines_win_rate_and_avg_win_loss():
    trades = [_trade(100, 110), _trade(100, 90)]
    e = expectancy(trades)
    assert e == pytest.approx(0.5 * 0.10 + 0.5 * -0.10)


def test_profit_factor_infinite_with_no_losses():
    trades = [_trade(100, 110), _trade(100, 120)]
    assert profit_factor(trades) == float("inf")


def test_cagr_on_doubling_equity_over_one_year():
    idx = pd.DatetimeIndex(["2023-01-01", "2024-01-01"])
    curve = pd.Series([100_000, 200_000], index=idx)
    assert cagr(curve) == pytest.approx(1.0, abs=0.02)


def test_max_drawdown_detects_peak_to_trough():
    idx = pd.date_range("2024-01-01", periods=5)
    curve = pd.Series([100, 120, 90, 95, 130], index=idx)
    dd = max_drawdown(curve)
    assert dd == pytest.approx((90 - 120) / 120, abs=1e-9)


def test_signal_precision_matches_win_rate():
    trades = [_trade(100, 110), _trade(100, 90), _trade(100, 120)]
    assert signal_precision(trades) == win_rate(trades)


def test_target_hit_rate_counts_only_target_reached_exits():
    trades = [
        _trade(100, 110, exit_reason="target_reached"),
        _trade(100, 95, exit_reason="stop_hit"),
        _trade(100, 101, exit_reason="time_stop"),
        _trade(100, 130, exit_reason="target_reached"),
    ]
    assert target_hit_rate(trades) == pytest.approx(0.5)


def test_target_hit_rate_empty_trades():
    assert target_hit_rate([]) == 0.0
