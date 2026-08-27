"""Expectations / Revisions module (weight 15): surprises et evolution des
estimations."""

from __future__ import annotations

from project_alpha.data.models import EstimateRevision
from project_alpha.scoring.utils import NEUTRAL_SCORE, scale_linear as _scale


def expectations_score(rev: EstimateRevision | None) -> float:
    if rev is None:
        return NEUTRAL_SCORE

    parts: list[float] = []

    if rev.eps_surprise_pct is not None:
        parts.append(_scale(rev.eps_surprise_pct, lo=-0.15, hi=0.15))

    revision_pct = rev.eps_revision_pct
    if revision_pct is not None:
        parts.append(_scale(revision_pct, lo=-0.10, hi=0.10))

    if not parts:
        return NEUTRAL_SCORE
    return round(sum(parts) / len(parts), 2)
