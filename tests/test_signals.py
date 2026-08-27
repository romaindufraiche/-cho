from datetime import date, timedelta

from project_alpha.data.models import (
    CompositeScore,
    ModuleScores,
    Position,
    PriceZone,
    Signal,
    Thesis,
)
from project_alpha.signals.engine import evaluate_new_candidate, evaluate_open_position


def _score(total_hint: float) -> CompositeScore:
    # weighted_total_score is recomputed from modules; pick modules whose
    # weighted sum lands near total_hint using equal-weight-ish inputs.
    modules = ModuleScores(
        catalyst=total_hint,
        fundamental=total_hint,
        expectations=total_hint,
        technical=total_hint,
        valuation=total_hint,
        market_regime=total_hint,
        smart_money=total_hint,
        risk=total_hint,
    )
    from project_alpha.scoring.composite import build_composite_score

    return build_composite_score("TEST", date.today(), modules)


def _zone(low: float, high: float, stop: float) -> PriceZone:
    return PriceZone(
        buy_zone_low=low,
        buy_zone_high=high,
        stop=stop,
        target_bear=high + 5,
        target_base=high + 10,
        target_bull=high + 20,
    )


def test_no_trade_when_score_below_watch_threshold():
    score = _score(40)
    zone = _zone(90, 100, 85)
    assert evaluate_new_candidate(score, current_price=95, zone=zone) == Signal.NO_TRADE


def test_watch_when_score_between_watch_and_buy_thresholds():
    score = _score(65)
    zone = _zone(90, 100, 85)
    assert evaluate_new_candidate(score, current_price=95, zone=zone) == Signal.WATCH


def test_buy_when_high_score_and_price_in_zone():
    score = _score(85)
    zone = _zone(90, 100, 85)
    assert evaluate_new_candidate(score, current_price=95, zone=zone) == Signal.BUY


def test_buy_on_dip_when_high_score_but_price_above_zone():
    score = _score(85)
    zone = _zone(90, 100, 85)
    assert evaluate_new_candidate(score, current_price=150, zone=zone) == Signal.BUY_ON_DIP


def _open_position(entry_price: float = 100.0, stop: float = 90.0, entry_date: date | None = None) -> Position:
    thesis = Thesis(
        ticker="TEST",
        reason="test",
        catalyst="test catalyst",
        horizon_weeks=8,
        expected_return_pct=0.2,
        invalidation_conditions="none",
    )
    return Position(
        ticker="TEST",
        entry_date=entry_date or date.today(),
        entry_price=entry_price,
        shares=10,
        stop=stop,
        risk_pct_target=0.01,
        thesis=thesis,
    )


def test_open_position_sells_on_stop_hit():
    position = _open_position(entry_price=100, stop=90)
    score = _score(80)
    signal, reason = evaluate_open_position(position, current_price=89, current_score=score, as_of=date.today())
    assert signal == Signal.SELL
    assert reason == "stop_hit"


def test_open_position_sells_on_thesis_invalidated():
    position = _open_position()
    score = _score(80)
    signal, reason = evaluate_open_position(
        position, current_price=105, current_score=score, as_of=date.today(), thesis_invalidated=True
    )
    assert signal == Signal.SELL
    assert reason == "thesis_invalidated"


def test_open_position_time_stop_when_flat_after_horizon():
    position = _open_position(entry_price=100, entry_date=date.today() - timedelta(weeks=9))
    score = _score(80)
    signal, reason = evaluate_open_position(position, current_price=99, current_score=score, as_of=date.today())
    assert signal == Signal.SELL
    assert reason == "time_stop"


def test_open_position_holds_when_thesis_intact():
    position = _open_position()
    score = _score(80)
    signal, reason = evaluate_open_position(position, current_price=110, current_score=score, as_of=date.today())
    assert signal == Signal.HOLD
    assert reason == "thesis_intact"
