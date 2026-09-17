"""
Unit tests for Triple-Barrier Labeling Module.
Verifies label values (BUY: 1, SELL: -1, HOLD: 0), vertical barrier expiry, and barrier hit order.
"""

import pytest
import pandas as pd
import numpy as np

from crypto_ml_trader.src.labels import TripleBarrierLabeler


def test_triple_barrier_buy_label():
    """Tests that touching upper profit barrier generates label 1 (BUY)."""
    n = 30
    closes = np.array([100.0] * n)
    highs = np.array([100.0] * n)
    lows = np.array([100.0] * n)

    # At step 3, price spikes up past profit target
    highs[3] = 110.0
    closes[3] = 108.0

    df = pd.DataFrame({
        "close": closes,
        "high": highs,
        "low": lows
    })

    labeler = TripleBarrierLabeler(pt_multiplier=1.0, sl_multiplier=1.0, max_vertical_barrier=12, min_return=0.02)
    df_labeled = labeler.generate_labels(df)

    assert df_labeled["label_tb"].iloc[0] == 1
    assert df_labeled["target_buy"].iloc[0] == 1
    assert df_labeled["barrier_touch_type"].iloc[0] == "upper"


def test_triple_barrier_sell_label():
    """Tests that touching lower stop loss barrier generates label -1 (SELL)."""
    n = 30
    closes = np.array([100.0] * n)
    highs = np.array([100.0] * n)
    lows = np.array([100.0] * n)

    # At step 2, price drops past stop loss barrier
    lows[2] = 90.0
    closes[2] = 91.0

    df = pd.DataFrame({
        "close": closes,
        "high": highs,
        "low": lows
    })

    labeler = TripleBarrierLabeler(pt_multiplier=1.0, sl_multiplier=1.0, max_vertical_barrier=12, min_return=0.02)
    df_labeled = labeler.generate_labels(df)

    assert df_labeled["label_tb"].iloc[0] == -1
    assert df_labeled["target_buy"].iloc[0] == 0
    assert df_labeled["barrier_touch_type"].iloc[0] == "lower"


def test_triple_barrier_vertical_expiry():
    """Tests flat price movement reaching vertical barrier expiry (HOLD label 0)."""
    n = 30
    df = pd.DataFrame({
        "close": [100.0] * n,
        "high": [100.5] * n,
        "low": [99.5] * n
    })

    labeler = TripleBarrierLabeler(pt_multiplier=2.0, sl_multiplier=2.0, max_vertical_barrier=12, min_return=0.02)
    df_labeled = labeler.generate_labels(df)

    assert df_labeled["label_tb"].iloc[0] == 0
    assert df_labeled["barrier_touch_type"].iloc[0] == "vertical"
    assert df_labeled["barrier_touch_bars"].iloc[0] == 12
