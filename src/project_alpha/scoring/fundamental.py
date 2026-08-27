"""Fundamental module (weight 15): croissance, marges, FCF, dette, ROIC,
guidance."""

from __future__ import annotations

from project_alpha.data.models import FundamentalSnapshot
from project_alpha.scoring.utils import NEUTRAL_SCORE, scale_linear as _scale


def fundamental_score(snap: FundamentalSnapshot | None) -> float:
    if snap is None:
        return NEUTRAL_SCORE

    parts: list[float] = []

    if snap.revenue_growth_yoy is not None:
        parts.append(_scale(snap.revenue_growth_yoy, lo=-0.10, hi=0.30))

    if snap.gross_margin is not None:
        parts.append(_scale(snap.gross_margin, lo=0.10, hi=0.70))

    if snap.operating_margin is not None:
        parts.append(_scale(snap.operating_margin, lo=-0.05, hi=0.35))

    if snap.free_cash_flow is not None:
        parts.append(70.0 if snap.free_cash_flow > 0 else 30.0)

    if snap.net_debt_to_ebitda is not None:
        # lower leverage is better; >5x is stressed, <0 (net cash) is best
        parts.append(_scale(-snap.net_debt_to_ebitda, lo=-5.0, hi=1.0))

    if snap.roic is not None:
        parts.append(_scale(snap.roic, lo=0.0, hi=0.25))

    if snap.guidance_direction is not None:
        parts.append({-1: 20.0, 0: 55.0, 1: 85.0}[snap.guidance_direction])

    if not parts:
        return NEUTRAL_SCORE
    return round(sum(parts) / len(parts), 2)
