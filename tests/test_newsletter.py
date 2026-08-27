from datetime import date

from project_alpha.data.models import (
    CompositeScore,
    MarketRegime,
    ModuleScores,
    PriceZone,
    Recommendation,
    Signal,
)
from project_alpha.reporting.newsletter import render_newsletter


def _recommendation(ticker: str, signal: Signal) -> Recommendation:
    modules = ModuleScores(
        catalyst=80, fundamental=70, expectations=60, technical=65,
        valuation=55, market_regime=50, smart_money=50, risk=90,
    )
    score = CompositeScore(
        ticker=ticker,
        as_of=date.today(),
        modules=modules,
        quality_score=84,
        opportunity_score=91,
        price_score=82,
        weighted_total_score=76.5,
        data_version="v0.1",
        scoring_version="v0.1",
    )
    zone = PriceZone(
        buy_zone_low=145, buy_zone_high=153, stop=138,
        target_bear=160, target_base=180, target_bull=195,
    )
    return Recommendation(
        ticker=ticker,
        signal=signal,
        score=score,
        price_zone=zone,
        current_price=152,
        data_version="v0.1",
        scoring_version="v0.1",
        model_version="v0.1",
        prompt_version="v0.1",
    )


def test_newsletter_contains_regime_and_opportunity():
    rec = _recommendation("SIEMENS_ENERGY", Signal.BUY)
    text = render_newsletter(
        as_of=date.today(),
        regime=MarketRegime.RISK_ON,
        top_opportunities=[rec],
        traps=[],
        not_yet_buyable=[],
        positions_to_manage=[],
        track_record=None,
    )
    assert "RISK-ON" in text
    assert "SIEMENS_ENERGY" in text
    assert "NO TRADE" not in text.split("Top Opportunities")[1].split("piege")[0]


def test_newsletter_no_trade_message_when_no_opportunities():
    text = render_newsletter(
        as_of=date.today(),
        regime=MarketRegime.NEUTRAL,
        top_opportunities=[],
        traps=[],
        not_yet_buyable=[],
        positions_to_manage=[],
        track_record=None,
    )
    assert "NO TRADE" in text
