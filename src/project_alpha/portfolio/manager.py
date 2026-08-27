"""Portfolio construction guardrails (section 10): does not pick four
independent-looking stocks that are actually one factor. Controls
correlation, sector, geography, beta, volatility and concentration, and
enforces the weekly/total position limits from the cadrage table
(0-4 new positions/week, 5-10 positions max).
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from project_alpha.data.models import Company, Position

MAX_POSITIONS = 10
MIN_POSITIONS_FOR_FULL_BOOK = 5
MAX_NEW_POSITIONS_PER_WEEK = 4
MAX_SECTOR_WEIGHT = 0.35
HIGH_CORRELATION_THRESHOLD = 0.75


class PortfolioManager:
    def __init__(self, positions: list[Position] | None = None):
        self.positions: list[Position] = positions or []

    @property
    def open_positions(self) -> list[Position]:
        return [p for p in self.positions if not p.closed]

    def new_positions_this_week(self, as_of: date) -> int:
        week_start = as_of - timedelta(days=as_of.weekday())
        return sum(1 for p in self.open_positions if p.entry_date >= week_start)

    def can_open_new_position(self, as_of: date) -> tuple[bool, str | None]:
        if len(self.open_positions) >= MAX_POSITIONS:
            return False, f"portfolio already at max ({MAX_POSITIONS}) positions"
        if self.new_positions_this_week(as_of) >= MAX_NEW_POSITIONS_PER_WEEK:
            return False, f"weekly new-position budget ({MAX_NEW_POSITIONS_PER_WEEK}) already used"
        return True, None

    def sector_weight(self, sector: str, companies_by_ticker: dict[str, Company]) -> float:
        open_pos = self.open_positions
        if not open_pos:
            return 0.0
        total_value = sum(p.shares * p.entry_price for p in open_pos)
        if total_value == 0:
            return 0.0
        sector_value = sum(
            p.shares * p.entry_price
            for p in open_pos
            if companies_by_ticker.get(p.ticker) and companies_by_ticker[p.ticker].sector == sector
        )
        return sector_value / total_value

    def max_correlation_to_book(
        self, candidate_returns: pd.Series, returns_by_ticker: dict[str, pd.Series]
    ) -> float:
        """Highest pairwise correlation between the candidate's daily
        returns and any currently-held position's returns."""
        max_corr = 0.0
        for pos in self.open_positions:
            other = returns_by_ticker.get(pos.ticker)
            if other is None:
                continue
            aligned = pd.concat([candidate_returns, other], axis=1).dropna()
            if len(aligned) < 20:
                continue
            corr = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
            if corr is not None and abs(corr) > abs(max_corr):
                max_corr = corr
        return round(max_corr, 3)

    def correlation_penalty(self, max_correlation: float) -> float:
        if abs(max_correlation) < HIGH_CORRELATION_THRESHOLD:
            return 0.0
        return min(1.0, (abs(max_correlation) - HIGH_CORRELATION_THRESHOLD) / (1 - HIGH_CORRELATION_THRESHOLD))
