"""
Unit Tests for Phase 3B.2.2: Authentic Data Path Resolution & Dataset Validation.

Verifies:
1. Explicit data_dir takes precedence and raises FileNotFoundError if path does not exist.
2. Default path resolution reliably resolves to 'data/authentic_raw' from repo root.
3. Default path resolution works when executing from another working directory.
4. Missing authentic data raises an explicit error and strictly prevents silent fallback to 'data/raw'.
5. Dataset validation validates expected universe symbols, required columns, and non-null values.
"""

import os
import tempfile
from pathlib import Path
import pytest
import pandas as pd

from btc_ml_system.src.research.evaluator import ResearchEvaluator


def test_explicit_data_dir_takes_precedence():
    """Verifies that an explicitly specified data_dir takes precedence over defaults."""
    repo_root = Path(__file__).resolve().parents[2]
    raw_dir = repo_root / "data" / "raw"
    auth_dir = repo_root / "data" / "authentic_raw"

    ev_explicit = ResearchEvaluator(data_dir=str(raw_dir))
    assert ev_explicit.data_dir.resolve() == raw_dir.resolve()

    ev_auth = ResearchEvaluator(data_dir=str(auth_dir))
    assert ev_auth.data_dir.resolve() == auth_dir.resolve()

    # Non-existent path must raise FileNotFoundError
    non_existent = repo_root / "data" / "does_not_exist_xyz"
    with pytest.raises(FileNotFoundError, match="Explicitly specified data_dir does not exist"):
        ResearchEvaluator(data_dir=str(non_existent))


def test_default_resolves_to_authentic_raw():
    """Verifies that ResearchEvaluator() by default resolves to authentic_raw and loads authentic data."""
    ev = ResearchEvaluator()
    assert ev.data_dir.name == "authentic_raw"
    assert "authentic_raw" in str(ev.data_dir)

    df_aapl = ev.load_asset_data("AAPL")
    # Authentic dataset has 10,871 bars (not legacy 5,110 bars)
    assert len(df_aapl) == 10871


def test_execution_from_another_working_directory():
    """Verifies that default path resolution succeeds when cwd is changed to a different directory."""
    original_cwd = os.getcwd()
    temp_dir = tempfile.gettempdir()
    try:
        os.chdir(temp_dir)
        ev = ResearchEvaluator()
        assert ev.data_dir.name == "authentic_raw"
        assert ev.data_dir.exists()
        df = ev.load_asset_data("AAPL")
        assert len(df) == 10871
    finally:
        os.chdir(original_cwd)


def test_missing_authentic_data_cannot_silently_fallback_to_raw(monkeypatch):
    """
    Verifies that if authentic_raw is missing or unresolvable, an explicit FileNotFoundError
    is raised and legacy data/raw is NEVER silently loaded.
    """
    # Monkeypatch Path.exists such that any check for 'authentic_raw' returns False
    orig_exists = Path.exists

    def mock_exists(path_obj):
        if "authentic_raw" in str(path_obj):
            return False
        return orig_exists(path_obj)

    monkeypatch.setattr(Path, "exists", mock_exists)

    with pytest.raises(FileNotFoundError) as excinfo:
        ResearchEvaluator()

    err_msg = str(excinfo.value)
    assert "Authentic data directory 'data/authentic_raw' could not be resolved" in err_msg
    assert "Silent fallback to legacy cloned data in 'data/raw' is strictly forbidden" in err_msg


def test_dataset_validation_checks_expected_symbols():
    """Verifies that validate_dataset raises ValueError when expected symbols are missing."""
    ev = ResearchEvaluator()
    dummy_df = pd.DataFrame({
        "open_time": pd.date_range("2026-01-01", periods=10, freq="1h", tz="UTC"),
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 102.0,
        "volume": 1000.0
    })

    # Missing expected symbols
    incomplete_dict = {"AAPL": dummy_df, "MSFT": dummy_df}
    with pytest.raises(ValueError, match="Universe validation failed: missing expected assets"):
        ev.validate_dataset(incomplete_dict, expected_symbols=["AAPL", "MSFT", "NVDA"])


def test_dataset_validation_checks_required_columns_and_nulls():
    """Verifies that validate_dataset raises ValueError when columns are missing or nulls exist."""
    ev = ResearchEvaluator()
    dates = pd.date_range("2026-01-01", periods=10, freq="1h", tz="UTC")

    # Missing 'volume' column
    df_missing_col = pd.DataFrame({
        "open_time": dates,
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 102.0
    })
    with pytest.raises(ValueError, match="missing required columns"):
        ev.validate_dataset({"AAPL": df_missing_col}, expected_symbols=["AAPL"])

    # Null values in close
    df_with_null = pd.DataFrame({
        "open_time": dates,
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": [102.0] * 9 + [None],
        "volume": 1000.0
    })
    with pytest.raises(ValueError, match="null values found in OHLCV columns"):
        ev.validate_dataset({"AAPL": df_with_null}, expected_symbols=["AAPL"])
