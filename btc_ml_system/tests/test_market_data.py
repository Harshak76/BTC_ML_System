"""
Unit and Integration Tests for Market Data Pipeline.
Validates:
- DAT-001: Completed candle finalization & forming candle exclusion
- DAT-002: Historical lookback gap detection and backfill logic
"""

import pandas as pd
import numpy as np
import pytest
from btc_ml_system.src.data_provider import DataProvider


def test_completed_candle_filtering():
    """DAT-001: Verifies that forming unclosed candles are excluded from signal calculations."""
    base_time = pd.Timestamp("2026-11-18 16:00:00", tz="UTC")
    dates = pd.date_range(start="2026-11-18 10:00:00", periods=7, freq="1h", tz="UTC")
    step = pd.Timedelta(hours=1)

    df = pd.DataFrame({
        "open_time": dates,
        "close_time": dates + step,
        "open": [100 + i for i in range(7)],
        "high": [105 + i for i in range(7)],
        "low": [95 + i for i in range(7)],
        "close": [102 + i for i in range(7)],
        "volume": [1000 for _ in range(7)]
    })

    # Scenario A: Current time is 16:30:00 UTC (The 16:00-17:00 bar is forming!)
    now_forming = pd.Timestamp("2026-11-18 16:30:00", tz="UTC")
    completed_a = DataProvider.get_completed_candles(df, interval="1h", now_utc=now_forming)

    assert len(completed_a) == 6
    assert completed_a.iloc[-1]["open_time"] == pd.Timestamp("2026-11-18 15:00:00", tz="UTC")
    assert completed_a.iloc[-1]["close_time"] == pd.Timestamp("2026-11-18 16:00:00", tz="UTC")
    # Verify the forming 16:00 candle was excluded
    assert pd.Timestamp("2026-11-18 16:00:00", tz="UTC") not in completed_a["open_time"].values

    # Scenario B: Current time is 17:05:00 UTC (The 16:00-17:00 bar has fully completed!)
    now_closed = pd.Timestamp("2026-11-18 17:05:00", tz="UTC")
    completed_b = DataProvider.get_completed_candles(df, interval="1h", now_utc=now_closed)

    assert len(completed_b) == 7
    assert completed_b.iloc[-1]["open_time"] == pd.Timestamp("2026-11-18 16:00:00", tz="UTC")
    assert completed_b.iloc[-1]["close_time"] == pd.Timestamp("2026-11-18 17:00:00", tz="UTC")


def test_gap_detection_and_stale_cache_handling(tmp_path):
    """DAT-002: Verifies gap detection when cache and live data are separated by a large time gap."""
    config = {
        "data": {"raw_dir": str(tmp_path)},
        "asset": {"symbol": "BTCUSDT", "asset_type": "crypto"},
        "alpaca": {"api_key": "MOCK_KEY", "secret_key": "MOCK_SECRET"}
    }
    provider = DataProvider(config)

    # 1. Create a stale cache ending in September 2026
    stale_dates = pd.date_range("2026-09-01", periods=100, freq="1h", tz="UTC")
    stale_df = pd.DataFrame({
        "open_time": stale_dates,
        "close_time": stale_dates + pd.Timedelta(hours=1),
        "open": 60000.0, "high": 60100.0, "low": 59900.0, "close": 60050.0, "volume": 500.0
    })
    stale_path = tmp_path / "btcusdt_1h.csv"
    stale_df.to_csv(stale_path, index=False)

    # 2. Mock live data starting in November 2026 (Gap of ~50 days)
    live_dates = pd.date_range("2026-11-15", periods=50, freq="1h", tz="UTC")
    live_df = pd.DataFrame({
        "open_time": live_dates,
        "close_time": live_dates + pd.Timedelta(hours=1),
        "open": 90000.0, "high": 90500.0, "low": 89500.0, "close": 90200.0, "volume": 1200.0
    })

    # Mock _fetch_live_crypto to return live_df and _backfill_range to return empty (unbridgeable)
    provider._fetch_live_crypto = lambda sym, interval, limit=350: live_df
    provider._backfill_range = lambda sym, interval, start, end, is_crypto: pd.DataFrame()

    stitched = provider.fetch_live_data("BTCUSDT", "1h")

    # Stale cache must be discarded to prevent joining 60k Sep prices with 90k Nov prices without continuity
    assert len(stitched) == 50
    assert stitched["open_time"].min() == pd.Timestamp("2026-11-15", tz="UTC")
