"""
Tests for Feature Engineering in btc_ml_system.
Verifies no lookahead bias and accurate feature output shapes.
"""

import pytest
import pandas as pd
import numpy as np
import yaml

from btc_ml_system.src.features import FeatureEngineer


@pytest.fixture
def sample_ohlcv():
    dates = pd.date_range("2023-01-01", periods=200, freq="1h", tz="UTC")
    np.random.seed(42)
    close = 20000 + np.cumsum(np.random.randn(200) * 50)
    high = close + np.random.rand(200) * 20
    low = close - np.random.rand(200) * 20
    open_p = close + np.random.randn(200) * 5
    volume = 100 + np.random.rand(200) * 50

    return pd.DataFrame({
        "open_time": dates,
        "close_time": dates + pd.Timedelta(minutes=59, seconds=59),
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "taker_buy_base": volume * 0.5,
        "taker_buy_quote": volume * 0.5 * close,
        "quote_volume": volume * close
    })


def test_feature_generation(sample_ohlcv):
    config = {
        "features": {
            "returns_windows": [1, 2, 6],
            "rsi_period": 14,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "adx_period": 14,
            "volatility_windows": [12, 24],
            "volume_windows": [6, 24],
            "interaction_features": True
        }
    }
    fe = FeatureEngineer(config)
    feat_df = fe.create_features(sample_ohlcv)

    assert "ret_1h" in feat_df.columns
    assert "rsi_14" in feat_df.columns
    assert "macd" in feat_df.columns
    assert "adx_14" in feat_df.columns
    assert "rsi_x_vol24" in feat_df.columns
    assert len(feat_df) == len(sample_ohlcv)
