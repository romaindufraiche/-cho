"""Market Regime module (weight 5): risk-on / neutral / risk-off.

Kept intentionally simple: a small set of macro/technical breadth signals
map to a regime, which both scores individual candidates (risk-on rewards
higher-beta/momentum names) and drives the newsletter's headline regime
(section 11)."""

from __future__ import annotations

from project_alpha.data.models import MarketRegime


def classify_regime(
    benchmark_above_200sma: bool | None,
    vix_level: float | None,
    credit_spread_widening: bool | None,
) -> MarketRegime:
    signals = [benchmark_above_200sma, vix_level, credit_spread_widening]
    if all(s is None for s in signals):
        return MarketRegime.NEUTRAL

    risk_off_votes = 0
    risk_on_votes = 0
    total_votes = 0

    if benchmark_above_200sma is not None:
        total_votes += 1
        risk_on_votes += int(benchmark_above_200sma)
        risk_off_votes += int(not benchmark_above_200sma)

    if vix_level is not None:
        total_votes += 1
        if vix_level >= 25:
            risk_off_votes += 1
        elif vix_level <= 16:
            risk_on_votes += 1

    if credit_spread_widening is not None:
        total_votes += 1
        risk_off_votes += int(credit_spread_widening)
        risk_on_votes += int(not credit_spread_widening)

    if total_votes == 0:
        return MarketRegime.NEUTRAL
    if risk_off_votes / total_votes >= 0.6:
        return MarketRegime.RISK_OFF
    if risk_on_votes / total_votes >= 0.6:
        return MarketRegime.RISK_ON
    return MarketRegime.NEUTRAL


def market_regime_score(regime: MarketRegime, beta: float | None = None) -> float:
    """Higher-beta names score better in risk-on and worse in risk-off;
    defensive (low-beta) names get the opposite tilt."""
    base = {MarketRegime.RISK_ON: 75.0, MarketRegime.NEUTRAL: 50.0, MarketRegime.RISK_OFF: 25.0}[
        regime
    ]
    if beta is None:
        return base

    tilt = (beta - 1.0) * 15.0
    if regime == MarketRegime.RISK_OFF:
        tilt *= -1
    elif regime == MarketRegime.NEUTRAL:
        tilt = 0.0

    return round(min(100.0, max(0.0, base + tilt)), 2)
