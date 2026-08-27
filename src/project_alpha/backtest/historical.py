"""Historical backtest runner (section 9): replays the scoring + signal
engine day by day over a real price history and reports the metrics from
`backtest.metrics`.

IMPORTANT CAVEAT - read before trusting the numbers this produces:
Catalyst, Fundamental, Expectations/Revisions, Valuation and Smart Money
all need point-in-time data (a filing's numbers as they were known on a
given date, historical analyst estimates, ...). The free yfinance `.info`
endpoint only exposes *today's* snapshot, so using it for a historical date
would leak future information into the past - exactly the look-ahead bias
section 9's walk-forward requirement exists to avoid. This runner therefore
holds those five modules at NEUTRAL_SCORE (50) and lets only
Technical/Momentum (weight 15) and Risk (weight 10) vary with history: it
is a genuine, look-ahead-free backtest of the technical/risk slice of the
model, not of the full 8-module system from section 4. Wiring in
point-in-time fundamentals (e.g. SEC EDGAR's dated XBRL facts, which are
suitable for this precisely because each fact carries its own filing date)
is the natural next step to backtest the full model faithfully.

Because 6 of the 8 modules are pinned at neutral, the full-model
`weighted_total_score` can never exceed ~62.5/100 here (50 + 25% max
uplift from the two live modules), well under the live pipeline's
BUY_THRESHOLD of 75 - reusing that threshold would make this backtest
structurally silent (zero trades, always). Entries are therefore decided
on `tech_risk_score`, a 0-100 rescaling of just the two live modules
(Technical 15 + Risk 10 renormalized to 100), against its own
TECH_RISK_BUY_THRESHOLD. This is this runner's own bar, not the section 4
signal engine's - do not compare it directly to BUY_THRESHOLD.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from project_alpha.backtest.engine import compute_backtest_metrics, equity_curve_from_trades
from project_alpha.backtest.metrics import Trade
from project_alpha.data.models import BacktestMetrics, TechnicalFeatures
from project_alpha.scoring.risk import risk_score
from project_alpha.scoring.technical import compute_technical_series, row_to_features, technical_score
from project_alpha.scoring.utils import NEUTRAL_SCORE
from project_alpha.signals.engine import TIME_STOP_WEEKS
from project_alpha.signals.pricing import compute_price_zone

# (ticker, entry date, features, realized_vol) -> (score 0-100, entry
# threshold on that same scale). Ticker/date are only used by the ML-fitted
# hybrid scorer (ml.scoring.make_hybrid_score_fn, wired in by the CLI's
# `--trained` flag) to look up point-in-time fundamentals; the hand-picked
# heuristic below ignores both.
ScoreFn = Callable[[str, "pd.Timestamp", TechnicalFeatures, "float | None"], tuple[float, float]]

# Rows needed before sma_200 (the slowest indicator) is populated; entries
# before this are skipped rather than trading on partial/NaN features.
WARMUP_ROWS = 200

# This runner's own entry bar on the Technical(15)+Risk(10) rescaled-to-100
# score - see the module docstring for why the full model's BUY_THRESHOLD
# does not apply here.
TECH_RISK_BUY_THRESHOLD = 65.0
_TECH_WEIGHT, _RISK_WEIGHT = 15, 10


def simulate_ticker(
    ticker: str, prices: pd.DataFrame, cost_bps: float = 10.0, score_fn: ScoreFn | None = None
) -> list[Trade]:
    """`prices` must be indexed by date with close/high/low/volume columns
    (as produced by `yfinance_source.prices_to_dataframe`). Walks the
    series once, strictly causally: the decision at row T only ever uses
    indicator values computed from rows at or before T. Holds at most one
    open position at a time per ticker.

    `score_fn` decides entries; defaults to the hand-picked Technical(15)+
    Risk(10) weighted average against TECH_RISK_BUY_THRESHOLD (unchanged
    from before this became pluggable) - pass `ml.scoring.trained_entry_score`
    for the ML-fitted weights instead."""
    if len(prices) < WARMUP_ROWS:
        return []

    series = compute_technical_series(ticker, prices)
    # Realized volatility, causal (rolling window looks backward only) -
    # the one piece of the Risk module that's honestly computable from
    # price history alone, without leaking future information.
    realized_vol = prices["close"].pct_change().rolling(20).std() * (252**0.5)
    cost_factor = cost_bps / 10_000

    trades: list[Trade] = []
    position: dict | None = None

    for dt, row in series.iloc[WARMUP_ROWS:].iterrows():
        if pd.isna(row.get("atr_14")):
            continue
        price = float(row["close"])

        if position is None:
            features = row_to_features(ticker, dt.date(), row)
            vol = realized_vol.get(dt)
            vol_value = None if pd.isna(vol) else float(vol)
            if score_fn is not None:
                score, threshold = score_fn(ticker, dt, features, vol_value)
            else:
                tech = technical_score(features)
                risk = risk_score(annualized_volatility=vol_value)
                score = (tech * _TECH_WEIGHT + risk * _RISK_WEIGHT) / (_TECH_WEIGHT + _RISK_WEIGHT)
                threshold = TECH_RISK_BUY_THRESHOLD
            zone = compute_price_zone(price, features)
            in_zone = zone.buy_zone_low * 0.98 <= price <= zone.buy_zone_high
            if score >= threshold and in_zone:
                position = {
                    "entry_date": dt,
                    "entry_price": price * (1 + cost_factor),
                    "stop": zone.stop,
                    "target": zone.target_base,
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
            trades.append(
                Trade(
                    ticker=ticker,
                    entry_date=position["entry_date"],
                    exit_date=dt,
                    entry_price=position["entry_price"],
                    exit_price=price * (1 - cost_factor),
                    exit_reason=exit_reason,
                )
            )
            position = None

    return trades


@dataclass
class UniverseBacktestResult:
    trades: list[Trade]
    equity_curve: pd.Series
    metrics: BacktestMetrics
    trades_per_ticker: dict[str, int] = field(default_factory=dict)
    # Set by the CLI when `--trained` is used, purely for the report footer -
    # the simulation itself doesn't care, it just calls whatever score_fn it's given.
    entry_model: str = "heuristic"


def run_universe_backtest(
    price_data: dict[str, pd.DataFrame],
    starting_capital: float = 100_000.0,
    risk_pct_per_trade: float = 0.01,
    cost_bps: float = 10.0,
    benchmark_equity_curve: pd.Series | None = None,
    benchmark_name: str | None = None,
    score_fn: ScoreFn | None = None,
    entry_model: str = "heuristic",
) -> UniverseBacktestResult:
    """Pure function over already-fetched price data - no network calls -
    so it can be unit-tested with synthetic data and reused by whatever
    fetches the real data (CLI, notebook, ...)."""
    all_trades: list[Trade] = []
    counts: dict[str, int] = {}
    for ticker, prices in price_data.items():
        ticker_trades = simulate_ticker(ticker, prices, cost_bps=cost_bps, score_fn=score_fn)
        counts[ticker] = len(ticker_trades)
        all_trades.extend(ticker_trades)

    equity_curve = equity_curve_from_trades(all_trades, starting_capital, risk_pct_per_trade)
    metrics = compute_backtest_metrics(all_trades, equity_curve, benchmark_equity_curve, benchmark_name)
    return UniverseBacktestResult(all_trades, equity_curve, metrics, counts, entry_model=entry_model)


def fetch_and_run(
    tickers: list[str],
    start: str = "2020-01-01",
    end: str | None = None,
    benchmark_ticker: str | None = "^GSPC",
    **kwargs,
) -> UniverseBacktestResult:
    """Convenience entry point that fetches real yfinance history and runs
    `run_universe_backtest`. Requires outbound internet access to Yahoo
    Finance - not available in every execution environment (e.g. a
    network-restricted sandbox), in which case call `run_universe_backtest`
    directly with your own `price_data`."""
    from project_alpha.data.sources.yfinance_source import (
        fetch_price_history_range,
        prices_to_dataframe,
    )

    price_data: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        df = prices_to_dataframe(fetch_price_history_range(ticker, start, end))
        if not df.empty:
            price_data[ticker] = df

    benchmark_curve = None
    if benchmark_ticker:
        bench_df = prices_to_dataframe(fetch_price_history_range(benchmark_ticker, start, end))
        if not bench_df.empty:
            benchmark_curve = bench_df["close"]

    return run_universe_backtest(
        price_data, benchmark_equity_curve=benchmark_curve, benchmark_name=benchmark_ticker, **kwargs
    )
