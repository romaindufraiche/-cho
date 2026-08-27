import pandas as pd
import pytest

from project_alpha.data.models import TechnicalFeatures
from project_alpha.ml.scoring import make_hybrid_score_fn, predict_win_probability, trained_entry_score

_FULL_WEIGHTS = {
    "feature_names": [
        "trend_score", "rsi_14", "macd_hist", "volume_zscore", "atr_pct", "realized_vol",
        "revenue_growth_yoy", "gross_margin", "operating_margin", "free_cash_flow_margin",
        "net_debt_to_ebitda", "pe_ratio",
    ],
    "means": {k: 0.0 for k in [
        "trend_score", "rsi_14", "macd_hist", "volume_zscore", "atr_pct", "realized_vol",
        "revenue_growth_yoy", "gross_margin", "operating_margin", "free_cash_flow_margin",
        "net_debt_to_ebitda", "pe_ratio",
    ]},
    "stds": {k: 1.0 for k in [
        "trend_score", "rsi_14", "macd_hist", "volume_zscore", "atr_pct", "realized_vol",
        "revenue_growth_yoy", "gross_margin", "operating_margin", "free_cash_flow_margin",
        "net_debt_to_ebitda", "pe_ratio",
    ]},
    "coefficients": {k: 0.1 for k in [
        "trend_score", "rsi_14", "macd_hist", "volume_zscore", "atr_pct", "realized_vol",
        "revenue_growth_yoy", "gross_margin", "operating_margin", "free_cash_flow_margin",
        "net_debt_to_ebitda", "pe_ratio",
    ]},
    "intercept": 0.0,
    "metrics": {"deployment_threshold": 0.6},
}

_WEIGHTS = {
    "feature_names": ["trend_score", "rsi_14", "macd_hist", "volume_zscore", "atr_pct", "realized_vol"],
    "means": {"trend_score": 0.5, "rsi_14": 50.0, "macd_hist": 0.0, "volume_zscore": 0.0, "atr_pct": 0.02, "realized_vol": 0.25},
    "stds": {"trend_score": 0.3, "rsi_14": 15.0, "macd_hist": 1.0, "volume_zscore": 1.0, "atr_pct": 0.01, "realized_vol": 0.1},
    "coefficients": {"trend_score": 1.2, "rsi_14": 0.3, "macd_hist": 0.5, "volume_zscore": 0.1, "atr_pct": -0.4, "realized_vol": -0.6},
    "intercept": -0.2,
    "metrics": {"deployment_threshold": 0.55},
}


def _features(**overrides) -> TechnicalFeatures:
    base = dict(
        ticker="TEST", as_of="2024-01-01", close=100.0, sma_20=99, sma_50=95, sma_200=90,
        rsi_14=60.0, macd=1.0, macd_signal=0.5, atr_14=2.0, volume_zscore=0.5, trend_score=1.0,
    )
    base.update(overrides)
    return TechnicalFeatures(**base)


def test_predict_win_probability_is_a_probability():
    proba = predict_win_probability(_features(), realized_vol=0.2, weights=_WEIGHTS)
    assert proba is not None
    assert 0.0 <= proba <= 1.0


def test_predict_win_probability_none_when_indicators_missing():
    assert predict_win_probability(_features(atr_14=None), realized_vol=0.2, weights=_WEIGHTS) is None
    assert predict_win_probability(_features(), realized_vol=None, weights=_WEIGHTS) is None


def test_higher_trend_score_increases_probability():
    low = predict_win_probability(_features(trend_score=0.0), realized_vol=0.2, weights=_WEIGHTS)
    high = predict_win_probability(_features(trend_score=1.0), realized_vol=0.2, weights=_WEIGHTS)
    assert high > low


def test_trained_entry_score_uses_deployment_threshold():
    score, threshold = trained_entry_score(_features(), realized_vol=0.2, weights=_WEIGHTS)
    assert threshold == pytest.approx(55.0)
    assert 0.0 <= score <= 100.0


def test_trained_entry_score_never_enters_on_missing_features():
    score, threshold = trained_entry_score(_features(atr_14=None), realized_vol=0.2, weights=_WEIGHTS)
    assert score == 0.0
    assert threshold == 100.0


def test_hybrid_uses_full_model_when_fundamentals_available():
    snapshot_date = pd.Timestamp("2024-01-01")
    fundamentals = pd.DataFrame(
        [{"revenue_growth_yoy": 0.1, "gross_margin": 0.4, "operating_margin": 0.2,
          "free_cash_flow_margin": 0.15, "net_debt_to_ebitda": 0.5, "eps_diluted": 5.0}],
        index=pd.DatetimeIndex([snapshot_date], name="filed"),
    )
    score_fn = make_hybrid_score_fn(_WEIGHTS, _FULL_WEIGHTS, {"AAPL": fundamentals})
    score, threshold = score_fn("AAPL", snapshot_date, _features(), 0.2)
    assert threshold == pytest.approx(60.0)  # the full model's deployment_threshold, not _WEIGHTS'
    assert 0.0 <= score <= 100.0


def test_hybrid_falls_back_to_base_model_without_fundamentals():
    score_fn = make_hybrid_score_fn(_WEIGHTS, _FULL_WEIGHTS, fundamentals_by_ticker={})
    score, threshold = score_fn("SIE.DE", pd.Timestamp("2024-01-01"), _features(), 0.2)
    assert threshold == pytest.approx(55.0)  # _WEIGHTS' deployment_threshold


def test_hybrid_falls_back_when_no_full_model_trained_yet():
    score_fn = make_hybrid_score_fn(_WEIGHTS, full_weights=None, fundamentals_by_ticker={})
    score, threshold = score_fn("AAPL", pd.Timestamp("2024-01-01"), _features(), 0.2)
    assert threshold == pytest.approx(55.0)
