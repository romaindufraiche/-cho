"""Runtime inference for the trained weights (no scikit-learn dependency
here - training needs it, scoring a logistic regression is just
arithmetic, so production doesn't need to install it).

Loads the JSON produced by `ml.train.train_and_evaluate` /
`ml.train.save_weights` and reproduces the fitted sigmoid by hand. This is
the `score_fn` plugged into `backtest.historical.simulate_ticker` in place
of the hand-picked Technical(15)+Risk(10) weighted average and its fixed 65
threshold.

`make_hybrid_score_fn` combines two fitted models: the "full" one (Technical
+ Risk + Fundamental + Valuation, US filers only - see
data/sources/sec_edgar_fundamentals.py) when a ticker has SEC filings known
as of the given date, falling back to the "base" Technical/Risk-only model
otherwise (every European ticker, and any US ticker before its first 10-K).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import pandas as pd

from project_alpha.data.models import TechnicalFeatures
from project_alpha.data.sources.sec_edgar_fundamentals import as_of
from project_alpha.ml.dataset import extended_feature_vector, feature_vector

DEFAULT_WEIGHTS_PATH = Path(__file__).with_name("technical_risk_weights.json")
EXTENDED_WEIGHTS_PATH = Path(__file__).with_name("full_weights.json")


class WeightsNotFound(FileNotFoundError):
    pass


@lru_cache(maxsize=4)
def load_weights(path: str = str(DEFAULT_WEIGHTS_PATH)) -> dict:
    p = Path(path)
    if not p.exists():
        raise WeightsNotFound(
            f"No trained weights at {p}. Run `project-alpha train-weights` first, "
            "or pass --no-trained to fall back to the hand-picked heuristic."
        )
    return json.loads(p.read_text())


def _score_from_vector(fv: dict[str, float], weights: dict) -> float:
    z = weights["intercept"]
    for name in weights["feature_names"]:
        std = weights["stds"][name] or 1.0
        z += weights["coefficients"][name] * (fv[name] - weights["means"][name]) / std
    return 1.0 / (1.0 + math.exp(-z))


def predict_win_probability(features: TechnicalFeatures, realized_vol: float | None, weights: dict) -> float | None:
    fv = feature_vector(features, realized_vol)
    if fv is None:
        return None
    return _score_from_vector(fv, weights)


def trained_entry_score(
    features: TechnicalFeatures, realized_vol: float | None, weights: dict | None = None
) -> tuple[float, float]:
    """`score_fn` for `simulate_ticker` (single-model form): (probability *
    100, deployment threshold * 100). Missing indicators score 0 against a
    100 threshold, i.e. never enter, rather than guessing."""
    weights = weights if weights is not None else load_weights()
    proba = predict_win_probability(features, realized_vol, weights)
    if proba is None:
        return 0.0, 100.0
    threshold = weights["metrics"].get("deployment_threshold", 0.5)
    return proba * 100, threshold * 100


def make_hybrid_score_fn(
    base_weights: dict,
    full_weights: dict | None = None,
    fundamentals_by_ticker: dict[str, pd.DataFrame] | None = None,
) -> Callable[[str, "pd.Timestamp", TechnicalFeatures, "float | None"], tuple[float, float]]:
    """Per-ticker: use `full_weights` when it has a SEC filing known as of
    that date, else fall back to `base_weights`. Ticker/date-aware, unlike
    `trained_entry_score`, since the fundamentals lookup depends on both."""
    fundamentals_by_ticker = fundamentals_by_ticker or {}

    def score_fn(ticker: str, dt, features: TechnicalFeatures, realized_vol: float | None) -> tuple[float, float]:
        if full_weights is not None:
            fdf = fundamentals_by_ticker.get(ticker)
            if fdf is not None and not fdf.empty:
                snapshot = as_of(fdf, dt)
                if snapshot is not None:
                    fv = extended_feature_vector(features, realized_vol, snapshot, features.close)
                    if fv is not None:
                        proba = _score_from_vector(fv, full_weights)
                        threshold = full_weights["metrics"].get("deployment_threshold", 0.5)
                        return proba * 100, threshold * 100
        return trained_entry_score(features, realized_vol, base_weights)

    return score_fn
