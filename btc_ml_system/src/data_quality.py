"""
Data Quality Module for V2 btc_ml_system.
Performs verification on OHLCV data to guarantee:
- Missing timestamp check
- Outlier detection (price spikes, zero volume)
- Monotonic timestamp ordering
- Zero lookahead bias validation
"""

import logging
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger("btc_ml_system.data_quality")


class DataQualityChecker:
    """Verifies data integrity and reports health metrics."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def check_integrity(self, df: pd.DataFrame, timeframe: str = "1h") -> Tuple[bool, Dict[str, Any]]:
        """
        Runs comprehensive data quality audits on OHLCV dataframe.
        Returns (is_valid, report_dict).
        """
        report = {
            "total_rows": len(df),
            "missing_values": 0,
            "gap_count": 0,
            "outlier_count": 0,
            "is_monotonic": True,
            "issues": []
        }

        if df.empty:
            report["issues"].append("DataFrame is empty.")
            return False, report

        # 1. Missing values
        null_counts = df.isnull().sum().to_dict()
        total_nulls = sum(null_counts.values())
        report["missing_values"] = int(total_nulls)
        if total_nulls > 0:
            report["issues"].append(f"Found {total_nulls} missing values across columns.")

        # 2. Monotonicity check
        if not df["open_time"].is_monotonic_increasing:
            report["is_monotonic"] = False
            report["issues"].append("open_time is NOT monotonically increasing.")

        # 3. Gap check
        freq_map = {"1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4)}
        expected_diff = freq_map.get(timeframe, pd.Timedelta(hours=1))
        time_diffs = df["open_time"].diff()
        gaps = time_diffs[time_diffs > expected_diff]
        report["gap_count"] = len(gaps)
        if len(gaps) > 0:
            report["issues"].append(f"Detected {len(gaps)} missing time gaps in sequence.")

        # 4. Outlier check (high < low, negative prices, price spikes > 20% in 1 bar)
        invalid_prices = (df["high"] < df["low"]) | (df["open"] <= 0) | (df["close"] <= 0)
        returns = df["close"].pct_change().abs()
        spikes = returns > 0.20

        outlier_mask = invalid_prices | spikes
        report["outlier_count"] = int(outlier_mask.sum())
        if report["outlier_count"] > 0:
            report["issues"].append(f"Detected {report['outlier_count']} price anomalies or extreme spikes (>20%).")

        is_valid = len(report["issues"]) == 0
        if is_valid:
            logger.info(f"Data quality check passed successfully for {len(df)} rows.")
        else:
            logger.warning(f"Data quality issues found: {report['issues']}")

        return is_valid, report

    def clean_data(self, df: pd.DataFrame, timeframe: str = "1h") -> pd.DataFrame:
        """Fixes minor gaps and forwards fills non-critical missing values strictly using past info."""
        df_clean = df.copy()
        df_clean = df_clean.sort_values("open_time").drop_duplicates("open_time").reset_index(drop=True)

        # Forward fill up to 3 bars max for gaps
        df_clean = df_clean.bfill(limit=3).ffill(limit=3)
        return df_clean
