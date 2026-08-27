"""Buy zone / stop / targets (section 5).

- Buy zone: computed from valuation, supports, ATR, volatility and momentum.
  Here (MVP, technicals only until valuation/DCF is fully wired) it centers
  on the nearest support with an ATR-scaled band.
- Stop: technical structure and volatility, never a fixed percentage.
- Targets: bear/base/bull scenarios with probabilised expected return.
"""

from __future__ import annotations

from project_alpha.data.models import PriceZone, TechnicalFeatures

_STOP_ATR_MULT = 1.5
_ZONE_ATR_MULT = 0.75


def compute_price_zone(
    current_price: float,
    features: TechnicalFeatures,
    dcf_fair_value: float | None = None,
) -> PriceZone:
    atr = features.atr_14 or (current_price * 0.02)
    support = features.support or (current_price - 2 * atr)
    resistance = features.resistance or (current_price + 2 * atr)

    # Buy zone centers on the stronger of (support, current price pulled back
    # by less than one ATR), bounded so it never sits above the current price.
    zone_center = min(current_price, max(support, current_price - atr))
    buy_zone_low = round(zone_center - _ZONE_ATR_MULT * atr, 2)
    buy_zone_high = round(min(current_price, zone_center + _ZONE_ATR_MULT * atr), 2)
    if buy_zone_high < buy_zone_low:
        buy_zone_low, buy_zone_high = buy_zone_high, buy_zone_low

    stop = round(max(0.01, support - _STOP_ATR_MULT * atr), 2)

    # Base target: structural resistance, blended with DCF fair value when
    # available. Bear/bull are symmetric-ish scenarios around it, scaled by
    # the stop distance (risk) so reward/risk stays coherent per name.
    risk_per_share = max(0.01, current_price - stop)
    base_target = resistance if resistance > current_price else current_price + 2 * risk_per_share
    if dcf_fair_value:
        base_target = (base_target + dcf_fair_value) / 2

    target_base = round(base_target, 2)
    target_bear = round(current_price + 0.4 * (target_base - current_price), 2)
    target_bull = round(current_price + 1.6 * (target_base - current_price), 2)

    return PriceZone(
        buy_zone_low=buy_zone_low,
        buy_zone_high=buy_zone_high,
        stop=stop,
        target_bear=target_bear,
        target_base=target_base,
        target_bull=target_bull,
    )


def reward_risk_ratio(current_price: float, zone: PriceZone) -> float | None:
    risk = current_price - zone.stop
    if risk <= 0:
        return None
    reward = zone.target_base - current_price
    return round(reward / risk, 2)
