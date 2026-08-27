from datetime import date, timedelta

from project_alpha.data.models import Position, Thesis
from project_alpha.portfolio.manager import (
    MAX_NEW_POSITIONS_PER_WEEK,
    MAX_POSITIONS,
    PortfolioManager,
)


def _position(ticker: str, entry_date: date) -> Position:
    thesis = Thesis(
        ticker=ticker,
        reason="test",
        catalyst="test",
        horizon_weeks=8,
        expected_return_pct=0.15,
        invalidation_conditions="none",
    )
    return Position(
        ticker=ticker,
        entry_date=entry_date,
        entry_price=100,
        shares=10,
        stop=90,
        risk_pct_target=0.01,
        thesis=thesis,
    )


def test_can_open_new_position_when_book_is_empty():
    manager = PortfolioManager([])
    allowed, reason = manager.can_open_new_position(date.today())
    assert allowed
    assert reason is None


def test_blocks_new_position_at_max_book_size():
    positions = [_position(f"T{i}", date.today() - timedelta(days=30)) for i in range(MAX_POSITIONS)]
    manager = PortfolioManager(positions)
    allowed, reason = manager.can_open_new_position(date.today())
    assert not allowed
    assert "max" in reason


def test_blocks_new_position_over_weekly_budget():
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    positions = [
        _position(f"T{i}", week_start + timedelta(days=1))
        for i in range(MAX_NEW_POSITIONS_PER_WEEK)
    ]
    manager = PortfolioManager(positions)
    allowed, reason = manager.can_open_new_position(today)
    assert not allowed
    assert "weekly" in reason


def test_correlation_penalty_zero_below_threshold():
    manager = PortfolioManager([])
    assert manager.correlation_penalty(0.5) == 0.0


def test_correlation_penalty_scales_above_threshold():
    manager = PortfolioManager([])
    penalty = manager.correlation_penalty(0.9)
    assert 0.0 < penalty <= 1.0
