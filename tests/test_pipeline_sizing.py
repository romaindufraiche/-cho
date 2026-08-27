from project_alpha.data.models import PriceZone, Signal
from project_alpha.pipeline import compute_recommended_position


def _zone() -> PriceZone:
    return PriceZone(
        buy_zone_low=145, buy_zone_high=153, stop=138,
        target_bear=160, target_base=180, target_bull=195,
    )


def test_no_sizing_for_non_entry_signal():
    assert compute_recommended_position(Signal.WATCH, 150, _zone(), 70, 500.0) is None


def test_no_sizing_without_price_zone():
    assert compute_recommended_position(Signal.BUY, 150, None, 70, 500.0) is None


def test_sizing_scales_with_small_capital():
    sizing = compute_recommended_position(Signal.BUY, 150, _zone(), 70, 500.0)
    assert sizing is not None
    assert sizing.position_value <= 500.0
    assert 0 < sizing.risk_pct <= 0.0125


def test_no_sizing_with_zero_capital():
    assert compute_recommended_position(Signal.BUY, 150, _zone(), 70, 0.0) is None


def test_sizing_still_meaningful_with_small_capital():
    # position_size sizes in fractional shares, so 500 EUR still produces a
    # usable (small) suggested position rather than rounding to nothing.
    sizing = compute_recommended_position(Signal.BUY, 150, _zone(), 70, 500.0)
    assert sizing.shares > 0
    assert sizing.position_value > 0
