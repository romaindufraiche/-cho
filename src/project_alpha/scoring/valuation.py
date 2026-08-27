"""Valuation module (weight 15): multiples, historique, comparables,
DCF / reverse DCF."""

from __future__ import annotations

from project_alpha.data.models import ValuationFeatures
from project_alpha.scoring.utils import NEUTRAL_SCORE, scale_linear as _scale


def valuation_score(val: ValuationFeatures | None) -> float:
    if val is None:
        return NEUTRAL_SCORE

    parts: list[float] = []

    if val.pe_ratio is not None and val.pe_ratio > 0:
        # cheaper (lower PE) scores higher; 8x=rich reward, 40x=expensive
        parts.append(_scale(-val.pe_ratio, lo=-40.0, hi=-8.0))

    if val.pe_vs_5y_avg is not None:
        # negative = trading below own history = attractive
        parts.append(_scale(-val.pe_vs_5y_avg, lo=-0.40, hi=0.40))

    if val.peer_percentile is not None:
        # lower percentile vs peers (cheaper) = higher score
        parts.append(_scale(1 - val.peer_percentile, lo=0.0, hi=1.0))

    if val.dcf_fair_value is not None and val.pe_ratio is not None:
        pass  # requires current price; combined at a higher layer if available

    if not parts:
        return NEUTRAL_SCORE
    return round(sum(parts) / len(parts), 2)


def dcf_upside_score(current_price: float, dcf_fair_value: float | None) -> float:
    if not dcf_fair_value or current_price <= 0:
        return NEUTRAL_SCORE
    upside = (dcf_fair_value - current_price) / current_price
    return _scale(upside, lo=-0.30, hi=0.50)
