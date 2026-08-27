import numpy as np
import pandas as pd

from project_alpha.backtest.historical import (
    WARMUP_ROWS,
    run_universe_backtest,
    simulate_ticker,
)


def _trending_prices(n=500, start=100.0, drift=0.0006, vol=0.012, seed=1) -> pd.DataFrame:
    """A price series with enough sustained uptrend + pullbacks to trigger
    both entries and exits (stop/target/time-stop) in the simulator."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(loc=drift, scale=vol, size=n)
    close = start * (1 + pd.Series(returns)).cumprod()
    high = close * 1.008
    low = close * 0.992
    volume = pd.Series(rng.integers(1_000_000, 5_000_000, size=n), dtype=float)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"open": close, "high": high.values, "low": low.values, "close": close.values, "volume": volume.values},
        index=idx,
    )


def _flat_prices(n=500, start=100.0, seed=2) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    noise = rng.normal(loc=0.0, scale=0.003, size=n)
    close = start * (1 + pd.Series(noise)).cumprod()
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": close,
            "high": close.values * 1.003,
            "low": close.values * 0.997,
            "close": close.values,
            "volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )


def test_simulate_ticker_returns_no_trades_below_warmup():
    short_prices = _trending_prices(n=WARMUP_ROWS - 10)
    assert simulate_ticker("TEST", short_prices) == []


def test_simulate_ticker_produces_trades_on_sustained_uptrend():
    prices = _trending_prices(n=600, drift=0.0015, vol=0.01)
    trades = simulate_ticker("TEST", prices)
    assert len(trades) > 0
    for trade in trades:
        assert trade.entry_date < trade.exit_date
        assert trade.exit_reason in {"stop_hit", "target_reached", "time_stop"}


def test_simulate_ticker_entries_are_causal_no_lookahead():
    """Truncating the series after the last recorded trade's exit must not
    change any earlier trade - i.e. no decision used data past its own date."""
    prices = _trending_prices(n=600, drift=0.0015, vol=0.01)
    trades = simulate_ticker("TEST", prices)
    assert trades, "expected at least one trade to validate causality against"

    cutoff = trades[0].exit_date
    truncated = prices.loc[:cutoff]
    trades_truncated = simulate_ticker("TEST", truncated)

    assert trades_truncated
    assert trades_truncated[0].entry_date == trades[0].entry_date
    assert trades_truncated[0].exit_date == trades[0].exit_date


def test_run_universe_backtest_aggregates_across_tickers():
    price_data = {
        "UP": _trending_prices(n=600, drift=0.0015, vol=0.01, seed=1),
        "FLAT": _flat_prices(n=600, seed=2),
    }
    result = run_universe_backtest(price_data)
    assert set(result.trades_per_ticker) == {"UP", "FLAT"}
    assert result.metrics.n_trades == len(result.trades)
    assert result.metrics.n_trades == sum(result.trades_per_ticker.values())


def test_run_universe_backtest_computes_alpha_when_benchmark_given():
    price_data = {"UP": _trending_prices(n=600, drift=0.0015, vol=0.01, seed=1)}
    benchmark = _flat_prices(n=600, seed=99)["close"]
    result = run_universe_backtest(price_data, benchmark_equity_curve=benchmark, benchmark_name="TEST_BENCH")
    assert result.metrics.benchmark == "TEST_BENCH"
    assert result.metrics.alpha_vs_benchmark is not None
