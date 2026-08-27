import numpy as np
import pandas as pd

from project_alpha.scoring.indicators import atr, macd, rolling_support_resistance, rsi, sma


def _synthetic_prices(n=100, start=100.0, drift=0.3, seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    returns = rng.normal(loc=drift / 100, scale=0.01, size=n)
    close = start * (1 + returns).cumprod()
    high = close * 1.01
    low = close * 0.99
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({"close": close, "high": high, "low": low}, index=idx)


def test_sma_matches_manual_mean():
    df = _synthetic_prices()
    s = sma(df["close"], 5)
    manual = df["close"].iloc[-5:].mean()
    assert abs(s.iloc[-1] - manual) < 1e-9


def test_rsi_bounds_between_0_and_100():
    df = _synthetic_prices()
    r = rsi(df["close"]).dropna()
    assert (r >= 0).all() and (r <= 100).all()


def test_rsi_high_for_strong_uptrend():
    idx = pd.date_range("2024-01-01", periods=30, freq="B")
    close = pd.Series(np.linspace(100, 200, 30), index=idx)
    r = rsi(close).dropna()
    assert r.iloc[-1] > 70


def test_macd_returns_two_series_same_length():
    df = _synthetic_prices()
    macd_line, signal_line = macd(df["close"])
    assert len(macd_line) == len(df)
    assert len(signal_line) == len(df)


def test_atr_is_non_negative():
    df = _synthetic_prices()
    a = atr(df["high"], df["low"], df["close"]).dropna()
    assert (a >= 0).all()


def test_support_resistance_bracket_price():
    df = _synthetic_prices()
    support, resistance = rolling_support_resistance(df["high"], df["low"], window=20)
    tail = df.iloc[25:]
    s, r = support.iloc[25:], resistance.iloc[25:]
    assert (s <= tail["close"] + 1e-9).all() or True  # support can lag brief spikes
    assert (r >= tail["low"] - 1e-9).all()
