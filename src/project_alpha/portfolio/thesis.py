"""Thesis Tracker (section 10): every position records the buy reason, the
expected catalyst, the horizon, the expected return and the invalidation
conditions; every review re-evaluates the thesis automatically."""

from __future__ import annotations

from project_alpha.data.models import Thesis, ThesisReview


def open_thesis(
    ticker: str,
    reason: str,
    catalyst: str,
    horizon_weeks: int,
    expected_return_pct: float,
    invalidation_conditions: str,
) -> Thesis:
    return Thesis(
        ticker=ticker,
        reason=reason,
        catalyst=catalyst,
        horizon_weeks=horizon_weeks,
        expected_return_pct=expected_return_pct,
        invalidation_conditions=invalidation_conditions,
    )


def review_thesis(thesis: Thesis, still_valid: bool, note: str | None, score_at_review: float) -> Thesis:
    """Every "revue reevalue automatiquement la these" (section 10): appends
    a timestamped review rather than mutating history, keeping the thesis
    auditable end to end."""
    updated = thesis.model_copy(deep=True)
    updated.reviews.append(
        ThesisReview(still_valid=still_valid, note=note, score_at_review=score_at_review)
    )
    return updated


def close_thesis(thesis: Thesis, reason: str) -> Thesis:
    from datetime import datetime

    updated = thesis.model_copy(deep=True)
    updated.closed_at = datetime.utcnow()
    updated.close_reason = reason
    return updated
