"""Risk module (weight 10): volatilite, dette, evenement, macro,
geopolitique, concentration.

By convention (matching ModuleScores.risk in the data model) a HIGHER score
means LOWER risk, so it combines additively with the other "higher is
better" modules in the weighted total."""

from __future__ import annotations

from project_alpha.scoring.utils import NEUTRAL_SCORE, scale_linear


def risk_score(
    annualized_volatility: float | None = None,
    net_debt_to_ebitda: float | None = None,
    pending_binary_event: bool | None = None,
    portfolio_correlation: float | None = None,
) -> float:
    parts: list[float] = []

    if annualized_volatility is not None:
        # lower volatility -> less risk -> higher score
        parts.append(scale_linear(-annualized_volatility, lo=-0.80, hi=-0.15))

    if net_debt_to_ebitda is not None:
        parts.append(scale_linear(-net_debt_to_ebitda, lo=-6.0, hi=1.0))

    if pending_binary_event is not None:
        parts.append(30.0 if pending_binary_event else 70.0)

    if portfolio_correlation is not None:
        # high correlation to existing book concentrates risk
        parts.append(scale_linear(-abs(portfolio_correlation), lo=-1.0, hi=-0.2))

    if not parts:
        return NEUTRAL_SCORE
    return round(sum(parts) / len(parts), 2)
