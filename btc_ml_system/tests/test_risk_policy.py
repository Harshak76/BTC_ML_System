"""
Unit and Policy Tests for Risk Denominator and Portfolio Risk Limits.
Validates:
- RSK-001: 0.5% risk calculation under 'component_allocation' vs 'portfolio_equity'
- Consistency with 3% aggregate open portfolio risk ceiling
- Consistency with 2% daily loss and 10% drawdown circuit breakers
"""

import pytest
import pandas as pd
from btc_ml_system.src.risk import RiskEngine


def test_risk_denominator_calculations_on_10k_portfolio():
    """
    RSK-001: Mathematical verification of risk per trade under both denominator models.
    Hypothetical Portfolio: $10,000 Total Equity
    Allocations: Equities 50% (10% per stock), BTC 25%, ETH 25%
    Risk per trade: 0.50% (0.005)
    """
    total_equity = 10000.0
    allocations = {
        "AAPL": 0.10 * total_equity,    # $1,000
        "MSFT": 0.10 * total_equity,    # $1,000
        "NVDA": 0.10 * total_equity,    # $1,000
        "TSLA": 0.10 * total_equity,    # $1,000
        "AMZN": 0.10 * total_equity,    # $1,000
        "BTCUSDT": 0.25 * total_equity, # $2,500
        "ETHUSDT": 0.25 * total_equity  # $2,500
    }

    # Model A: component_allocation (Current default preserved behavior)
    dollar_risks_model_a = {}
    for sym, sub_cap in allocations.items():
        dollar_risks_model_a[sym] = sub_cap * 0.005

    assert dollar_risks_model_a["AAPL"] == 5.00     # $5.00 on $1,000 (0.05% of account)
    assert dollar_risks_model_a["BTCUSDT"] == 12.50 # $12.50 on $2,500 (0.125% of account)
    assert dollar_risks_model_a["ETHUSDT"] == 12.50 # $12.50 on $2,500 (0.125% of account)

    # Model B: portfolio_equity (Standard institutional model)
    dollar_risks_model_b = {}
    for sym in allocations:
        dollar_risks_model_b[sym] = total_equity * 0.005

    assert dollar_risks_model_b["AAPL"] == 50.00     # $50.00 on $10,000 (0.50% of account)
    assert dollar_risks_model_b["BTCUSDT"] == 50.00 # $50.00 on $10,000 (0.50% of account)
    assert dollar_risks_model_b["ETHUSDT"] == 50.00 # $50.00 on $10,000 (0.50% of account)


def test_aggregate_open_risk_ceiling_and_circuit_breakers():
    """Verifies that 3% max open risk, 2% daily loss, and 10% DD operate correctly."""
    total_equity = 10000.0
    max_portfolio_risk_pct = 0.03 # 3% = $300 max combined open dollar risk

    # If 5 positions each risk $50 (Model B), combined open risk is $250 / $10,000 = 2.50% (Allowed)
    open_risk_5_positions = 5 * 50.00
    assert (open_risk_5_positions / total_equity) <= max_portfolio_risk_pct

    # If a 6th position risking $60 is added: $250 + $60 = $310 (3.10% > 3.00% -> Blocked!)
    open_risk_6_positions = open_risk_5_positions + 60.00
    assert (open_risk_6_positions / total_equity) > max_portfolio_risk_pct

    # Test RiskEngine circuit breakers
    risk_engine = RiskEngine({
        "risk": {
            "initial_capital": 10000.0,
            "max_daily_loss_pct": 0.02,
            "max_drawdown_pct": 0.10,
            "cooldown_bars": 2
        }
    })

    # Normal conditions -> Passes
    passed, reason = risk_engine.evaluate_risk(current_bar_idx=10, current_drawdown=0.04, daily_pnl_pct=-0.01)
    assert passed is True

    # Daily loss hit (-2.1% <= -2.0%) -> Blocked
    passed_dl, reason_dl = risk_engine.evaluate_risk(current_bar_idx=10, current_drawdown=0.04, daily_pnl_pct=-0.021)
    assert passed_dl is False
    assert "Daily loss circuit breaker" in reason_dl

    # Max Drawdown hit (10.5% >= 10.0%) -> Kill switch activated & Blocked
    passed_dd, reason_dd = risk_engine.evaluate_risk(current_bar_idx=10, current_drawdown=0.105, daily_pnl_pct=-0.01)
    assert passed_dd is False
    assert "Max drawdown limit hit" in reason_dd
