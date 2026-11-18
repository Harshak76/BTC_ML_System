"""
Unit Tests for ExperimentTracker.
Validates:
- Unique UUID generation
- JSON persistence and registry checks
- Resumability detection
"""

import tempfile
from pathlib import Path
import pytest
from btc_ml_system.src.validation.experiment_tracker import ExperimentTracker


def test_experiment_tracker_logging_and_resumability():
    """Verifies experiment ID generation, JSON file logging, and resumability detection."""
    with tempfile.TemporaryDirectory() as temp_dir:
        tracker = ExperimentTracker(registry_dir=temp_dir, db_path=":memory:")

        exp_id = tracker.create_experiment_id()
        assert exp_id.startswith("EXP-")
        assert not tracker.is_experiment_completed(exp_id)

        record = tracker.log_experiment(
            experiment_id=exp_id,
            strategy_name="crypto_regime_momentum",
            strategy_version="v4.2",
            asset="BTCUSDT",
            timeframe="4h",
            parameter_config={"ema_fast": 20, "ema_slow": 50},
            dataset_info={"start": "2024-01-01", "end": "2026-01-01"},
            validation_results={"metrics": {"sharpe_ratio": 1.25, "total_return_pct": 15.0}}
        )

        assert tracker.is_experiment_completed(exp_id)
        saved_file = Path(temp_dir) / f"{exp_id}.json"
        assert saved_file.exists()
