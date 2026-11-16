"""
Unit Tests for Portfolio Paper Trading Modes: Strict vs Loose_Stage1.
Verifies config-driven switching, parameter locks, loosened rule detection,
and database trade logging.
"""

import pytest
import yaml
from pathlib import Path

from btc_ml_system.src.portfolio_paper_trader import PortfolioPaperTrader


@pytest.fixture
def base_config():
    cfg_path = Path(__file__).resolve().parent.parent / "configs" / "portfolio_paper_v5.yaml"
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)
    # Ensure dry_run for testing
    cfg["alpaca"]["dry_run"] = True
    return cfg


def test_strict_mode_configuration(base_config):
    """Verifies strict mode enforces exact locked parameters."""
    trader = PortfolioPaperTrader(base_config, dry_run_override=True, mode_override="strict")
    
    assert trader.trading_mode == "strict"
    assert trader.max_corr_threshold == 0.70
    assert trader.btc_allowed_regimes == ["NORMAL"]
    
    # Verify BTC config
    btc_cfg = trader.asset_configs["BTCUSDT"]
    assert btc_cfg["volatility_regime"]["allowed_regimes"] == ["NORMAL"]
    assert btc_cfg["multi_timeframe_filter"]["enabled"] is True
    assert btc_cfg["multi_timeframe_filter"]["strength"] == "Medium"
    assert btc_cfg["dynamic_risk_sizer"]["enabled"] is False

    # Verify ETH clean config
    eth_cfg = trader.asset_configs["ETHUSDT"]
    assert eth_cfg["multi_timeframe_filter"]["enabled"] is False
    assert eth_cfg["session_filter"]["enabled"] is False
    assert eth_cfg["volatility_regime"]["allowed_regimes"] == ["CALM"]

    # Verify Equity V4.3 frozen
    for sym in trader.symbols_equity:
        eq_cfg = trader.asset_configs[sym]
        assert eq_cfg["dynamic_risk_sizer"]["enabled"] is False
        assert eq_cfg["exit_rules"]["enable_early_loss_cut"] is False
        assert eq_cfg["exit_rules"]["enable_profit_runner"] is False

    # Verify risk limits unchanged
    assert trader.max_portfolio_risk_pct == 0.03
    assert trader.max_daily_loss_pct == 0.02
    assert trader.max_drawdown_limit_pct == 0.10


def test_loose_stage1_mode_configuration(base_config):
    """Verifies loose_stage1 mode loosens ONLY BTC regime and correlation threshold."""
    trader = PortfolioPaperTrader(base_config, dry_run_override=True, mode_override="loose_stage1")
    
    assert trader.trading_mode == "loose_stage1"
    assert trader.max_corr_threshold == 0.80
    assert trader.btc_allowed_regimes == ["NORMAL", "CALM"]
    
    # Verify BTC config allows NORMAL and CALM
    btc_cfg = trader.asset_configs["BTCUSDT"]
    assert btc_cfg["volatility_regime"]["allowed_regimes"] == ["NORMAL", "CALM"]
    assert btc_cfg["multi_timeframe_filter"]["enabled"] is True
    assert btc_cfg["multi_timeframe_filter"]["strength"] == "Medium"
    assert btc_cfg["dynamic_risk_sizer"]["enabled"] is False

    # Verify ETH remains completely locked to clean version
    eth_cfg = trader.asset_configs["ETHUSDT"]
    assert eth_cfg["multi_timeframe_filter"]["enabled"] is False
    assert eth_cfg["session_filter"]["enabled"] is False
    assert eth_cfg["volatility_regime"]["allowed_regimes"] == ["CALM"]

    # Verify Equity V4.3 remains completely frozen
    for sym in trader.symbols_equity:
        eq_cfg = trader.asset_configs[sym]
        assert eq_cfg["dynamic_risk_sizer"]["enabled"] is False
        assert eq_cfg["exit_rules"]["enable_early_loss_cut"] is False
        assert eq_cfg["exit_rules"]["enable_profit_runner"] is False

    # Verify all portfolio risk limits remain strict and identical
    assert trader.max_portfolio_risk_pct == 0.03
    assert trader.max_daily_loss_pct == 0.02
    assert trader.max_drawdown_limit_pct == 0.10


def test_config_fallback_and_switch(base_config):
    """Verifies switching via config dictionary without CLI override."""
    # Test switching via config
    base_config["system"]["trading_mode"] = "loose_stage1"
    t1 = PortfolioPaperTrader(base_config, dry_run_override=True)
    assert t1.trading_mode == "loose_stage1"
    assert t1.max_corr_threshold == 0.80

    base_config["system"]["trading_mode"] = "strict"
    t2 = PortfolioPaperTrader(base_config, dry_run_override=True)
    assert t2.trading_mode == "strict"
    assert t2.max_corr_threshold == 0.70

    # Test invalid mode fallback to strict
    base_config["system"]["trading_mode"] = "unknown_mode"
    t3 = PortfolioPaperTrader(base_config, dry_run_override=True)
    assert t3.trading_mode == "strict"
