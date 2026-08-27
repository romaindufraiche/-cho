"""Fits the Technical/Risk entry weights on real history (requires the
`ml` extra: `pip install -e ".[ml]"` for scikit-learn - training-only, the
runtime scorer in `ml/scoring.py` doesn't need it).

Replaces the hand-picked Technical(15)+Risk(10) weighted average and its
fixed 65 threshold (see `backtest/historical.py`) with a logistic
regression fit on `ml.dataset.build_dataset`'s labeled entries: does the
setup at each feature vector actually predict hitting target before stop,
based on what happened historically. Chronological train/test split (no
shuffling) so the reported test metrics are genuinely out-of-sample.

Deliberately out of scope: Catalyst, Fundamental, Expectations, Valuation
and Smart Money still have no point-in-time historical source (see
backtest/historical.py's module docstring) - training weights for them
would mean fitting to today's-snapshot-leaked-into-the-past data, which is
worse than not training them at all. This only touches the 25/100 slice
that has honest history to learn from.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from project_alpha.data.sources.sec_edgar_fundamentals import point_in_time_fundamentals
from project_alpha.data.sources.yfinance_source import fetch_price_history_range, prices_to_dataframe
from project_alpha.ml.dataset import FEATURE_NAMES, build_dataset

DEFAULT_WEIGHTS_PATH = Path(__file__).with_name("technical_risk_weights.json")
EXTENDED_WEIGHTS_PATH = Path(__file__).with_name("full_weights.json")

# US + Europe large caps across sectors, deliberately broader than (and
# overlapping with) any single recommendation universe, so the fit isn't
# tuned to the specific names it will later be asked to score.
TRAINING_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    "JPM", "V", "MA", "UNH", "JNJ", "PG", "KO", "PEP", "HD",
    "XOM", "CVX", "DIS", "NFLX", "ADBE", "CRM", "CSCO", "INTC",
    "SIE.DE", "SAP.DE", "MC.PA", "OR.PA", "ASML.AS", "TTE.PA",
    "AIR.PA", "ALV.DE", "NESN.SW", "SAN.PA",
]  # fmt: skip


def fetch_training_price_data(tickers: list[str], start: str, end: str | None = None) -> dict[str, pd.DataFrame]:
    price_data: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        df = prices_to_dataframe(fetch_price_history_range(ticker, start, end))
        if not df.empty:
            price_data[ticker] = df
    return price_data


def fetch_training_fundamentals(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """US filers only - `point_in_time_fundamentals` returns an empty frame
    for anything the SEC has no 10-K history for (European tickers, mainly),
    which `build_dataset` handles by leaving those rows' Fundamental/
    Valuation columns NaN."""
    fundamentals: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        df = point_in_time_fundamentals(ticker)
        if not df.empty:
            fundamentals[ticker] = df
    return fundamentals


def _standardize(df: pd.DataFrame, means: dict[str, float], stds: dict[str, float], feature_names: list[str]) -> np.ndarray:
    return np.column_stack([(df[f] - means[f]) / stds[f] for f in feature_names])


def train_and_evaluate(dataset: pd.DataFrame, cutoff_date: str | date, feature_names: list[str] = FEATURE_NAMES) -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score

    dataset = dataset.dropna(subset=[*feature_names, "label"]).copy()
    dataset["entry_date"] = pd.to_datetime(dataset["entry_date"])
    cutoff = pd.Timestamp(cutoff_date)
    train = dataset[dataset["entry_date"] < cutoff]
    test = dataset[dataset["entry_date"] >= cutoff]
    if len(train) < 30 or len(test) < 10:
        raise ValueError(
            f"not enough data to train reliably (train={len(train)}, test={len(test)}) "
            "- widen the date range, add tickers, or move the cutoff"
        )

    means = {f: float(train[f].mean()) for f in feature_names}
    stds = {f: float(train[f].std(ddof=0)) or 1.0 for f in feature_names}
    X_train = _standardize(train, means, stds, feature_names)
    y_train = train["label"].to_numpy()
    X_test = _standardize(test, means, stds, feature_names)
    y_test = test["label"].to_numpy()

    model = LogisticRegression(max_iter=1000)
    model.fit(X_train, y_train)

    train_proba = model.predict_proba(X_train)[:, 1]
    test_proba = model.predict_proba(X_test)[:, 1]

    # Pick the entry-probability cutoff on the TRAIN set only (max F1), then
    # evaluate that fixed threshold on the held-out TEST set - tuning it on
    # the test set would leak the very thing we're trying to validate.
    thresholds = np.linspace(0.2, 0.8, 25)
    f1s = [f1_score(y_train, (train_proba >= t).astype(int), zero_division=0) for t in thresholds]
    deployment_threshold = float(thresholds[int(np.argmax(f1s))])
    test_pred = (test_proba >= deployment_threshold).astype(int)

    metrics = {
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "train_base_rate": round(float(y_train.mean()), 4),
        "test_base_rate": round(float(y_test.mean()), 4),
        "deployment_threshold": round(deployment_threshold, 4),
        "test_n_signals": int(test_pred.sum()),
        "test_precision": round(float(precision_score(y_test, test_pred, zero_division=0)), 4),
        "test_recall": round(float(recall_score(y_test, test_pred, zero_division=0)), 4),
        "test_auc": round(float(roc_auc_score(y_test, test_proba)), 4) if len(set(y_test)) > 1 else None,
    }

    coefficients = {name: float(c) for name, c in zip(feature_names, model.coef_[0])}
    total_abs = sum(abs(c) for c in coefficients.values()) or 1.0
    normalized_weights_pct = {k: round(abs(v) / total_abs * 100, 2) for k, v in coefficients.items()}

    return {
        "feature_names": feature_names,
        "means": means,
        "stds": stds,
        "coefficients": coefficients,
        "intercept": float(model.intercept_[0]),
        "normalized_weights_pct": normalized_weights_pct,
        "metrics": metrics,
        "cutoff_date": str(cutoff.date()),
        "universe": sorted(dataset["ticker"].unique().tolist()),
        "trained_at": pd.Timestamp.utcnow().isoformat(),
    }


def save_weights(result: dict, path: Path = DEFAULT_WEIGHTS_PATH) -> None:
    path.write_text(json.dumps(result, indent=2))
