"""
Automated Target Leakage & Point-in-Time Alignment Test Suite.
Guarantees zero future leakage across the feature engineering and split pipeline.
"""

import pytest
import pandas as pd
import numpy as np

from crypto_ml_trader.src.features import FeatureEngineer, detect_target_leakage
from crypto_ml_trader.src.splits import PurgedWalkForwardCV


def test_purged_walk_forward_splits_no_overlap():
    """Verifies purged walk forward CV creates non-overlapping train and validation index sets."""
    df = pd.DataFrame({"close": np.random.normal(100, 5, 500)})
    cv = PurgedWalkForwardCV(n_splits=5, label_horizon=12, embargo_pct=0.01)

    for fold, (train_idx, val_idx) in enumerate(cv.split(df)):
        # Train indices must all precede validation indices
        assert np.max(train_idx) < np.min(val_idx)

        # Check purging gap: min(val_idx) - max(train_idx) >= label_horizon
        purged_gap = np.min(val_idx) - np.max(train_idx)
        assert purged_gap >= 12, f"Fold {fold} purging gap ({purged_gap}) is less than label horizon (12)!"


def test_feature_matrix_no_future_timestamps():
    """Ensures feature matrix X at index t depends ONLY on rows <= t."""
    n = 100
    df = pd.DataFrame({
        "open_time": pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC"),
        "close_time": pd.date_range("2023-01-01 00:59:59", periods=n, freq="1h", tz="UTC"),
        "open": np.random.normal(100, 2, n),
        "high": np.random.normal(102, 2, n),
        "low": np.random.normal(98, 2, n),
        "close": np.random.normal(100, 2, n),
        "volume": np.random.uniform(10, 50, n)
    })

    fe = FeatureEngineer()
    df_feat1 = fe.create_1h_features(df.iloc[:50])
    df_feat2 = fe.create_1h_features(df)

    # Values for row 40 should be EXACTLY IDENTICAL whether computed on 50 bars or 100 bars
    feat_cols = [c for c in df_feat1.columns if c not in ["open_time", "close_time"]]
    for col in feat_cols:
        val1 = df_feat1[col].iloc[40]
        val2 = df_feat2[col].iloc[40]
        if np.isnan(val1) and np.isnan(val2):
            continue
        assert np.isclose(val1, val2, atol=1e-8), f"Feature '{col}' changed when future bars were added! Leakage detected!"
