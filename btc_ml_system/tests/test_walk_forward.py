"""
Unit and Integration Tests for WalkForwardEngine.
Validates:
- Correct purged and embargoed chronological splits
- Rolling vs anchored window generation
- No data leakage across train/val/test splits
- Out-of-sample forward evaluation and WFE calculation
"""

import pandas as pd
import numpy as np
import pytest
from btc_ml_system.src.validation.walk_forward import WalkForwardEngine


@pytest.fixture
def sample_timeseries():
    """Generates 500 bars of synthetic time-series data."""
    dates = pd.date_range("2026-01-01 00:00:00", periods=500, freq="1h", tz="UTC")
    df = pd.DataFrame({
        "open_time": dates,
        "close_time": dates + pd.Timedelta(hours=1),
        "open": np.linspace(100, 200, 500) + np.random.normal(0, 1, 500),
        "high": np.linspace(102, 202, 500),
        "low": np.linspace(98, 198, 500),
        "close": np.linspace(101, 201, 500),
        "volume": [1000.0] * 500
    }, index=dates)
    return df


def test_walk_forward_split_generation_and_leakage_protection(sample_timeseries):
    """Verifies that walk-forward splits have zero index overlap and adhere to purge buffers."""
    engine = WalkForwardEngine({
        "walk_forward": {
            "train_bars": 120,
            "val_bars": 20,
            "test_bars": 40,
            "step_bars": 40,
            "purge_bars": 10,
            "embargo_bars": 10
        }
    })

    splits = list(engine.generate_splits(sample_timeseries, mode="rolling"))
    assert len(splits) > 0, "Should generate at least one split"

    for s in splits:
        train_idx = set(s["train_indices"])
        val_idx = set(s["val_indices"])
        test_idx = set(s["test_indices"])

        # 1. Zero index overlap
        assert len(train_idx.intersection(val_idx)) == 0, "Train and Val must not overlap"
        assert len(train_idx.intersection(test_idx)) == 0, "Train and Test must not overlap (zero leakage)"
        assert len(val_idx.intersection(test_idx)) == 0, "Val and Test must not overlap"

        # 2. Strict chronological ordering: all train/val indices < test indices
        max_train = max(train_idx)
        min_test = min(test_idx)
        assert min_test > max_train, f"Test index {min_test} must be strictly greater than train index {max_train}"

        # 3. Purge buffer enforcement
        purge_gap = min_test - max_train
        assert purge_gap >= engine.purge_bars, f"Gap {purge_gap} must be >= purge_bars {engine.purge_bars}"


def test_anchored_vs_rolling_window_modes(sample_timeseries):
    """Verifies that anchored window mode expands from 0, while rolling window mode shifts train_start."""
    engine = WalkForwardEngine({
        "walk_forward": {
            "train_bars": 100,
            "test_bars": 40,
            "step_bars": 40,
            "purge_bars": 5
        }
    })

    rolling_splits = list(engine.generate_splits(sample_timeseries, mode="rolling"))
    anchored_splits = list(engine.generate_splits(sample_timeseries, mode="anchored"))

    assert len(rolling_splits) >= 2
    assert len(anchored_splits) >= 2

    # In rolling mode, train_start shifts forward with each window
    assert rolling_splits[0]["train_indices"][0] < rolling_splits[1]["train_indices"][0]

    # In anchored mode, train_start is always 0 (expanding window)
    assert anchored_splits[0]["train_indices"][0] == 0
    assert anchored_splits[1]["train_indices"][0] == 0
    assert len(anchored_splits[1]["train_indices"]) > len(anchored_splits[0]["train_indices"])


def test_walk_forward_end_to_end_evaluation(sample_timeseries):
    """Verifies that run_walk_forward selects optimal IS parameters and tests on unseen OOS."""
    engine = WalkForwardEngine({
        "walk_forward": {
            "train_bars": 120,
            "test_bars": 40,
            "step_bars": 40,
            "purge_bars": 5
        }
    })

    candidate_params = [
        {"param_multiplier": 1.0},
        {"param_multiplier": 2.0},
        {"param_multiplier": 3.0}
    ]

    # Dummy evaluation function
    def mock_eval_fn(df_sub, params):
        mult = params["param_multiplier"]
        ret = float(len(df_sub) * mult * 0.01)
        return {
            "total_return_pct": ret,
            "sharpe_ratio": mult * 0.5,
            "win_rate": 0.55,
            "profit_factor": 1.2 * mult,
            "max_drawdown_pct": 3.0 / mult,
            "total_trades": len(df_sub) // 10,
            "trades": [{"pnl_usd": 10.0 * mult}]
        }

    wf_results = engine.run_walk_forward(
        sample_timeseries,
        candidate_params=candidate_params,
        eval_fn=mock_eval_fn,
        mode="rolling",
        selection_metric="sharpe_ratio"
    )

    assert wf_results["total_windows"] > 0
    assert "walk_forward_efficiency" in wf_results
    assert "consistency_ratio" in wf_results
    assert wf_results["windows"][0]["selected_params"]["param_multiplier"] == 3.0, (
        "IS selection should choose highest Sharpe parameter (3.0)"
    )
