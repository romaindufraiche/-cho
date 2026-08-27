"""Signal engine (section 1, 5, 15): turns scores + price into one of
BUY / BUY_ON_DIP / WATCH / HOLD / REDUCE / SELL / NO_TRADE.

Non-negotiable principle from section 15: "No BUY obligatoire. Le systeme
peut recommander CASH / NO TRADE." NO_TRADE is always the default when
nothing clears the bar - it is never an error state.
"""

from __future__ import annotations

from datetime import date, timedelta

from project_alpha.data.models import CompositeScore, Position, PriceZone, Signal

# Thresholds on weighted_total_score (0-100). Tunable via backtest (V2).
BUY_THRESHOLD = 75.0
WATCH_THRESHOLD = 60.0
SELL_THRESHOLD = 35.0

TIME_STOP_WEEKS = 8


def evaluate_new_candidate(
    score: CompositeScore, current_price: float, zone: PriceZone
) -> Signal:
    total = score.weighted_total_score

    if total < WATCH_THRESHOLD:
        return Signal.NO_TRADE

    in_or_near_zone = zone.buy_zone_low * 0.98 <= current_price <= zone.buy_zone_high
    too_expensive = current_price > zone.buy_zone_high

    if total >= BUY_THRESHOLD:
        if in_or_near_zone:
            return Signal.BUY
        if too_expensive:
            # Good company, good opportunity, bad price right now: wait for
            # a pullback into the buy zone rather than chase (section 11:
            # "Pas encore achetable").
            return Signal.BUY_ON_DIP
        return Signal.WATCH

    return Signal.WATCH


def evaluate_open_position(
    position: Position,
    current_price: float,
    current_score: CompositeScore,
    as_of: date,
    thesis_invalidated: bool = False,
    guidance_broken: bool = False,
    materially_better_opportunity: bool = False,
) -> tuple[Signal, str]:
    """Exit rules from section 5: stop, these invalidee, guidance cassee,
    objectif atteint, time-stop 6-8 semaines, opportunite nettement
    superieure. Returns (signal, reason)."""

    if current_price <= position.stop:
        return Signal.SELL, "stop_hit"

    if thesis_invalidated:
        return Signal.SELL, "thesis_invalidated"

    if guidance_broken:
        return Signal.SELL, "guidance_broken"

    if materially_better_opportunity:
        return Signal.SELL, "better_opportunity_elsewhere"

    weeks_held = (as_of - position.entry_date).days / 7
    if weeks_held >= TIME_STOP_WEEKS and current_price <= position.entry_price:
        return Signal.SELL, "time_stop"

    if current_score.weighted_total_score < SELL_THRESHOLD:
        return Signal.REDUCE, "score_deteriorated"

    if current_score.weighted_total_score < WATCH_THRESHOLD:
        return Signal.REDUCE, "score_weakening"

    return Signal.HOLD, "thesis_intact"


def target_reached(current_price: float, zone: PriceZone) -> bool:
    return current_price >= zone.target_base
