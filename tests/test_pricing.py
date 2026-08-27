from datetime import date

from project_alpha.data.models import TechnicalFeatures
from project_alpha.signals.pricing import compute_price_zone, reward_risk_ratio


def _features(close=100.0, support=92.0, resistance=115.0, atr_14=2.0) -> TechnicalFeatures:
    return TechnicalFeatures(
        ticker="TEST",
        as_of=date.today(),
        close=close,
        support=support,
        resistance=resistance,
        atr_14=atr_14,
    )


def test_buy_zone_is_below_or_at_current_price():
    zone = compute_price_zone(100.0, _features())
    assert zone.buy_zone_low <= zone.buy_zone_high <= 100.0


def test_stop_is_below_support():
    features = _features()
    zone = compute_price_zone(100.0, features)
    assert zone.stop < features.support


def test_targets_are_ordered_bear_base_bull():
    zone = compute_price_zone(100.0, _features())
    assert zone.target_bear <= zone.target_base <= zone.target_bull


def test_reward_risk_ratio_positive_for_healthy_setup():
    zone = compute_price_zone(100.0, _features())
    rr = reward_risk_ratio(100.0, zone)
    assert rr is not None and rr > 0


def test_reward_risk_ratio_none_when_price_already_below_stop():
    zone = compute_price_zone(100.0, _features())
    rr = reward_risk_ratio(zone.stop - 1, zone)
    assert rr is None
