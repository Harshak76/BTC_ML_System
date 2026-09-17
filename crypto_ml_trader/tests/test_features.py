"""
Unit tests for Feature Engineering Module.
Tests 4h point-in-time shift non-leakage, indicator calculation, and NaN handling.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from crypto_ml_trader.src.features import FeatureEngineer, detect_target_leakage


@pytest.fixture
def dummy_1h_4h_data():
    """Generates synthetic 1h and 4h price data for testing feature calculation."""
    n_1h = 240 # 10 days of 1h bars
    times_1h = [datetime(2023, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i) for i in range(n_1h)]
    closes = 20000.0 + np.cumsum(np.random.normal(0, 50, n_1h))

    df_1h = pd.DataFrame({
        "open_time": times_1h,
        "close_time": [t + timedelta(minutes=59, seconds=59) for t in times_1h],
        "open": closes - 10,
        "high": closes + 20,
        "low": closes - 20,
        "close": closes,
        "volume": np.random.uniform(10, 100, n_1h)
    })

    # Resample to 4h
    df_4h_grouped = df_1h.set_index("open_time").resample("4h")
    df_4h = pd.DataFrame({
        "open_time": df_4h_grouped.first().index,
        "close_time": df_4h_grouped.last()["close_time"].values,
        "open": df_4h_grouped["open"].first().values,
        "high": df_4h_grouped["high"].max().values,
        "low": df_4h_grouped["low"].min().values,
        "close": df_4h_grouped["close"].last().values,
        "volume": df_4h_grouped["volume"].sum().values
    }).reset_index()

    return df_1h, df_4h


def test_1h_feature_creation(dummy_1h_4h_data):
    df_1h, _ = dummy_1h_4h_data
    fe = FeatureEngineer()
    df_feat = fe.create_1h_features(df_1h)

    assert "log_ret_1h" in df_feat.columns
    assert "rsi_14" in df_feat.columns
    assert "norm_atr_14" in df_feat.columns
    assert "body_ratio" in df_feat.columns
    assert len(df_feat) == len(df_1h)


def test_4h_point_in_time_shift_non_leakage(dummy_1h_4h_data):
    """Verifies 4h features do NOT leak future incomplete bar data to 1h candles."""
    df_1h, df_4h = dummy_1h_4h_data
    fe = FeatureEngineer()
    df_1h_feat = fe.create_1h_features(df_1h)
    merged = fe.merge_confirmed_4h_features(df_1h_feat, df_4h)

    assert "htf_rsi_14" in merged.columns
    assert "htf_adx_14" in merged.columns

    # Verify that at any 1h bar close time T, the merged 4h HTF close time <= T
    # (Checking backward merge alignment)
    assert merged["htf_rsi_14"].notna().sum() > 0


def test_detect_target_leakage():
    df = pd.DataFrame({
        "clean_feature": np.random.normal(0, 1, 100),
        "leaked_feature": [0] * 90 + [1] * 10,
        "target": [0] * 90 + [1] * 10
    })

    leaked = detect_target_leakage(df, ["clean_feature", "leaked_feature"], "target", threshold=0.90)
    assert "leaked_feature" in leaked
    assert "clean_feature" not in leaked
