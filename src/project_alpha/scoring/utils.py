"""Shared scoring helpers."""

from __future__ import annotations

NEUTRAL_SCORE = 50.0


def scale_linear(value: float, lo: float, hi: float) -> float:
    """Linearly maps `value` in [lo, hi] to [0, 100], clamped at the bounds."""
    if hi == lo:
        return NEUTRAL_SCORE
    pct = (value - lo) / (hi - lo)
    return round(min(1.0, max(0.0, pct)) * 100, 2)
