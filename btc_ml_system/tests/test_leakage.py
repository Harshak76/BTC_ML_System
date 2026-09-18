"""
Tests for Data Leakage and Purging in btc_ml_system.
Verifies no future leakage between train, validation, and test splits.
"""

import pytest
import pandas as pd
import numpy as np

from btc_ml_system.src.splits import DataSplitter


def test_purged_splits():
    dates = pd.date_range("2023-01-01", periods=1000, freq="1h", tz="UTC")
    df = pd.DataFrame({"open_time": dates, "close": np.random.randn(1000)})

    config = {
        "splits": {
            "n_splits": 3,
            "embargo_pct": 0.01,
            "label_horizon": 12
        }
    }
    splitter = DataSplitter(config)
    splits = list(splitter.purged_walk_forward_splits(df))

    assert len(splits) > 0

    for train_idx, val_idx, test_idx in splits:
        # Check train < val < test ordering
        assert train_idx.max() < val_idx.min()
        assert val_idx.max() < test_idx.min()

        # Check purging gap between train and val
        gap_train_val = val_idx.min() - train_idx.max()
        assert gap_train_val >= config["splits"]["label_horizon"]
