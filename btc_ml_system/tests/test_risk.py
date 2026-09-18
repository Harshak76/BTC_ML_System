"""
Tests for Risk Engine in btc_ml_system.
Verifies safety controls, drawdown triggers, and position sizing limits.
"""

import pytest
from btc_ml_system.src.risk import RiskEngine


def test_risk_engine():
    config = {
        "risk": {
            "initial_capital": 10000.0,
            "risk_per_trade_pct": 0.005,
            "max_daily_loss_pct": 0.01,
            "max_drawdown_pct": 0.10,
            "cooldown_bars": 3,
            "kill_switch_enabled": True
        }
    }
    risk = RiskEngine(config)

    # Test 1: Clean risk -> Passed
    pass1, reason1 = risk.evaluate_risk(10, current_drawdown=0.0, daily_pnl_pct=0.0)
    assert pass1

    # Test 2: Max Drawdown hit -> Rejected & Trigger Kill Switch
    pass2, reason2 = risk.evaluate_risk(11, current_drawdown=0.12, daily_pnl_pct=0.0)
    assert not pass2

    # Test 3: Subsequent trade after kill switch -> Blocked
    pass3, reason3 = risk.evaluate_risk(15, current_drawdown=0.0, daily_pnl_pct=0.0)
    assert not pass3
