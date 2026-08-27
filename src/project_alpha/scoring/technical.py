"""Technical / Momentum module (weight 15): tendance, RSI, MACD, volume,
supports/resistances."""

from __future__ import annotations

from datetime import date

import pandas as pd

from project_alpha.data.models import TechnicalFeatures
from project_alpha.scoring.indicators import (
    atr,
    macd,
    rolling_support_resistance,
    rsi,
    sma,
    volume_zscore,
)

NEUTRAL_SCORE = 50.0


def compute_technical_features(ticker: str, prices: pd.DataFrame) -> TechnicalFeatures | None:
    """`prices` must be a DataFrame indexed by date with open/high/low/close/volume
    columns (as produced by `yfinance_source.prices_to_dataframe`)."""
    if prices.empty or len(prices) < 20:
        return None

    close, high, low, volume = prices["close"], prices["high"], prices["low"], prices["volume"]
    macd_line, signal_line = macd(close)
    support, resistance = rolling_support_resistance(high, low)

    last = prices.index[-1]
    as_of = last.date() if hasattr(last, "date") else date.today()

    def _f(series: pd.Series) -> float | None:
        val = series.iloc[-1]
        return None if pd.isna(val) else float(val)

    trend = _trend_score(close, _f(sma(close, 20)), _f(sma(close, 50)), _f(sma(close, 200)))

    return TechnicalFeatures(
        ticker=ticker,
        as_of=as_of,
        close=float(close.iloc[-1]),
        sma_20=_f(sma(close, 20)),
        sma_50=_f(sma(close, 50)),
        sma_200=_f(sma(close, 200)),
        rsi_14=_f(rsi(close, 14)),
        macd=_f(macd_line),
        macd_signal=_f(signal_line),
        atr_14=_f(atr(high, low, close, 14)),
        volume_zscore=_f(volume_zscore(volume, 20)),
        support=_f(support),
        resistance=_f(resistance),
        trend_score=trend,
    )


def _trend_score(
    close: pd.Series, sma20: float | None, sma50: float | None, sma200: float | None
) -> float | None:
    if sma20 is None or sma50 is None:
        return None
    price = float(close.iloc[-1])
    score = 0
    total = 0
    for fast, slow in ((price, sma20), (sma20, sma50)):
        total += 1
        if fast > slow:
            score += 1
    if sma200 is not None:
        total += 1
        if price > sma200:
            score += 1
    return score / total if total else None


def technical_score(features: TechnicalFeatures | None) -> float:
    """0-100: rewards uptrend, healthy (non-extreme) RSI, positive MACD
    momentum and above-average volume confirming the move."""
    if features is None:
        return NEUTRAL_SCORE

    parts: list[float] = []

    if features.trend_score is not None:
        parts.append(features.trend_score * 100)

    if features.rsi_14 is not None:
        rsi_val = features.rsi_14
        if rsi_val >= 80 or rsi_val <= 20:
            rsi_score = 30  # overbought/oversold extremes penalized
        elif 45 <= rsi_val <= 65:
            rsi_score = 90  # healthy momentum zone
        else:
            rsi_score = 60
        parts.append(rsi_score)

    if features.macd is not None and features.macd_signal is not None:
        parts.append(75.0 if features.macd > features.macd_signal else 35.0)

    if features.volume_zscore is not None:
        vz = features.volume_zscore
        parts.append(min(100.0, max(0.0, 50 + vz * 15)))

    if not parts:
        return NEUTRAL_SCORE
    return round(sum(parts) / len(parts), 2)
