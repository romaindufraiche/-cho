"""Pure pandas/numpy technical indicators. No external TA dependency so the
project stays light and the math stays auditable (deterministic, per
section 8's "les chiffres restent deterministes et tracables")."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    return close.rolling(window).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    # Degenerate cases the rs formula can't express: an unbroken uptrend
    # (avg_loss == 0) is maximal RSI, and a perfectly flat series
    # (avg_gain == avg_loss == 0) is neutral RSI, not NaN.
    result = result.where(avg_loss != 0, 100.0)
    flat = (avg_gain == 0) & (avg_loss == 0)
    result = result.where(~flat, 50.0)
    return result


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series]:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()


def volume_zscore(volume: pd.Series, window: int = 20) -> pd.Series:
    mean = volume.rolling(window).mean()
    std = volume.rolling(window).std().replace(0, np.nan)
    return (volume - mean) / std


def rolling_support_resistance(
    high: pd.Series, low: pd.Series, window: int = 50
) -> tuple[pd.Series, pd.Series]:
    support = low.rolling(window).min()
    resistance = high.rolling(window).max()
    return support, resistance
