"""Core data model, matching the entities listed in section 7 of the cahier
des charges: companies, prices, fundamentals, estimates, earnings, news,
events, themes, company_exposure, technical_features, valuation_features,
scores, signals, positions, portfolio, thesis, backtests, recommendations,
sources.

These are the local, zero-cost MVP equivalent of the target GCP/BigQuery
schema (section 7). Field names are kept close to the eventual BigQuery
column names so migration later is mostly a matter of swapping the storage
backend, not the model.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class Region(str, Enum):
    EUROPE = "europe"
    US = "us"


class Signal(str, Enum):
    BUY = "BUY"
    BUY_ON_DIP = "BUY_ON_DIP"
    WATCH = "WATCH"
    HOLD = "HOLD"
    REDUCE = "REDUCE"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"


class MarketRegime(str, Enum):
    RISK_ON = "risk_on"
    NEUTRAL = "neutral"
    RISK_OFF = "risk_off"


class SourceRef(BaseModel):
    """A single sourced fact, per the LLM/Research Agent rule (section 8):
    every important fact keeps its source, URL, date, retrieval timestamp
    and confidence level."""

    source: str
    url: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class Company(BaseModel):
    ticker: str
    name: str
    region: Region
    sector: str | None = None
    industry: str | None = None
    currency: str = "EUR"
    exchange: str | None = None
    beta: float | None = None


class PriceBar(BaseModel):
    ticker: str
    dt: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    provider: str = "yfinance"


class FundamentalSnapshot(BaseModel):
    ticker: str
    as_of: date
    revenue: float | None = None
    revenue_growth_yoy: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    free_cash_flow: float | None = None
    net_debt_to_ebitda: float | None = None
    roic: float | None = None
    guidance_direction: int | None = None  # -1 lowered, 0 unchanged, 1 raised
    provider: str = "unknown"


class EstimateRevision(BaseModel):
    ticker: str
    as_of: date
    eps_estimate_current: float | None = None
    eps_estimate_prior: float | None = None
    revenue_estimate_current: float | None = None
    revenue_estimate_prior: float | None = None
    eps_surprise_pct: float | None = None
    provider: str = "unknown"

    @property
    def eps_revision_pct(self) -> float | None:
        if self.eps_estimate_current is None or not self.eps_estimate_prior:
            return None
        return (self.eps_estimate_current - self.eps_estimate_prior) / abs(
            self.eps_estimate_prior
        )


class EarningsEvent(BaseModel):
    ticker: str
    report_date: date
    eps_actual: float | None = None
    eps_estimate: float | None = None
    revenue_actual: float | None = None
    revenue_estimate: float | None = None


class NewsItem(BaseModel):
    ticker: str | None = None
    headline: str
    summary: str | None = None
    source: SourceRef
    sentiment: float | None = Field(default=None, ge=-1.0, le=1.0)


class EventCategory(str, Enum):
    EARNINGS = "earnings"
    GUIDANCE = "guidance"
    CONTRACT = "contract"
    CAPEX = "capex"
    MNA = "mna"
    REGULATION = "regulation"
    MACRO = "macro"
    GEOPOLITICAL = "geopolitical"
    SUPPLY_SHOCK = "supply_shock"
    SECTOR_DISRUPTION = "sector_disruption"


class Event(BaseModel):
    """A detected market-moving event; the entry point of the
    Event -> Theme -> Company engine (section 3)."""

    id: str
    category: EventCategory
    headline: str
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    theme: str | None = None
    already_priced: bool | None = None
    sources: list[SourceRef] = Field(default_factory=list)


class CompanyExposure(BaseModel):
    """Maps a theme/event to the companies exposed to it, with a
    conviction weight (theme graph, section 3)."""

    event_id: str
    ticker: str
    exposure_weight: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None


class TechnicalFeatures(BaseModel):
    ticker: str
    as_of: date
    close: float
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None
    rsi_14: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    atr_14: float | None = None
    volume_zscore: float | None = None
    support: float | None = None
    resistance: float | None = None
    trend_score: float | None = None


class ValuationFeatures(BaseModel):
    ticker: str
    as_of: date
    pe_ratio: float | None = None
    ev_ebitda: float | None = None
    price_to_fcf: float | None = None
    pe_vs_5y_avg: float | None = None
    peer_percentile: float | None = None
    dcf_fair_value: float | None = None


class ModuleScores(BaseModel):
    """The eight weighted modules from section 4."""

    catalyst: float = Field(ge=0, le=100)
    fundamental: float = Field(ge=0, le=100)
    expectations: float = Field(ge=0, le=100)
    technical: float = Field(ge=0, le=100)
    valuation: float = Field(ge=0, le=100)
    market_regime: float = Field(ge=0, le=100)
    smart_money: float = Field(ge=0, le=100)
    risk: float = Field(ge=0, le=100)  # higher = lower risk


class CompositeScore(BaseModel):
    ticker: str
    as_of: date
    modules: ModuleScores
    quality_score: float
    opportunity_score: float
    price_score: float
    weighted_total_score: float
    data_version: str
    scoring_version: str


class PriceZone(BaseModel):
    buy_zone_low: float
    buy_zone_high: float
    stop: float
    target_bear: float
    target_base: float
    target_bull: float
    horizon_weeks_low: int = 2
    horizon_weeks_high: int = 16


class PositionSizing(BaseModel):
    shares: float
    risk_pct: float
    risk_amount: float
    position_value: float


class Recommendation(BaseModel):
    ticker: str
    as_of: datetime = Field(default_factory=datetime.utcnow)
    signal: Signal
    score: CompositeScore
    price_zone: PriceZone | None = None
    current_price: float | None = None
    position_sizing: PositionSizing | None = None
    thesis_summary: str | None = None
    why_now: str | None = None
    invalidation: str | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    data_version: str
    scoring_version: str
    model_version: str
    prompt_version: str


class ThesisReview(BaseModel):
    reviewed_at: datetime = Field(default_factory=datetime.utcnow)
    still_valid: bool
    note: str | None = None
    score_at_review: float | None = None


class Thesis(BaseModel):
    ticker: str
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    reason: str
    catalyst: str
    horizon_weeks: int
    expected_return_pct: float
    invalidation_conditions: str
    reviews: list[ThesisReview] = Field(default_factory=list)
    closed_at: datetime | None = None
    close_reason: str | None = None

    @property
    def is_open(self) -> bool:
        return self.closed_at is None


class Position(BaseModel):
    ticker: str
    entry_date: date
    entry_price: float
    shares: float
    stop: float
    risk_pct_target: float = Field(ge=0.0075, le=0.0125)
    thesis: Thesis
    closed: bool = False
    exit_date: date | None = None
    exit_price: float | None = None
    exit_reason: str | None = None


class BacktestMetrics(BaseModel):
    start: date
    end: date
    cagr: float
    alpha_vs_benchmark: float | None = None
    win_rate: float
    avg_win_pct: float
    avg_loss_pct: float
    expectancy: float
    profit_factor: float
    max_drawdown: float
    volatility: float
    sharpe: float
    sortino: float
    n_trades: int
    benchmark: str | None = None
