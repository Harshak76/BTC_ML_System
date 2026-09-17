"""
Unit tests for Risk Management & Decision Engine.
Verifies fixed-fractional position sizing math, daily loss lock, max DD shutdown, and trade entry checks.
"""

import pytest
from crypto_ml_trader.src.risk import RiskManager, DecisionEngine


def test_position_sizing_math():
    """Tests 0.5% risk per trade position sizing formula."""
    rm = RiskManager(config={"initial_capital": 10000.0, "risk_per_trade_pct": 0.005})
    # Equity = 10000. Risk = 50 USDT.
    # Entry = 20000, SL = 19000. Stop distance = 1000 USDT.
    # Expected units = 50 / 1000 = 0.05 BTC.
    res = rm.calculate_position_size(entry_price=20000.0, stop_loss_price=19000.0)

    assert pytest.approx(res["risk_usdt"], abs=1e-2) == 50.0
    assert pytest.approx(res["units"], abs=1e-4) == 0.05
    assert pytest.approx(res["position_value_usdt"], abs=1e-2) == 1000.0


def test_daily_loss_lock_trigger():
    """Tests 1.0% daily loss lock activation."""
    rm = RiskManager(config={"initial_capital": 10000.0, "max_daily_loss_pct": 0.010})
    rm.reset_daily_pnl(new_day_equity=10000.0)

    # Simulated loss of 150 USDT (1.5% > 1.0%)
    rm.update_equity(current_equity=9850.0, open_pnl=-150.0)
    assert rm.daily_loss_locked is True


def test_max_drawdown_shutdown_trigger():
    """Tests 10.0% max drawdown shutdown activation."""
    rm = RiskManager(config={"initial_capital": 10000.0, "max_drawdown_pct": 0.100})
    # High water mark = 10000. Equity drops to 8900 (11% DD > 10%)
    rm.update_equity(current_equity=8900.0)

    assert rm.max_dd_shutdown is True
    assert rm.manual_reset_required is True


def test_decision_engine_rejections():
    """Tests that decision engine rejects trades when risk limits or HTF rules are violated."""
    rm = RiskManager(config={"initial_capital": 10000.0})
    de = DecisionEngine(rm, config={"buy_probability_threshold": 0.55})

    # Test 1: Probability below threshold (0.50 < 0.55) -> HOLD
    res = de.evaluate(
        buy_probability=0.50,
        model_disagreement=0.05,
        htf_permits_long=True,
        entry_price=20000.0,
        stop_loss_price=19500.0,
        take_profit_price=21000.0,
        has_open_position=False
    )
    assert res["action"] == "HOLD"
    assert "below threshold" in res["reason"]

    # Test 2: HTF permits long is False -> HOLD
    res2 = de.evaluate(
        buy_probability=0.70,
        model_disagreement=0.05,
        htf_permits_long=False,
        entry_price=20000.0,
        stop_loss_price=19500.0,
        take_profit_price=21000.0,
        has_open_position=False
    )
    assert res2["action"] == "HOLD"
    assert "Higher Timeframe regime" in res2["reason"]

    # Test 3: All 10 rules passed -> BUY
    res3 = de.evaluate(
        buy_probability=0.65,
        model_disagreement=0.05,
        htf_permits_long=True,
        entry_price=20000.0,
        stop_loss_price=19500.0,
        take_profit_price=21000.0,
        has_open_position=False
    )
    assert res3["action"] == "BUY"
    assert res3["position_units"] > 0
