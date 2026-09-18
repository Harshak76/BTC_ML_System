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
            "volatility_targeting": True,
            "target_annual_vol": 0.15,
            "cooldown_bars": 3
        },
        "models": {
            "disagreement_threshold": 0.20
        }
    }
    risk = RiskEngine(config)
    regime_params = {"buy_prob_threshold": 0.55, "position_size_multiplier": 1.0}

    # Test 1: Low probability should be rejected
    dec1 = risk.evaluate_trade(10, buy_prob=0.50, disagreement=0.05, regime_params=regime_params, current_volatility=0.01, current_drawdown=0.0, daily_pnl_pct=0.0)
    assert not dec1.allow_trade

    # Test 2: High probability + clean risk -> Approved
    dec2 = risk.evaluate_trade(15, buy_prob=0.60, disagreement=0.05, regime_params=regime_params, current_volatility=0.01, current_drawdown=0.0, daily_pnl_pct=0.0)
    assert dec2.allow_trade
    assert dec2.position_size > 0.0

    # Test 3: Max Drawdown hit -> Rejected
    dec3 = risk.evaluate_trade(20, buy_prob=0.70, disagreement=0.05, regime_params=regime_params, current_volatility=0.01, current_drawdown=0.12, daily_pnl_pct=0.0)
    assert not dec3.allow_trade
