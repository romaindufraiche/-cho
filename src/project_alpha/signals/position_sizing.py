"""Position sizing (section 5): risque cible ~0.75-1.25% du portefeuille
modele, ajuste a la volatilite et aux correlations."""

from __future__ import annotations

RISK_PCT_LOW = 0.0075
RISK_PCT_HIGH = 0.0125


def target_risk_pct(volatility_score: float, correlation_penalty: float = 0.0) -> float:
    """`volatility_score` is the Risk module score (0-100, higher = lower
    risk): high-risk names get sized toward the low end of the band.
    `correlation_penalty` in [0, 1] further shrinks size for names that are
    highly correlated with existing book exposure."""
    vol_fraction = max(0.0, min(1.0, volatility_score / 100))
    base = RISK_PCT_LOW + vol_fraction * (RISK_PCT_HIGH - RISK_PCT_LOW)
    penalty = max(0.0, min(1.0, correlation_penalty))
    return round(base * (1 - 0.5 * penalty), 5)


def position_size(
    portfolio_value: float,
    entry_price: float,
    stop_price: float,
    volatility_score: float,
    correlation_penalty: float = 0.0,
) -> dict:
    risk_per_share = entry_price - stop_price
    if risk_per_share <= 0 or portfolio_value <= 0:
        return {"shares": 0.0, "risk_pct": 0.0, "risk_amount": 0.0}

    risk_pct = target_risk_pct(volatility_score, correlation_penalty)
    risk_amount = portfolio_value * risk_pct
    shares = risk_amount / risk_per_share

    # Never risk more capital on one line than the position sizing bounds imply.
    max_position_value = portfolio_value * 0.25
    shares = min(shares, max_position_value / entry_price)

    return {
        "shares": round(shares, 4),
        "risk_pct": risk_pct,
        "risk_amount": round(risk_amount, 2),
        "position_value": round(shares * entry_price, 2),
    }
