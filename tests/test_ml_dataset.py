import numpy as np
import pandas as pd

from project_alpha.data.models import TechnicalFeatures
from project_alpha.ml.dataset import (
    EXTENDED_FEATURE_NAMES,
    FEATURE_NAMES,
    build_dataset,
    extended_feature_vector,
    label_entries_for_ticker,
)


def _trending_prices(n=500, start=100.0, drift=0.0015, vol=0.01, seed=1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    returns = rng.normal(loc=drift, scale=vol, size=n)
    close = start * (1 + pd.Series(returns)).cumprod()
    high = close * 1.008
    low = close * 0.992
    volume = pd.Series(rng.integers(1_000_000, 5_000_000, size=n), dtype=float)
    idx = pd.date_range("2015-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"open": close, "high": high.values, "low": low.values, "close": close.values, "volume": volume.values},
        index=idx,
    )


def _choppy_prices(n=500, start=100.0, seed=2) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    noise = rng.normal(loc=-0.0005, scale=0.02, size=n)
    close = start * (1 + pd.Series(noise)).cumprod()
    idx = pd.date_range("2015-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": close,
            "high": close.values * 1.01,
            "low": close.values * 0.99,
            "close": close.values,
            "volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )


def test_label_entries_returns_expected_columns():
    df = label_entries_for_ticker("TEST", _trending_prices(n=600))
    assert not df.empty
    for col in ["ticker", "entry_date", "exit_date", "exit_reason", "label", *FEATURE_NAMES]:
        assert col in df.columns
    assert set(df["label"].unique()) <= {0, 1}
    assert set(df["exit_reason"].unique()) <= {"stop_hit", "target_reached", "time_stop"}


def test_label_entries_too_short_series_is_empty():
    df = label_entries_for_ticker("TEST", _trending_prices(n=50))
    assert df.empty


def test_label_entries_no_lookahead():
    """Truncating the series after the last labeled exit must not change
    any earlier label - same causality guarantee as simulate_ticker."""
    prices = _trending_prices(n=600)
    df = label_entries_for_ticker("TEST", prices)
    assert not df.empty

    cutoff = df.iloc[0]["exit_date"]
    truncated = prices.loc[:cutoff]
    df_truncated = label_entries_for_ticker("TEST", truncated)

    assert not df_truncated.empty
    assert df_truncated.iloc[0]["entry_date"] == df.iloc[0]["entry_date"]
    assert df_truncated.iloc[0]["label"] == df.iloc[0]["label"]


def test_build_dataset_aggregates_across_tickers():
    price_data = {
        "UP": _trending_prices(n=600, seed=1),
        "CHOP": _choppy_prices(n=600, seed=2),
    }
    df = build_dataset(price_data)
    assert set(df["ticker"].unique()) <= {"UP", "CHOP"}
    assert not df.empty


def test_build_dataset_empty_when_no_data():
    assert build_dataset({}).empty


def _technical_features() -> TechnicalFeatures:
    return TechnicalFeatures(
        ticker="TEST", as_of="2024-01-01", close=150.0, sma_20=145, sma_50=140, sma_200=130,
        rsi_14=60.0, macd=1.0, macd_signal=0.5, atr_14=3.0, volume_zscore=0.5, trend_score=1.0,
    )


_FUNDAMENTALS_SNAPSHOT = {
    "revenue_growth_yoy": 0.1, "gross_margin": 0.4, "operating_margin": 0.25,
    "free_cash_flow_margin": 0.2, "net_debt_to_ebitda": 0.5, "eps_diluted": 5.0,
}


def test_extended_feature_vector_includes_fundamentals():
    fv = extended_feature_vector(_technical_features(), realized_vol=0.2, fundamentals_snapshot=_FUNDAMENTALS_SNAPSHOT, price=150.0)
    assert fv is not None
    assert set(EXTENDED_FEATURE_NAMES) <= set(fv)
    assert fv["pe_ratio"] == 30.0


def test_extended_feature_vector_none_without_fundamentals():
    assert extended_feature_vector(_technical_features(), realized_vol=0.2, fundamentals_snapshot=None, price=150.0) is None


def test_extended_feature_vector_none_when_eps_missing():
    snap = {**_FUNDAMENTALS_SNAPSHOT, "eps_diluted": None}
    assert extended_feature_vector(_technical_features(), realized_vol=0.2, fundamentals_snapshot=snap, price=150.0) is None


def test_label_entries_attaches_fundamentals_for_covered_ticker():
    prices = _trending_prices(n=600)
    fundamentals = pd.DataFrame(
        [_FUNDAMENTALS_SNAPSHOT],
        index=pd.DatetimeIndex([prices.index[0]], name="filed"),
    )
    df = label_entries_for_ticker("TEST", prices, fundamentals=fundamentals)
    assert not df.empty
    assert df["pe_ratio"].notna().any()
