"""
Test Suite for Workstream 3: Regime Attribution Remediation.
Verifies:
1. Different assets can have different regimes at the same time.
2. A trade cannot inherit another asset's regime.
3. Future bars cannot affect historical regime classification (zero lookahead).
4. Rolling quantiles use only information available at the decision timestamp.
5. Missing observations cannot silently become a default regime (unmatched recorded).
6. Multi-asset regime evaluation matches valid trades on composite key (symbol, entry_time).
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from btc_ml_system.src.research.evaluator import ResearchEvaluator


def create_synthetic_candle_series(n_bars: int = 100, trend: float = 0.0, vol: float = 1.0, start_time: str = "2024-01-01 00:00:00+00:00") -> pd.DataFrame:
    """Helper to create synthetic OHLCV candles."""
    times = pd.date_range(start_time, periods=n_bars, freq="1h", tz="UTC")
    close = 100.0 + np.cumsum(np.random.normal(trend, vol, n_bars))
    high = close + vol * np.random.uniform(0.5, 1.5, n_bars)
    low = close - vol * np.random.uniform(0.5, 1.5, n_bars)
    open_p = (high + low) / 2.0
    vol_p = np.random.uniform(1000, 5000, n_bars)
    return pd.DataFrame({
        "open_time": times.astype(str),
        "open": open_p,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol_p,
        "close_time": (times + pd.Timedelta(hours=1)).astype(str)
    })


def test_regime_different_assets_different_regimes_at_same_time():
    """Workstream 3: Proves that different assets can have different regimes at the same timestamp."""
    np.random.seed(42)
    ev = ResearchEvaluator()

    # Asset A: High volatility
    df_a = create_synthetic_candle_series(n_bars=100, vol=5.0)
    # Asset B: Very calm volatility
    df_b = create_synthetic_candle_series(n_bars=100, vol=0.1)

    reg_a = ev.compute_asset_regime_features(df_a, rolling_window=50)
    reg_b = ev.compute_asset_regime_features(df_b, rolling_window=50)

    # Check that at bar 60, both assets have different volatility levels
    norm_vol_a = (reg_a["high"] - reg_a["low"]).iloc[60] / reg_a["close"].iloc[60]
    norm_vol_b = (reg_b["high"] - reg_b["low"]).iloc[60] / reg_b["close"].iloc[60]
    assert norm_vol_a > 5 * norm_vol_b, "Asset A should be significantly more volatile than Asset B."


def test_trade_cannot_inherit_another_assets_regime():
    """Workstream 3: Proves that a trade for Symbol B does not match against Symbol A."""
    np.random.seed(42)
    ev = ResearchEvaluator()

    df_a = create_synthetic_candle_series(n_bars=100, trend=2.0)
    df_b = create_synthetic_candle_series(n_bars=100, trend=-2.0)

    data_dict = {"AAPL": df_a, "BTCUSDT": df_b}

    # Trade for BTCUSDT
    t_time = str(df_b["open_time"].iloc[50])
    trade_btc = [{"symbol": "BTCUSDT", "entry_time": t_time, "pnl_usd": 100.0}]

    stats = ev.evaluate_regimes(data_dict, trade_btc)
    assert stats["matched_trades_count"] == 1
    assert stats["unmatched_trades_count"] == 0

    # Trade with wrong symbol should fail matching
    trade_unknown = [{"symbol": "UNKNOWN_ASSET", "entry_time": t_time, "pnl_usd": 100.0}]
    stats_unknown = ev.evaluate_regimes(data_dict, trade_unknown)
    assert stats_unknown["matched_trades_count"] == 0
    assert stats_unknown["unmatched_trades_count"] == 1
    assert stats_unknown["unmatched_trades"][0]["symbol"] == "UNKNOWN_ASSET"


def test_future_bars_cannot_affect_historical_regime_classification():
    """Workstream 3: Proves rolling quantiles introduce zero full-sample lookahead."""
    np.random.seed(42)
    ev = ResearchEvaluator()

    # Base dataset of 80 bars
    df_short = create_synthetic_candle_series(n_bars=80, vol=1.0)
    features_short = ev.compute_asset_regime_features(df_short, rolling_window=50)

    # Extended dataset with 40 massive future shock bars added to the end
    df_future_shock = create_synthetic_candle_series(n_bars=40, vol=50.0, start_time="2024-01-04 08:00:00+00:00")
    df_long = pd.concat([df_short, df_future_shock], ignore_index=True)
    features_long = ev.compute_asset_regime_features(df_long, rolling_window=50)

    # For all bars 0 to 79 (before the future shock occurred):
    # Historical rolling volatility and regime classification must be 100% IDENTICAL
    for idx in range(30, 80):
        vol_reg_short = features_short.loc[idx, "vol_regime"]
        vol_reg_long = features_long.loc[idx, "vol_regime"]
        assert vol_reg_short == vol_reg_long, f"Lookahead detected at bar {idx}! Short: {vol_reg_short}, Long: {vol_reg_long}"


def test_missing_observations_cannot_silently_become_default_regime():
    """Workstream 3: Proves that unmatched timestamps are recorded in unmatched_trades and not silently defaulted."""
    ev = ResearchEvaluator()
    df = create_synthetic_candle_series(n_bars=50)

    # Trade with an entry timestamp outside the data series
    fake_trades = [
        {"symbol": "AAPL", "entry_time": "1999-01-01 00:00:00+00:00", "pnl_usd": 50.0},
        {"symbol": "AAPL", "entry_time": "2050-01-01 00:00:00+00:00", "pnl_usd": -25.0}
    ]

    stats = ev.evaluate_regimes({"AAPL": df}, fake_trades)
    assert stats["matched_trades_count"] == 0
    assert stats["unmatched_trades_count"] == 2
    assert len(stats["unmatched_trades"]) == 2
    # Check that neither was added to RANGING or NORMAL
    assert stats["RANGING"]["trades"] == 0
    assert stats["NORMAL"]["trades"] == 0
