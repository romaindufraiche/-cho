"""Catalyst module (weight 20, the heaviest): force, nouveaute et proximite
du catalyseur. This is the entry point of the Event -> Theme -> Company
engine (section 3): a strong, fresh, near-term, not-yet-priced catalyst is
what turns a good company into a live opportunity."""

from __future__ import annotations

from datetime import datetime

from project_alpha.data.models import Event
from project_alpha.scoring.utils import NEUTRAL_SCORE, scale_linear

# Rough category strength priors (0-1); tune as the event detector matures.
_CATEGORY_STRENGTH = {
    "earnings": 0.6,
    "guidance": 0.8,
    "contract": 0.6,
    "capex": 0.5,
    "mna": 0.9,
    "regulation": 0.5,
    "macro": 0.4,
    "geopolitical": 0.4,
    "supply_shock": 0.7,
    "sector_disruption": 0.7,
}


def catalyst_score(
    event: Event | None,
    exposure_weight: float = 1.0,
    market_already_priced: bool | None = None,
) -> float:
    """`market_already_priced`: comparison of new info vs consensus vs price
    reaction (section 3). A catalyst already reflected in the price is not
    an opportunity, so it heavily discounts the score."""
    if event is None:
        return NEUTRAL_SCORE

    strength = _CATEGORY_STRENGTH.get(event.category.value, 0.5)
    freshness = _freshness_factor(event.detected_at)
    score = strength * freshness * exposure_weight * 100

    already_priced = (
        market_already_priced if market_already_priced is not None else event.already_priced
    )
    if already_priced is True:
        score *= 0.35
    elif already_priced is False:
        score *= 1.1

    return round(min(100.0, max(0.0, score)), 2)


def _freshness_factor(detected_at: datetime, half_life_days: float = 10.0) -> float:
    """Exponential decay: a catalyst loses relevance as it ages, on a
    half_life_days scale (proximity du catalyseur)."""
    age_days = max(0.0, (datetime.utcnow() - detected_at).total_seconds() / 86400)
    return 0.5 ** (age_days / half_life_days)


def proximity_score(days_to_catalyst: float | None) -> float:
    """For forward-looking catalysts (e.g. upcoming earnings date): the
    closer the catalyst, the higher the score."""
    if days_to_catalyst is None:
        return NEUTRAL_SCORE
    return scale_linear(-days_to_catalyst, lo=-60.0, hi=0.0)
