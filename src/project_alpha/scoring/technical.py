"""Technical / Momentum module (weight 15): tendance, RSI, MACD, volume,
supports/resistances."""

from __future__ import annotations

from datetime import date

import numpy as np
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


def compute_technical_series(ticker: str, prices: pd.DataFrame) -> pd.DataFrame:
    """Computes every indicator for the *entire* price history at once,
    causally (each row only ever depends on rows at or before it, since
    rolling/ewm windows are backward-looking by construction). This is what
    lets the historical backtest (`backtest/historical.py`) walk day by day
    without look-ahead bias, while `compute_technical_features` below just
    takes the last row for the live/daily-analysis pipeline."""
    close, high, low, volume = prices["close"], prices["high"], prices["low"], prices["volume"]
    macd_line, signal_line = macd(close)
    support, resistance = rolling_support_resistance(high, low)

    df = pd.DataFrame(
        {
            "close": close,
            "sma_20": sma(close, 20),
            "sma_50": sma(close, 50),
            "sma_200": sma(close, 200),
            "rsi_14": rsi(close, 14),
            "macd": macd_line,
            "macd_signal": signal_line,
            "atr_14": atr(high, low, close, 14),
            "volume_zscore": volume_zscore(volume, 20),
            "support": support,
            "resistance": resistance,
        },
        index=prices.index,
    )
    df["trend_score"] = _trend_score_series(df)
    return df


def compute_technical_features(ticker: str, prices: pd.DataFrame) -> TechnicalFeatures | None:
    """`prices` must be a DataFrame indexed by date with open/high/low/close/volume
    columns (as produced by `yfinance_source.prices_to_dataframe`)."""
    if prices.empty or len(prices) < 20:
        return None

    series = compute_technical_series(ticker, prices)
    last_idx = series.index[-1]
    as_of = last_idx.date() if hasattr(last_idx, "date") else date.today()
    return row_to_features(ticker, as_of, series.iloc[-1])


def row_to_features(ticker: str, as_of, row: pd.Series) -> TechnicalFeatures:
    def _f(key: str) -> float | None:
        val = row.get(key)
        return None if pd.isna(val) else float(val)

    return TechnicalFeatures(
        ticker=ticker,
        as_of=as_of,
        close=float(row["close"]),
        sma_20=_f("sma_20"),
        sma_50=_f("sma_50"),
        sma_200=_f("sma_200"),
        rsi_14=_f("rsi_14"),
        macd=_f("macd"),
        macd_signal=_f("macd_signal"),
        atr_14=_f("atr_14"),
        volume_zscore=_f("volume_zscore"),
        support=_f("support"),
        resistance=_f("resistance"),
        trend_score=_f("trend_score"),
    )


def _trend_score_series(df: pd.DataFrame) -> pd.Series:
    has_20_50 = df["sma_20"].notna() & df["sma_50"].notna()
    has_200 = df["sma_200"].notna()

    v1 = df["close"] > df["sma_20"]
    v2 = df["sma_20"] > df["sma_50"]
    v3 = df["close"] > df["sma_200"]

    score = pd.Series(np.nan, index=df.index)

    two_only = has_20_50 & ~has_200
    score[two_only] = (v1[two_only].astype(float) + v2[two_only].astype(float)) / 2

    all_three = has_20_50 & has_200
    score[all_three] = (
        v1[all_three].astype(float) + v2[all_three].astype(float) + v3[all_three].astype(float)
    ) / 3

    return score


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
