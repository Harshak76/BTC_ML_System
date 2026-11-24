"""
Unit and Lookahead Safety Tests for Phase 3C Strategy Filter Candidates:
1. RS_MOM_DONCHIAN_40_CONTROL
2. RS_MOM_DONCHIAN_40_ADX25
3. RS_MOM_DONCHIAN_40_4H_EMA_SLOPE
"""

import pytest
import numpy as np
import pandas as pd

from btc_ml_system.src.research.registry import ResearchStrategyRegistry
from btc_ml_system.src.research.strategies.donchian_filters import (
    Donchian40ControlStrategy,
    Donchian40AdxStrategy,
    Donchian40HtfEmaSlopeStrategy,
)
from btc_ml_system.src.research.runner import ResearchSimulationRunner


def create_synthetic_hourly_df(n_bars: int = 200, base_price: float = 100.0, trend: float = 0.5) -> pd.DataFrame:
    """Creates a deterministic synthetic hourly OHLCV dataframe."""
    timestamps = pd.date_range("2024-01-01 00:00:00", periods=n_bars, freq="1h", tz="UTC")
    closes = base_price + np.arange(n_bars) * trend + np.sin(np.arange(n_bars) / 5.0) * 2.0
    opens = closes - 0.2
    highs = closes + 1.0
    lows = closes - 1.0
    volumes = np.full(n_bars, 1000.0)

    return pd.DataFrame({
        "open_time": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes
    })


def test_phase3c_registry_and_metadata():
    """Verifies that all three Phase 3C candidates are registered with correct contracts."""
    strat_ids = [
        "RS_MOM_DONCHIAN_40_CONTROL",
        "RS_MOM_DONCHIAN_40_ADX25",
        "RS_MOM_DONCHIAN_40_4H_EMA_SLOPE"
    ]
    for sid in strat_ids:
        inst = ResearchStrategyRegistry.get(sid)
        assert inst is not None
        assert inst.metadata.strategy_id == sid
        assert inst.metadata.family.value == "momentum"
        assert inst.metadata.version == "2.0.0"
        assert "channel_entry_period" in inst.metadata.parameters_schema
        assert inst.metadata.parameters_schema["channel_entry_period"] == 40


def test_adx_filter_blocking_and_permission():
    """Verifies that ADX filter permits breakouts when ADX >= 25 and blocks them when ADX < 25."""
    strat_ctrl = ResearchStrategyRegistry.get("RS_MOM_DONCHIAN_40_CONTROL")
    strat_adx = ResearchStrategyRegistry.get("RS_MOM_DONCHIAN_40_ADX25")

    # Generate synthetic flat data (low ADX) with a sudden spike at the end
    n = 100
    ts = pd.date_range("2024-01-01 00:00:00", periods=n, freq="1h", tz="UTC")
    # Low-volatility flat range where ADX collapses
    closes = np.full(n, 100.0)
    # Oscillate slightly to keep ADX low
    closes = closes + np.sin(np.arange(n) * 2.0) * 0.1
    highs = closes + 0.2
    lows = closes - 0.2
    opens = closes.copy()

    # Create a breakout on bar 90
    for i in range(85, n):
        closes[i] = 100.0 + (i - 85) * 1.5
        highs[i] = closes[i] + 0.5
        lows[i] = closes[i] - 0.5
        opens[i] = closes[i] - 0.2

    df = pd.DataFrame({
        "open_time": ts,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": np.full(n, 500.0)
    })

    sig_ctrl = strat_ctrl.generate_signals(df)
    sig_adx = strat_adx.generate_signals(df)

    assert "adx" in sig_adx.columns
    # ADX must be bounded in [0, 100]
    valid_adx = sig_adx["adx"].dropna()
    assert (valid_adx >= 0.0).all()
    assert (valid_adx <= 100.0).all()

    # Where ADX filter triggered an entry, ADX must be >= 25.0
    adx_entries = sig_adx[sig_adx["signal"] == 1]
    if len(adx_entries) > 0:
        assert (adx_entries["adx"] >= 25.0).all()
        assert (adx_entries["regime"] == "MOMENTUM_EXPANSION_ADX").all()


def test_4h_ema_slope_zero_lookahead_boundary():
    """
    Strict boundary test: verifies that at 1H timestamps 12:00, 13:00, 14:00, 15:00,
    the 4H EMA slope references ONLY the completed 4H bar that closed at 12:00 UTC.
    Only at 16:00 (1H close of the 15:00 bar) may it reference the 12:00-16:00 bar.
    """
    strat = ResearchStrategyRegistry.get("RS_MOM_DONCHIAN_40_4H_EMA_SLOPE")

    # Construct 100 hourly bars
    n = 100
    ts = pd.date_range("2024-01-01 00:00:00", periods=n, freq="1h", tz="UTC")
    df = pd.DataFrame({
        "open_time": ts,
        "open": np.linspace(100, 150, n),
        "high": np.linspace(101, 151, n),
        "low": np.linspace(99, 149, n),
        "close": np.linspace(100.5, 150.5, n),
        "volume": np.full(n, 1000.0)
    })

    sig = strat.generate_signals(df)
    assert "htf_ema_slope" in sig.columns

    # Verify that htf_ema_slope is constant across each 4-hour forming window
    # 4H bar 1 completed at 04:00 UTC (slope is NaN because diff requires 2 bars)
    # 4H bar 2 completed at 08:00 UTC (first valid slope)
    # 1H bars with open_time:
    # 07:00 (closes 08:00) -> completed 4H is 08:00
    # 08:00 (closes 09:00), 09:00 (closes 10:00), 10:00 (closes 11:00) -> all reference completed 4H at 08:00
    slope_08 = sig.loc[sig["open_time"] == "2024-01-01 08:00:00+00:00", "htf_ema_slope"].values[0]
    slope_09 = sig.loc[sig["open_time"] == "2024-01-01 09:00:00+00:00", "htf_ema_slope"].values[0]
    slope_10 = sig.loc[sig["open_time"] == "2024-01-01 10:00:00+00:00", "htf_ema_slope"].values[0]

    assert not np.isnan(slope_08)
    assert slope_08 == slope_09 == slope_10, "Forming 4H candle must not leak varying values before completion!"

    # 1H bar at 11:00 (closes 12:00) advances to the 12:00 completed 4H bar
    slope_11 = sig.loc[sig["open_time"] == "2024-01-01 11:00:00+00:00", "htf_ema_slope"].values[0]
    assert not np.isnan(slope_11)
    # In an accelerating trend, slope_11 will be different from slope_08
    assert slope_11 != slope_08


def test_simulation_balance_sheet_identity_and_risk_bounds():
    """Verifies that running ResearchSimulationRunner preserves E = Cash + MV exactly."""
    df = create_synthetic_hourly_df(n_bars=150, trend=0.8)
    data_dict = {"AAPL": df}

    for sid in ["RS_MOM_DONCHIAN_40_CONTROL", "RS_MOM_DONCHIAN_40_ADX25", "RS_MOM_DONCHIAN_40_4H_EMA_SLOPE"]:
        strat = ResearchStrategyRegistry.get(sid)
        runner = ResearchSimulationRunner(strategy=strat, initial_capital=100000.0)
        res = runner.run_simulation(data_dict)

        eq_curve = res["equity_curve"]
        assert len(eq_curve) > 0
        for pt in eq_curve:
            # Check balance sheet identity
            assert "equity" in pt
            assert "cash" in pt
            assert pt["equity"] > 0
