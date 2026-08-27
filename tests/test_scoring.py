from datetime import date

from project_alpha.data.models import (
    EstimateRevision,
    FundamentalSnapshot,
    ModuleScores,
    ValuationFeatures,
)
from project_alpha.scoring.composite import (
    WEIGHTS,
    build_composite_score,
    opportunity_score,
    price_score,
    quality_score,
    weighted_total_score,
)
from project_alpha.scoring.expectations import expectations_score
from project_alpha.scoring.fundamental import fundamental_score
from project_alpha.scoring.utils import NEUTRAL_SCORE
from project_alpha.scoring.valuation import valuation_score


def test_weights_sum_to_100():
    assert sum(WEIGHTS.values()) == 100


def test_fundamental_score_neutral_when_no_data():
    assert fundamental_score(None) == NEUTRAL_SCORE


def test_fundamental_score_rewards_strong_growth_and_margins():
    strong = FundamentalSnapshot(
        ticker="TEST",
        as_of=date.today(),
        revenue_growth_yoy=0.25,
        gross_margin=0.6,
        operating_margin=0.25,
        free_cash_flow=1_000_000,
        net_debt_to_ebitda=-0.5,
        roic=0.20,
        guidance_direction=1,
    )
    weak = FundamentalSnapshot(
        ticker="TEST",
        as_of=date.today(),
        revenue_growth_yoy=-0.08,
        gross_margin=0.15,
        operating_margin=-0.02,
        free_cash_flow=-500_000,
        net_debt_to_ebitda=4.5,
        roic=0.01,
        guidance_direction=-1,
    )
    assert fundamental_score(strong) > fundamental_score(weak)


def test_expectations_score_rewards_positive_surprise_and_revisions():
    positive = EstimateRevision(
        ticker="TEST",
        as_of=date.today(),
        eps_estimate_current=1.10,
        eps_estimate_prior=1.00,
        eps_surprise_pct=0.08,
    )
    negative = EstimateRevision(
        ticker="TEST",
        as_of=date.today(),
        eps_estimate_current=0.90,
        eps_estimate_prior=1.00,
        eps_surprise_pct=-0.08,
    )
    assert expectations_score(positive) > expectations_score(negative)


def test_valuation_score_rewards_cheaper_multiples():
    cheap = ValuationFeatures(ticker="TEST", as_of=date.today(), pe_ratio=10.0)
    expensive = ValuationFeatures(ticker="TEST", as_of=date.today(), pe_ratio=38.0)
    assert valuation_score(cheap) > valuation_score(expensive)


def test_weighted_total_score_matches_manual_computation():
    modules = ModuleScores(
        catalyst=80,
        fundamental=70,
        expectations=60,
        technical=65,
        valuation=55,
        market_regime=50,
        smart_money=50,
        risk=90,
    )
    expected = (
        80 * 20 + 70 * 15 + 60 * 15 + 65 * 15 + 55 * 15 + 50 * 5 + 50 * 5 + 90 * 10
    ) / 100
    assert weighted_total_score(modules) == round(expected, 2)


def test_quality_opportunity_price_do_not_confuse_dimensions():
    great_company_bad_timing = ModuleScores(
        catalyst=10,
        fundamental=95,
        expectations=20,
        technical=30,
        valuation=15,  # very expensive
        market_regime=50,
        smart_money=80,
        risk=90,
    )
    q = quality_score(great_company_bad_timing)
    o = opportunity_score(great_company_bad_timing)
    p = price_score(great_company_bad_timing)
    assert q > 80  # excellent company
    assert o < 40  # but not a live opportunity right now
    assert p < 40  # and not attractively priced


def test_build_composite_score_is_consistent():
    modules = ModuleScores(
        catalyst=80,
        fundamental=70,
        expectations=60,
        technical=65,
        valuation=55,
        market_regime=50,
        smart_money=50,
        risk=90,
    )
    composite = build_composite_score("TEST", date.today(), modules)
    assert composite.weighted_total_score == weighted_total_score(modules)
    assert composite.quality_score == quality_score(modules)
