from project_alpha.signals.position_sizing import (
    RISK_PCT_HIGH,
    RISK_PCT_LOW,
    position_size,
    target_risk_pct,
)


def test_target_risk_pct_stays_within_band():
    assert RISK_PCT_LOW <= target_risk_pct(0) <= RISK_PCT_HIGH
    assert RISK_PCT_LOW <= target_risk_pct(100) <= RISK_PCT_HIGH


def test_target_risk_pct_lower_for_riskier_names():
    high_risk = target_risk_pct(volatility_score=10)  # low risk-module score = risky name
    low_risk = target_risk_pct(volatility_score=90)
    assert high_risk < low_risk


def test_correlation_penalty_shrinks_position():
    base = target_risk_pct(volatility_score=90, correlation_penalty=0.0)
    penalized = target_risk_pct(volatility_score=90, correlation_penalty=1.0)
    assert penalized < base


def test_position_size_respects_risk_budget():
    result = position_size(
        portfolio_value=100_000,
        entry_price=150,
        stop_price=138,
        volatility_score=70,
    )
    risk_per_share = 150 - 138
    implied_risk = result["shares"] * risk_per_share
    assert abs(implied_risk - result["risk_amount"]) < 0.01
    assert result["risk_pct"] >= 0


def test_position_size_zero_when_stop_above_entry():
    result = position_size(
        portfolio_value=100_000, entry_price=100, stop_price=105, volatility_score=70
    )
    assert result["shares"] == 0.0
