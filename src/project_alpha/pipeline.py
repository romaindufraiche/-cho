"""End-to-end daily analysis pipeline for a single ticker, wiring together
data ingestion -> features -> scoring -> pricing -> signal -> recommendation.

Uses yfinance (no API key needed) as the default data source so
`project-alpha analyze` works out of the box, per section 6's prototype
guidance. Optional sources (SEC, Finnhub, FRED, ...) are consulted only if
their API keys are configured (config.py); when absent, the corresponding
module score falls back to NEUTRAL_SCORE rather than failing the run - the
system must degrade, not crash, when a paid/keyed source is unavailable.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from project_alpha.config import SETTINGS
from project_alpha.data.models import (
    CompositeScore,
    Event,
    FundamentalSnapshot,
    MarketRegime,
    ModuleScores,
    PositionSizing,
    PriceZone,
    Recommendation,
    Signal,
    ValuationFeatures,
)
from project_alpha.data.sources import yfinance_source
from project_alpha.scoring.catalyst import catalyst_score
from project_alpha.scoring.composite import build_composite_score
from project_alpha.scoring.expectations import expectations_score
from project_alpha.scoring.fundamental import fundamental_score
from project_alpha.scoring.market_regime import market_regime_score
from project_alpha.scoring.risk import risk_score
from project_alpha.scoring.smart_money import smart_money_score
from project_alpha.scoring.technical import compute_technical_features, technical_score
from project_alpha.scoring.valuation import valuation_score
from project_alpha.signals.engine import evaluate_new_candidate
from project_alpha.signals.pricing import compute_price_zone
from project_alpha.signals.position_sizing import position_size

logger = logging.getLogger(__name__)

# Actionable signals only: WATCH/HOLD/REDUCE/SELL/NO_TRADE don't imply
# opening a new position, so sizing one for them would be misleading.
_ENTRY_SIGNALS = {Signal.BUY, Signal.BUY_ON_DIP}


def compute_recommended_position(
    signal: Signal,
    current_price: float | None,
    zone: PriceZone | None,
    risk_module_score: float,
    portfolio_value: float,
) -> PositionSizing | None:
    """Pure sizing step (section 5), separated from `analyze_ticker` so it's
    unit-testable without a network call: how many shares of `portfolio_value`
    to put on, for an entry signal, given the stop implied by `zone`."""
    if signal not in _ENTRY_SIGNALS or zone is None or current_price is None:
        return None
    sized = position_size(
        portfolio_value=portfolio_value,
        entry_price=current_price,
        stop_price=zone.stop,
        volatility_score=risk_module_score,
    )
    if sized["shares"] <= 0:
        return None
    return PositionSizing(**sized)


def analyze_ticker(
    ticker: str, regime: MarketRegime = MarketRegime.NEUTRAL, portfolio_value: float = 500.0
) -> Recommendation | None:
    bars = yfinance_source.fetch_price_history(ticker)
    if not bars:
        logger.warning("no price history for %s, skipping", ticker)
        return None
    prices = yfinance_source.prices_to_dataframe(bars)

    tech_features = compute_technical_features(ticker, prices)
    if tech_features is None:
        logger.warning("not enough price history for %s, skipping", ticker)
        return None

    current_price = tech_features.close

    fundamentals_raw = yfinance_source.fetch_fundamentals_snapshot(ticker)
    fundamentals = FundamentalSnapshot(ticker=ticker, as_of=tech_features.as_of, **fundamentals_raw)

    valuation_raw = yfinance_source.fetch_valuation_snapshot(ticker)
    valuation = ValuationFeatures(ticker=ticker, as_of=tech_features.as_of, **valuation_raw)

    company = yfinance_source.fetch_company_profile(ticker)

    modules = ModuleScores(
        catalyst=catalyst_score(event=None),  # no live event feed wired by default -> neutral
        fundamental=fundamental_score(fundamentals),
        expectations=expectations_score(None),  # requires Finnhub/FMP estimates
        technical=technical_score(tech_features),
        valuation=valuation_score(valuation),
        market_regime=market_regime_score(regime, beta=company.beta),
        smart_money=smart_money_score(),  # optional, "when available"
        risk=risk_score(),
    )

    composite = build_composite_score(ticker, tech_features.as_of, modules)
    zone = compute_price_zone(current_price, tech_features)
    signal = evaluate_new_candidate(composite, current_price, zone)
    sizing = compute_recommended_position(signal, current_price, zone, modules.risk, portfolio_value)

    return Recommendation(
        ticker=ticker,
        signal=signal,
        score=composite,
        price_zone=zone,
        current_price=current_price,
        position_sizing=sizing,
        thesis_summary=_default_thesis_summary(modules),
        why_now=None,  # requires an Event; populated once the theme graph fires
        invalidation="Stop technique touche, guidance degradee, ou these invalidee.",
        data_version=SETTINGS.data_version,
        scoring_version=SETTINGS.scoring_version,
        model_version=SETTINGS.model_version,
        prompt_version=SETTINGS.prompt_version,
    )


def _default_thesis_summary(modules: ModuleScores) -> str:
    strongest = max(
        (
            ("fondamentaux", modules.fundamental),
            ("technique/momentum", modules.technical),
            ("valorisation", modules.valuation),
        ),
        key=lambda pair: pair[1],
    )
    return f"Module le plus favorable: {strongest[0]} ({strongest[1]}/100)."
