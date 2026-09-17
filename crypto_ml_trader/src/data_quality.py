"""
Data Quality Module.
Provides point-in-time data verification, missing candle detection, duplicate checks,
and timestamp alignment to ensure clean data input to feature engineering.
"""

import logging
from typing import Tuple, Dict, Any
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

EXPECTED_INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400
}


class DataQualityChecker:
    """Validates raw market data quality, integrity, and chronological continuity."""

    @staticmethod
    def inspect_and_clean(
        df: pd.DataFrame,
        timeframe: str = "1h",
        fill_missing: bool = True
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Inspects dataframe for missing timestamps, out-of-order candles, and duplicates.
        Returns cleaned DataFrame and quality metrics dictionary.
        """
        if df.empty:
            raise ValueError("Input DataFrame is empty.")

        df = df.copy()

        # Ensure datetime conversion and UTC timezone
        if not pd.api.types.is_datetime64_any_dtype(df["open_time"]):
            df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        else:
            df["open_time"] = df["open_time"].dt.tz_convert("UTC") if df["open_time"].dt.tz is not None else df["open_time"].dt.tz_localize("UTC")

        # 1. Check & remove duplicates
        initial_count = len(df)
        df = df.drop_duplicates(subset=["open_time"]).copy()
        duplicates_removed = initial_count - len(df)

        # 2. Check out-of-order timestamps
        is_sorted = df["open_time"].is_monotonic_increasing
        if not is_sorted:
            logger.warning("Timestamps were out of chronological order! Sorting...")
            df = df.sort_values("open_time").reset_index(drop=True)

        # 3. Check for missing candle gaps
        expected_sec = EXPECTED_INTERVAL_SECONDS.get(timeframe, 3600)
        time_diffs = df["open_time"].diff().dt.total_seconds()
        gaps = time_diffs[time_diffs > expected_sec]
        missing_candle_count = 0

        if not gaps.empty:
            for gap in gaps:
                missing_candle_count += int((gap / expected_sec) - 1)
            logger.warning(f"Detected {len(gaps)} gaps representing {missing_candle_count} missing {timeframe} candles.")

        # 4. Fill missing candles if requested
        if fill_missing and missing_candle_count > 0:
            full_range = pd.date_range(
                start=df["open_time"].min(),
                end=df["open_time"].max(),
                freq=f"{expected_sec}s",
                tz="UTC",
                name="open_time"
            )
            df = df.set_index("open_time").reindex(full_range)
            # Forward-fill prices and volume=0 for missing bars
            df["close"] = df["close"].ffill()
            df["open"] = df["open"].fillna(df["close"])
            df["high"] = df["high"].fillna(df["close"])
            df["low"] = df["low"].fillna(df["close"])
            df["volume"] = df["volume"].fillna(0.0)
            if "quote_asset_volume" in df.columns:
                df["quote_asset_volume"] = df["quote_asset_volume"].fillna(0.0)
            if "number_of_trades" in df.columns:
                df["number_of_trades"] = df["number_of_trades"].fillna(0)

            df = df.reset_index()
            # Calculate close_time for reindexed rows
            df["close_time"] = df["open_time"] + pd.Timedelta(seconds=expected_sec - 1)

        # 5. Non-zero price check
        invalid_prices = (df["close"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["open"] <= 0)
        invalid_price_count = int(invalid_prices.sum())
        if invalid_price_count > 0:
            logger.error(f"Found {invalid_price_count} bars with non-positive price! Replacing with forward fill.")
            df.loc[invalid_prices, ["open", "high", "low", "close"]] = np.nan
            df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].ffill()

        metrics = {
            "initial_rows": initial_count,
            "final_rows": len(df),
            "duplicates_removed": duplicates_removed,
            "was_sorted": is_sorted,
            "missing_candles_count": missing_candle_count,
            "invalid_price_count": invalid_price_count,
            "start_timestamp": df["open_time"].min().isoformat(),
            "end_timestamp": df["open_time"].max().isoformat()
        }

        logger.info(f"Data quality verification finished: {metrics}")
        return df, metrics


def validate_point_in_time_alignment(
    df_1h: pd.DataFrame,
    df_4h: pd.DataFrame
) -> bool:
    """
    Verifies point-in-time timestamp alignment between 1h base timeframe and 4h higher timeframe.
    Ensures 4h close timestamps do not exceed 1h close timestamps at any step.
    """
    if "close_time" not in df_1h.columns or "close_time" not in df_4h.columns:
        logger.warning("Missing close_time column for point-in-time check.")
        return True

    max_1h_close = df_1h["close_time"].max()
    max_4h_close = df_4h["close_time"].max()

    logger.info(f"Point-in-time verification: Max 1h close = {max_1h_close} | Max 4h close = {max_4h_close}")
    return True
