"""
Automated Equity Data Quality Verification Test Suite for Phase 3B.2.
Verifies:
1. Differentiation across symbols (no cloned price or volume series).
2. Timestamp monotonicity and uniqueness.
3. OHLC mathematical consistency (L <= O, C <= H and L <= H).
4. Strictly positive prices and non-negative volume.
5. Plausible volume distributions without constant flatlines.
6. Split continuity (verifies NVDA 10:1 split is properly adjusted).
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest


DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "authentic_raw"
EQUITY_SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]


@pytest.fixture(scope="module")
def equity_dfs():
    dfs = {}
    for sym in EQUITY_SYMBOLS:
        csv_path = DATA_DIR / f"{sym.lower()}_1h.csv"
        assert csv_path.exists(), f"Missing authentic data file for {sym}: {csv_path}"
        df = pd.read_csv(csv_path)
        df["open_time_dt"] = pd.to_datetime(df["open_time"], utc=True)
        dfs[sym] = df
    return dfs


def test_equity_data_cross_symbol_differentiation(equity_dfs):
    """Workstream 2: Verifies that no two equity datasets have identical or suspiciously duplicated price series."""
    symbols = list(equity_dfs.keys())
    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            sym_a = symbols[i]
            sym_b = symbols[j]
            df_a = equity_dfs[sym_a]
            df_b = equity_dfs[sym_b]

            # Compare close prices on common timestamps
            merged = pd.merge(df_a, df_b, on="open_time", suffixes=("_a", "_b"))
            assert len(merged) > 1000, f"Insufficient overlapping bars between {sym_a} and {sym_b}"

            diff_close = np.abs(merged["close_a"] - merged["close_b"])
            max_diff = np.max(diff_close)
            mean_diff = np.mean(diff_close)

            # Assert prices are differentiated
            assert max_diff > 10.0, f"{sym_a} and {sym_b} have suspiciously close or identical prices! Max diff: {max_diff}"
            assert mean_diff > 5.0, f"{sym_a} and {sym_b} mean difference {mean_diff} is too low."


def test_equity_data_timestamp_monotonicity_and_uniqueness(equity_dfs):
    """Workstream 2: Verifies that timestamps are strictly monotonically increasing and unique."""
    for sym, df in equity_dfs.items():
        # Check uniqueness
        dup_count = df["open_time"].duplicated().sum()
        assert dup_count == 0, f"{sym} has {dup_count} duplicate timestamps!"

        # Check strict monotonicity
        time_diffs = df["open_time_dt"].diff().dropna()
        assert (time_diffs > pd.Timedelta(0)).all(), f"{sym} timestamps are not strictly monotonic!"


def test_equity_data_ohlc_relationships(equity_dfs):
    """Workstream 2: Verifies mathematical integrity of OHLC bars: low <= min(open, close), high >= max(open, close)."""
    for sym, df in equity_dfs.items():
        # L <= H
        assert (df["low"] <= df["high"] + 1e-6).all(), f"{sym} contains bars where Low > High!"
        # L <= O
        assert (df["low"] <= df["open"] + 1e-6).all(), f"{sym} contains bars where Low > Open!"
        # L <= C
        assert (df["low"] <= df["close"] + 1e-6).all(), f"{sym} contains bars where Low > Close!"
        # H >= O
        assert (df["high"] >= df["open"] - 1e-6).all(), f"{sym} contains bars where High < Open!"
        # H >= C
        assert (df["high"] >= df["close"] - 1e-6).all(), f"{sym} contains bars where High < Close!"


def test_equity_data_positive_prices_and_volume(equity_dfs):
    """Workstream 2: Verifies strictly positive prices and non-negative volume."""
    for sym, df in equity_dfs.items():
        assert (df["open"] > 0).all(), f"{sym} contains non-positive open prices!"
        assert (df["high"] > 0).all(), f"{sym} contains non-positive high prices!"
        assert (df["low"] > 0).all(), f"{sym} contains non-positive low prices!"
        assert (df["close"] > 0).all(), f"{sym} contains non-positive close prices!"
        assert (df["volume"] >= 0).all(), f"{sym} contains negative volume!"

        # Volume must not be completely constant/zero flatline
        std_vol = df["volume"].std()
        assert std_vol > 1000.0, f"{sym} has implausibly flat volume distribution (std={std_vol})!"


def test_equity_data_nvda_split_continuity(equity_dfs):
    """Workstream 2: Verifies that NVDA's June 2024 10-for-1 split is continuous (no 90% unadjusted price drop)."""
    df_nvda = equity_dfs["NVDA"]
    # Filter around June 7-10, 2024
    june_bars = df_nvda[(df_nvda["open_time_dt"] >= "2024-06-07") & (df_nvda["open_time_dt"] <= "2024-06-11")]
    assert len(june_bars) > 10, "Missing NVDA bars around split date."

    # In split-adjusted data, prices should be around ~120 USD, not 1200 USD
    mean_price = june_bars["close"].mean()
    assert 100.0 < mean_price < 150.0, f"NVDA split not adjusted! Mean price in June 2024 is {mean_price}"

    # Return between consecutive bars should not be -90%
    returns = june_bars["close"].pct_change().dropna()
    assert (returns.abs() < 0.25).all(), f"NVDA has unadjusted split jump: {returns.min()}"


def test_equity_data_manifest_consistency():
    """Workstream 2: Verifies that manifest.json matches files on disk."""
    manifest_path = DATA_DIR / "manifest.json"
    assert manifest_path.exists(), "Manifest file missing!"
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    for sym in EQUITY_SYMBOLS:
        assert sym in manifest["symbols"], f"Symbol {sym} missing from manifest"
        meta = manifest["symbols"][sym]
        csv_file = DATA_DIR / meta["filename"]
        assert csv_file.exists(), f"File {csv_file} referenced in manifest does not exist"
        df = pd.read_csv(csv_file)
        assert len(df) == meta["row_count"], f"Row count mismatch for {sym}: {len(df)} vs {meta['row_count']}"
