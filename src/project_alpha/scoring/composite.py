"""Combines the eight weighted modules (section 4) into:

- `weighted_total_score`: the official weighted sum (Catalyst 20, Fundamental
  15, Expectations 15, Technical 15, Valuation 15, Market Regime 5, Smart
  Money 5, Risk 10 = 100). This drives the final signal.
- Three diagnostic scores - Quality / Opportunity / Price - so the system
  never confuses "excellent company" with "excellent buy right now"
  (section 4's explicit warning). Their exact sub-weighting isn't specified
  in the cahier des charges beyond what each conceptually measures, so the
  breakdown below is this implementation's documented design choice.
"""

from __future__ import annotations

from datetime import date

from project_alpha.config import SETTINGS
from project_alpha.data.models import CompositeScore, ModuleScores

# Official weights from section 4 (must sum to 100).
WEIGHTS = {
    "catalyst": 20,
    "fundamental": 15,
    "expectations": 15,
    "technical": 15,
    "valuation": 15,
    "market_regime": 5,
    "smart_money": 5,
    "risk": 10,
}
assert sum(WEIGHTS.values()) == 100


def weighted_total_score(modules: ModuleScores) -> float:
    total = sum(getattr(modules, name) * weight for name, weight in WEIGHTS.items())
    return round(total / 100, 2)


def quality_score(modules: ModuleScores) -> float:
    """"Quality" = is this a good company, independent of timing/price."""
    return round(0.5 * modules.fundamental + 0.3 * modules.risk + 0.2 * modules.smart_money, 2)


def opportunity_score(modules: ModuleScores) -> float:
    """"Opportunity" = is now a good time, i.e. is there a live, unpriced
    catalyst with supportive momentum and market regime."""
    return round(
        0.45 * modules.catalyst
        + 0.30 * modules.expectations
        + 0.15 * modules.market_regime
        + 0.10 * modules.technical,
        2,
    )


def price_score(modules: ModuleScores) -> float:
    """"Price" = is the current price attractive, combining valuation with
    the technical read on where price sits (support proximity, momentum)."""
    return round(0.65 * modules.valuation + 0.35 * modules.technical, 2)


def build_composite_score(ticker: str, as_of: date, modules: ModuleScores) -> CompositeScore:
    return CompositeScore(
        ticker=ticker,
        as_of=as_of,
        modules=modules,
        quality_score=quality_score(modules),
        opportunity_score=opportunity_score(modules),
        price_score=price_score(modules),
        weighted_total_score=weighted_total_score(modules),
        data_version=SETTINGS.data_version,
        scoring_version=SETTINGS.scoring_version,
    )
