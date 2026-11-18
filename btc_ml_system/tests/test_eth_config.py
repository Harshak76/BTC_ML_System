"""
Tests for STR-001: ETH Session Filter Configuration Verification.
Validates:
- eth_1h_v4.5.yaml explicitly sets session_filter.enabled: false
- SessionFilter allows 24/7 trade evaluation when disabled (e.g. at 04:00 UTC)
- CryptoRegimeMomentumStrategy generates signals when evaluated with session filter disabled
"""

import yaml
from pathlib import Path
import pandas as pd
import numpy as np
from btc_ml_system.src.direction import SessionFilter
from btc_ml_system.src.strategies.crypto_regime_momentum import CryptoRegimeMomentumStrategy


def test_eth_config_session_filter_disabled():
    """STR-001: Verify ETH configuration has session_filter.enabled set to false."""
    config_path = Path(__file__).resolve().parent.parent / "configs" / "eth_1h_v4.5.yaml"
    assert config_path.exists(), f"Configuration file not found: {config_path}"

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    session_filter_cfg = cfg.get("session_filter", {})
    assert "enabled" in session_filter_cfg, "session_filter should define 'enabled'"
    assert session_filter_cfg["enabled"] is False, (
        f"ETH session_filter.enabled must be False for 24/7 crypto markets, found: {session_filter_cfg['enabled']}"
    )


def test_session_filter_permits_24_7_when_disabled():
    """STR-001: Verify SessionFilter permits signals at all hours (including 04:00 UTC) when disabled."""
    config = {
        "session_filter": {
            "enabled": False,
            "start_hour": 14,
            "end_hour": 22
        }
    }
    sf = SessionFilter(config)
    assert sf.enabled is False

    # Check timestamps across all 24 hours
    for hr in range(24):
        ts = pd.Timestamp(f"2026-01-01 {hr:02d}:00:00", tz="UTC")
        assert sf.is_session_valid(ts) is True, f"Hour {hr} should be valid when session filter is disabled"


def test_crypto_strategy_evaluates_with_disabled_session_filter():
    """STR-001: Verify CryptoRegimeMomentumStrategy correctly flags direction_valid in calm regime."""
    config = {
        "strategy": {
            "params": {
                "bb_period": 5,
                "bb_std_mult": 1.0,
                "max_bb_bandwidth": 0.10,
                "rsi_period": 5,
                "min_rsi": 40.0
            }
        },
        "multi_timeframe_filter": {
            "enabled": False
        }
    }
    strategy = CryptoRegimeMomentumStrategy(config)

    # 30 bars of tight calm base followed by a momentum expansion
    dates = pd.date_range("2026-01-01 00:00:00", periods=30, freq="1h", tz="UTC")
    closes = np.full(30, 2000.0)
    closes[20:25] = [2000, 2001, 2000, 2001, 2000]
    closes[25:] = [2010, 2020, 2030, 2040, 2050]

    df = pd.DataFrame({
        "open_time": dates,
        "close_time": dates + pd.Timedelta(hours=1),
        "open": closes,
        "high": closes + 5.0,
        "low": closes - 5.0,
        "close": closes,
        "volume": [1000.0] * 30,
        "volatility_regime": ["CALM"] * 30
    })

    df_out = strategy.evaluate_signals(df)
    assert "direction_valid" in df_out.columns
    assert df_out["direction_valid"].any(), "Strategy should generate valid signals under calm regime"
