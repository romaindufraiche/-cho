"""Smart Money module (weight 5): insiders, 13F, short interest, flux
lorsque disponibles. Optional by design - the spec explicitly scopes this
to "when available", so missing data returns a neutral score rather than
penalizing the candidate."""

from __future__ import annotations

from project_alpha.scoring.utils import NEUTRAL_SCORE, scale_linear


def smart_money_score(
    insider_net_buys_usd: float | None = None,
    short_interest_pct_float: float | None = None,
    institutional_ownership_change_pct: float | None = None,
) -> float:
    parts: list[float] = []

    if insider_net_buys_usd is not None:
        parts.append(scale_linear(insider_net_buys_usd, lo=-2_000_000, hi=2_000_000))

    if short_interest_pct_float is not None:
        # very high short interest is a risk flag, not a smart-money positive
        parts.append(scale_linear(-short_interest_pct_float, lo=-0.30, hi=-0.02))

    if institutional_ownership_change_pct is not None:
        parts.append(scale_linear(institutional_ownership_change_pct, lo=-0.10, hi=0.10))

    if not parts:
        return NEUTRAL_SCORE
    return round(sum(parts) / len(parts), 2)
