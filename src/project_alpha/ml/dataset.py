"""Training-example generation for the Technical/Risk weight fit (see
`ml/train.py`). Pure functions over already-fetched price history - no
network calls - so this is unit-testable the same way
`backtest.historical` is.

Walks each ticker's price series exactly like
`backtest.historical.simulate_ticker` (one candidate position at a time,
same stop / target / time-stop exit rule), but *without* gating entries on
the hand-picked Technical(15)+Risk(10) score: every day the price sits in
the computed buy zone becomes a labeled example (features at entry -> 1 if
the trade would have hit its target before its stop, else 0). Dropping the
score gate here is deliberate - it's exactly the gate we're trying to
learn a replacement for, so training on data pre-filtered by it would bake
the old guess into the "trained" one.
"""

from __future__ import annotations

import pandas as pd

from project_alpha.data.models import TechnicalFeatures
from project_alpha.data.sources.sec_edgar_fundamentals import as_of
from project_alpha.scoring.technical import compute_technical_series, row_to_features
from project_alpha.signals.engine import TIME_STOP_WEEKS
from project_alpha.signals.pricing import compute_price_zone

WARMUP_ROWS = 200

FEATURE_NAMES = ["trend_score", "rsi_14", "macd_hist", "volume_zscore", "atr_pct", "realized_vol"]

# Fundamental/Valuation slice, only fillable for US filers via SEC EDGAR
# point-in-time data (see data/sources/sec_edgar_fundamentals.py) - absent
# for every European name in this project's universe, which have NaN here
# and are simply excluded when training on EXTENDED_FEATURE_NAMES.
FUNDAMENTAL_FEATURES = [
    "revenue_growth_yoy", "gross_margin", "operating_margin", "free_cash_flow_margin", "net_debt_to_ebitda",
]  # fmt: skip
VALUATION_FEATURES = ["pe_ratio"]
EXTENDED_FEATURE_NAMES = [*FEATURE_NAMES, *FUNDAMENTAL_FEATURES, *VALUATION_FEATURES]

_DATASET_COLUMNS = ["ticker", "entry_date", "exit_date", "exit_reason", "label", *EXTENDED_FEATURE_NAMES]


def feature_vector(features: TechnicalFeatures, realized_vol: float | None) -> dict[str, float] | None:
    """None if any input indicator is still NaN (e.g. not enough warmup) -
    such rows are excluded from training rather than imputed, since a
    fabricated value would be a fabricated weight."""
    if features.atr_14 is None or not features.close:
        return None
    if features.macd is None or features.macd_signal is None:
        return None
    values = {
        "trend_score": features.trend_score,
        "rsi_14": features.rsi_14,
        "macd_hist": features.macd - features.macd_signal,
        "volume_zscore": features.volume_zscore,
        "atr_pct": features.atr_14 / features.close,
        "realized_vol": realized_vol,
    }
    if any(v is None for v in values.values()):
        return None
    return values


def extended_feature_vector(
    features: TechnicalFeatures, realized_vol: float | None, fundamentals_snapshot: dict | None, price: float
) -> dict[str, float] | None:
    """`feature_vector` plus Fundamental/Valuation, using the latest SEC
    filing known as of the entry date (`fundamentals_snapshot`, from
    `sec_edgar_fundamentals.as_of`). None whenever any input is missing -
    including simply having no US filing yet (or ever, for non-US tickers) -
    so callers naturally fall back to the Technical/Risk-only model."""
    base = feature_vector(features, realized_vol)
    if base is None or fundamentals_snapshot is None:
        return None
    eps = fundamentals_snapshot.get("eps_diluted")
    pe_ratio = price / eps if eps and eps > 0 and price else None
    extra = {
        "revenue_growth_yoy": fundamentals_snapshot.get("revenue_growth_yoy"),
        "gross_margin": fundamentals_snapshot.get("gross_margin"),
        "operating_margin": fundamentals_snapshot.get("operating_margin"),
        "free_cash_flow_margin": fundamentals_snapshot.get("free_cash_flow_margin"),
        "net_debt_to_ebitda": fundamentals_snapshot.get("net_debt_to_ebitda"),
        "pe_ratio": pe_ratio,
    }
    if any(v is None for v in extra.values()):
        return None
    return {**base, **extra}


def label_entries_for_ticker(
    ticker: str, prices: pd.DataFrame, cost_bps: float = 10.0, fundamentals: pd.DataFrame | None = None
) -> pd.DataFrame:
    """`fundamentals`, when given (see `sec_edgar_fundamentals.point_in_time_fundamentals`),
    adds Fundamental/Valuation columns looked up as-of each entry date - NaN
    wherever no SEC filing predates that entry (before the ticker's first
    10-K, or for any non-US ticker, where `fundamentals` is typically empty)."""
    if len(prices) < WARMUP_ROWS:
        return pd.DataFrame(columns=_DATASET_COLUMNS)

    series = compute_technical_series(ticker, prices)
    realized_vol = prices["close"].pct_change().rolling(20).std() * (252**0.5)
    cost_factor = cost_bps / 10_000

    rows: list[dict] = []
    position: dict | None = None

    for dt, row in series.iloc[WARMUP_ROWS:].iterrows():
        if pd.isna(row.get("atr_14")):
            continue
        price = float(row["close"])

        if position is None:
            features = row_to_features(ticker, dt.date(), row)
            vol = realized_vol.get(dt)
            vol_value = None if pd.isna(vol) else float(vol)
            zone = compute_price_zone(price, features)
            in_zone = zone.buy_zone_low * 0.98 <= price <= zone.buy_zone_high
            if not in_zone:
                continue
            fv = feature_vector(features, vol_value)
            if fv is None:
                continue
            if fundamentals is not None and not fundamentals.empty:
                snapshot = as_of(fundamentals, dt)
                extended = extended_feature_vector(features, vol_value, snapshot, price)
                if extended is not None:
                    fv = extended
            position = {
                "entry_date": dt,
                "entry_price": price * (1 + cost_factor),
                "stop": zone.stop,
                "target": zone.target_base,
                "features": fv,
            }
            continue

        weeks_held = (dt - position["entry_date"]).days / 7
        exit_reason = None
        if price <= position["stop"]:
            exit_reason = "stop_hit"
        elif price >= position["target"]:
            exit_reason = "target_reached"
        elif weeks_held >= TIME_STOP_WEEKS and price <= position["entry_price"]:
            exit_reason = "time_stop"

        if exit_reason:
            rows.append(
                {
                    "ticker": ticker,
                    "entry_date": position["entry_date"],
                    "exit_date": dt,
                    "exit_reason": exit_reason,
                    "label": 1 if exit_reason == "target_reached" else 0,
                    **position["features"],
                }
            )
            position = None
        # else: still open (or still-open at series end) - dropped rather
        # than labeled, since we don't know how it would have resolved.

    return pd.DataFrame(rows, columns=_DATASET_COLUMNS)


def build_dataset(
    price_data: dict[str, pd.DataFrame],
    cost_bps: float = 10.0,
    fundamentals_by_ticker: dict[str, pd.DataFrame] | None = None,
) -> pd.DataFrame:
    fundamentals_by_ticker = fundamentals_by_ticker or {}
    frames = [
        label_entries_for_ticker(ticker, prices, cost_bps, fundamentals_by_ticker.get(ticker))
        for ticker, prices in price_data.items()
    ]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=_DATASET_COLUMNS)
    return pd.concat(frames, ignore_index=True)
