"""
Tests for Labeling in btc_ml_system.
Verifies triple-barrier logic and sample weight generation.
"""

import pytest
import pandas as pd
import numpy as np

from btc_ml_system.src.labels import TripleBarrierLabeler


@pytest.fixture
def sample_ohlcv():
    dates = pd.date_range("2023-01-01", periods=100, freq="1h", tz="UTC")
    np.random.seed(42)
    close = 20000 + np.cumsum(np.random.randn(100) * 50)
    high = close + 30
    low = close - 30
    open_p = close

    return pd.DataFrame({
        "open_time": dates,
        "close_time": dates + pd.Timedelta(minutes=59, seconds=59),
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": 100.0
    })


def test_triple_barrier_labeler(sample_ohlcv):
    config = {
        "labels": {
            "pt_multiplier": 1.5,
            "sl_multiplier": 1.0,
            "max_vertical_barrier": 12,
            "volatility_window": 24,
            "min_return": 0.002
        }
    }
    labeler = TripleBarrierLabeler(config)
    lbl_df = labeler.generate_labels(sample_ohlcv)

    assert "target" in lbl_df.columns
    assert "target_binary" in lbl_df.columns
    assert "sample_weight" in lbl_df.columns
    assert set(lbl_df["target"].unique()).issubset({-1, 0, 1})
    assert (lbl_df["sample_weight"] > 0).all()
