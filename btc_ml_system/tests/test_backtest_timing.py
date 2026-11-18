"""
Tests for BKT-001 and BKT-002: Backtest Execution Timing and Gap Slippage.
Validates:
- BKT-001: Next-bar open execution vs same-bar close execution
- BKT-002: Opening gap slippage handling (exit at open when open < sl_price)
"""

import pandas as pd
import numpy as np
import pytest
from btc_ml_system.src.portfolio_manager import PortfolioManager


def create_mock_backtest_data():
    """Creates synthetic price data with explicit signal at bar 1."""
    # 5 bars:
    # Bar 0: Flat baseline
    # Bar 1: Signal bar (close = 100, direction_valid=True)
    # Bar 2: Next bar opens at 105 (gap up on entry), high 110, low 102, close 108
    # Bar 3: Gap down on exit: open at 85 (below initial SL 95), low 80, close 82
    # Bar 4: Flat baseline
    dates = pd.date_range("2026-01-01 00:00:00", periods=5, freq="1h", tz="UTC")
    df = pd.DataFrame({
        "open_time": dates,
        "close_time": dates + pd.Timedelta(hours=1),
        "open":  [100.0, 100.0, 105.0, 85.0, 80.0],
        "high":  [101.0, 102.0, 110.0, 90.0, 85.0],
        "low":   [99.0,   98.0, 102.0, 80.0, 78.0],
        "close": [100.0, 100.0, 108.0, 82.0, 80.0],
        "volume": [1000.0] * 5,
        "direction_valid": [False, True, False, False, False],
        "htf_trend_valid": [True, True, True, True, True],
        "session_valid": [True, True, True, True, True],
        "vol_regime_favorable": [True, True, True, True, True],
        "atr": [5.0] * 5,
        "volatility_regime": ["NORMAL"] * 5
    })
    return df


def test_next_bar_open_execution_timing():
    """BKT-001: Next-bar open timing must fill at bar t+1 open rather than bar t close."""
    port_cfg = {
        "portfolio": {
            "initial_capital": 10000.0,
            "max_open_risk_pct": 0.05,
            "per_trade_risk_pct": 0.01,
            "risk_denominator": "component_allocation",
            "execution_timing": "next_bar_open",
            "max_drawdown_limit_pct": 0.10,
            "max_daily_loss_pct": 0.02
        },
        "allocation": {
            "TEST_ASSET": 1.0
        }
    }

    pm = PortfolioManager(port_cfg)
    assert pm.execution_timing == "next_bar_open"

    df = create_mock_backtest_data()
    asset_configs = {
        "TEST_ASSET": {
            "prepared_df": df,
            "sl_atr_mult": 1.0,
            "tp_atr_mult": 4.0,
            "position_sizer": {
                "risk_pct": 0.01
            },
            "volatility_regime": {
                "allowed_regimes": ["NORMAL"]
            },
            "exit_rules": {
                "enable_trailing_stop": False
            },
            "execution": {
                "slippage_bps": 0,
                "commission_bps": 0
            }
        }
    }

    metrics = pm.run_portfolio_backtest(asset_configs)

    trades = metrics["trades"]
    assert len(trades) == 1, f"Should have executed exactly 1 trade, got {len(trades)}"
    trade = trades[0]

    # Signal was generated at bar 1 (2026-01-01 01:00 UTC)
    # Under next_bar_open, entry should be at bar 2 (2026-01-01 02:00 UTC) at open price 105.0
    expected_entry_time = pd.Timestamp("2026-01-01 02:00:00", tz="UTC")
    assert pd.Timestamp(trade["entry_time"]) == expected_entry_time
    assert np.isclose(trade["entry_price"], 105.0)


def test_same_bar_close_execution_timing():
    """BKT-001: Same-bar close legacy timing must fill at bar t close."""
    port_cfg = {
        "portfolio": {
            "initial_capital": 10000.0,
            "max_open_risk_pct": 0.05,
            "per_trade_risk_pct": 0.01,
            "risk_denominator": "component_allocation",
            "execution_timing": "same_bar_close",
            "max_drawdown_limit_pct": 0.10,
            "max_daily_loss_pct": 0.02
        },
        "allocation": {
            "TEST_ASSET": 1.0
        }
    }

    pm = PortfolioManager(port_cfg)
    assert pm.execution_timing == "same_bar_close"

    df = create_mock_backtest_data()
    asset_configs = {
        "TEST_ASSET": {
            "prepared_df": df,
            "sl_atr_mult": 1.0,
            "tp_atr_mult": 4.0,
            "position_sizer": {
                "risk_pct": 0.01
            },
            "volatility_regime": {
                "allowed_regimes": ["NORMAL"]
            },
            "exit_rules": {
                "enable_trailing_stop": False
            },
            "execution": {
                "slippage_bps": 0,
                "commission_bps": 0
            }
        }
    }

    metrics = pm.run_portfolio_backtest(asset_configs)

    trades = metrics["trades"]
    assert len(trades) == 1
    trade = trades[0]

    # Signal generated at bar 1 (2026-01-01 01:00 UTC)
    # Under same_bar_close, entry is at bar 1 close price 100.0
    expected_entry_time = pd.Timestamp("2026-01-01 01:00:00", tz="UTC")
    assert pd.Timestamp(trade["entry_time"]) == expected_entry_time
    assert np.isclose(trade["entry_price"], 100.0)


def test_opening_gap_slippage_handling():
    """BKT-002: If bar opens below stop price, exit must occur at open price, capturing slippage."""
    port_cfg = {
        "portfolio": {
            "initial_capital": 10000.0,
            "max_open_risk_pct": 0.05,
            "per_trade_risk_pct": 0.01,
            "risk_denominator": "component_allocation",
            "execution_timing": "next_bar_open",
            "max_drawdown_limit_pct": 0.10,
            "max_daily_loss_pct": 0.02
        },
        "allocation": {
            "TEST_ASSET": 1.0
        }
    }

    pm = PortfolioManager(port_cfg)
    df = create_mock_backtest_data()
    asset_configs = {
        "TEST_ASSET": {
            "prepared_df": df,
            "sl_atr_mult": 1.0,
            "tp_atr_mult": 4.0,
            "position_sizer": {
                "risk_pct": 0.01
            },
            "volatility_regime": {
                "allowed_regimes": ["NORMAL"]
            },
            "exit_rules": {
                "enable_trailing_stop": False
            },
            "execution": {
                "slippage_bps": 0,
                "commission_bps": 0
            }
        }
    }

    metrics = pm.run_portfolio_backtest(asset_configs)

    trades = metrics["trades"]
    assert len(trades) == 1
    trade = trades[0]

    # Stop price for next_bar_open:
    # Fill price = 105.0. Raw stop distance = 5.0 (from bar 1 atr=5.0 * 1.0).
    # So pos sl_price = 105.0 - 5.0 = 100.0.
    # At Bar 3, curr_open is 85.0, which is < sl_price 100.0.
    # Gap slippage exit price must be 85.0!
    assert np.isclose(trade["exit_price"], 85.0), f"Expected gap exit at 85.0, got: {trade['exit_price']}"
    assert trade["reason"] == "SL_HIT"
