"""
Unit and Integration Test Suite for BTC-ML System V2 Phase 3A:
Research Architecture & Quantitative Strategy Foundation.
"""

import tempfile
import numpy as np
import pandas as pd
import pytest

from btc_ml_system.src.research.base import (
    BaseResearchStrategy,
    StrategyMetadata,
    ExecutionAssumptions,
    StrategyFamily,
    ReturnUnit,
)
from btc_ml_system.src.research.registry import ResearchStrategyRegistry
from btc_ml_system.src.research.strategies.trend_following import DualEmaAtrTrendStrategy
from btc_ml_system.src.research.strategies.momentum import TsMomBreakoutStrategy
from btc_ml_system.src.research.strategies.mean_reversion import BbRsiMeanReversionStrategy
from btc_ml_system.src.research.runner import ResearchSimulationRunner
from btc_ml_system.src.research.candidate_matrix import GenuineCandidateMatrixBuilder
from btc_ml_system.src.validation.oos_validation import OutOfSampleEngine
from btc_ml_system.src.validation.experiment_tracker import ExperimentTracker


def create_mock_ohlcv(n_bars: int = 200, seed: int = 42, drift: float = 0.05) -> pd.DataFrame:
    """Generates synthetic, deterministic OHLCV candles with strictly completed intervals."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-01 00:00:00", periods=n_bars, freq="1h", tz="UTC")

    close_prices = 100.0 + np.cumsum(rng.normal(drift, 1.0, size=n_bars))
    close_prices = np.maximum(close_prices, 10.0)

    high_prices = close_prices + rng.uniform(0.2, 1.5, size=n_bars)
    low_prices = close_prices - rng.uniform(0.2, 1.5, size=n_bars)
    open_prices = low_prices + (high_prices - low_prices) * rng.uniform(0.2, 0.8, size=n_bars)
    volume = rng.uniform(1000.0, 50000.0, size=n_bars)

    df = pd.DataFrame({
        "open_time": dates,
        "open": open_prices,
        "high": high_prices,
        "low": low_prices,
        "close": close_prices,
        "volume": volume
    })
    return df


# ---------------------------------------------------------------------------
# 1. Strategy Interface Compliance & Metadata Isolation
# ---------------------------------------------------------------------------

def test_strategy_interface_compliance():
    """Verifies that all three initial strategy candidates implement BaseResearchStrategy."""
    candidates = [
        DualEmaAtrTrendStrategy(),
        TsMomBreakoutStrategy(),
        BbRsiMeanReversionStrategy(),
    ]
    unique_ids = set()

    for strat in candidates:
        assert isinstance(strat, BaseResearchStrategy)
        meta = strat.metadata
        assert isinstance(meta, StrategyMetadata)
        assert meta.strategy_id.startswith("RS_")
        assert meta.version == "1.0.0"
        assert meta.strategy_id not in unique_ids, "Strategy IDs must be unique"
        unique_ids.add(meta.strategy_id)

        # Assumptions
        assump = strat.execution_assumptions
        assert isinstance(assump, ExecutionAssumptions)
        assert assump.execution_timing == "next_bar_open"
        assert assump.enforce_completed_candles is True
        assert assump.expected_return_unit == ReturnUnit.PERCENTAGE_POINTS

        # Required features
        req_features = strat.required_features()
        assert isinstance(req_features, list)
        assert len(req_features) >= 3


def test_registry_registration_and_lookup():
    """Verifies ResearchStrategyRegistry registers and retrieves candidate instances."""
    strat = ResearchStrategyRegistry.get("RS_TF_DUAL_EMA_ATR_V1")
    assert isinstance(strat, DualEmaAtrTrendStrategy)

    all_metas = ResearchStrategyRegistry.list_strategies()
    assert len(all_metas) >= 3
    strat_ids = [m.strategy_id for m in all_metas]
    assert "RS_TF_DUAL_EMA_ATR_V1" in strat_ids
    assert "RS_MOM_TSMOM_BREAKOUT_V1" in strat_ids
    assert "RS_MR_BB_RSI_REVERSION_V1" in strat_ids


# ---------------------------------------------------------------------------
# 2. Deterministic Signal Generation & Zero Lookahead
# ---------------------------------------------------------------------------

def test_deterministic_signal_generation():
    """Verifies that identical historical market data inputs produce identical signals."""
    df = create_mock_ohlcv(150, seed=101)
    strat = DualEmaAtrTrendStrategy()

    sig1 = strat.generate_signals(df)
    sig2 = strat.generate_signals(df)

    pd.testing.assert_frame_equal(sig1, sig2)
    assert "signal" in sig1.columns
    assert "signal_strength" in sig1.columns
    assert "stop_loss_price" in sig1.columns
    assert "take_profit_price" in sig1.columns


def test_lookahead_prevention_on_signals():
    """
    Verifies that signal at bar t is invariant to future data bars t+1...t+N.
    """
    df_full = create_mock_ohlcv(200, seed=77)
    df_prefix = df_full.iloc[:120].copy()

    strat = TsMomBreakoutStrategy()
    sig_full = strat.generate_signals(df_full)
    sig_prefix = strat.generate_signals(df_prefix)

    # The signals up to row 120 must match exactly
    cols_to_check = ["signal", "signal_strength", "stop_loss_price", "take_profit_price"]
    pd.testing.assert_frame_equal(
        sig_prefix[cols_to_check],
        sig_full.iloc[:120][cols_to_check].reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# 3. Specific Entry and Exit Rules for All 3 Candidates
# ---------------------------------------------------------------------------

def test_trend_following_signals_and_stops():
    """Verifies Dual EMA trend signal generation and stops."""
    strat = DualEmaAtrTrendStrategy({"parameters": {"fast_ema_period": 5, "slow_ema_period": 15}})
    # Strong upward trend to force crossover
    df = create_mock_ohlcv(100, seed=42, drift=1.5)
    out = strat.generate_signals(df)

    assert set(out["signal"].unique()).issubset({0, 1})
    valid_stops = out.dropna(subset=["stop_loss_price", "take_profit_price"])
    assert len(valid_stops) > 50
    assert (valid_stops["stop_loss_price"] < valid_stops["close"]).all()
    assert (valid_stops["take_profit_price"] > valid_stops["close"]).all()


def test_momentum_signals_and_stops():
    """Verifies Donchian Breakout momentum signals and stops."""
    strat = TsMomBreakoutStrategy({"parameters": {"channel_entry_period": 10, "channel_exit_period": 5}})
    df = create_mock_ohlcv(120, seed=55, drift=1.2)
    out = strat.generate_signals(df)

    assert set(out["signal"].unique()).issubset({0, 1})
    valid_stops = out.dropna(subset=["stop_loss_price", "take_profit_price"])
    assert len(valid_stops) > 50
    assert (valid_stops["stop_loss_price"] < valid_stops["close"]).all()
    assert (valid_stops["take_profit_price"] > valid_stops["close"]).all()


def test_mean_reversion_signals_and_stops():
    """Verifies Bollinger Band / RSI mean reversion signals and stops."""
    strat = BbRsiMeanReversionStrategy({"parameters": {"bb_period": 15, "rsi_period": 10}})
    # Downward drift with oscillations
    df = create_mock_ohlcv(120, seed=99, drift=-0.5)
    out = strat.generate_signals(df)

    assert set(out["signal"].unique()).issubset({0, 1})
    valid_stops = out.dropna(subset=["stop_loss_price"])
    assert len(valid_stops) > 50
    assert (valid_stops["stop_loss_price"] < valid_stops["close"]).all()


# ---------------------------------------------------------------------------
# 4. Input Data Validation: Completed Candles, Missing Data & Monotonicity
# ---------------------------------------------------------------------------

def test_input_dataframe_validation_checks():
    """Verifies input validation rejects corrupted, unordered, or incomplete data."""
    strat = DualEmaAtrTrendStrategy()
    df_valid = create_mock_ohlcv(50)

    # Valid DataFrame passes
    strat.validate_input_dataframe(df_valid)

    # 1. Missing columns
    with pytest.raises(ValueError, match="missing mandatory columns"):
        strat.validate_input_dataframe(df_valid.drop(columns=["close"]))

    # 2. Non-monotonic timestamps
    df_unmonotonic = df_valid.copy()
    df_unmonotonic.loc[5, "open_time"] = df_unmonotonic.loc[0, "open_time"] - pd.Timedelta(days=1)
    with pytest.raises(ValueError, match="timestamps are not strictly monotonically increasing"):
        strat.validate_input_dataframe(df_unmonotonic)

    # 3. NaN in OHLC
    df_nan = df_valid.copy()
    df_nan.loc[3, "open"] = np.nan
    with pytest.raises(ValueError, match="contains NaN values in OHLC"):
        strat.validate_input_dataframe(df_nan)


# ---------------------------------------------------------------------------
# 5. Return Unit Scale Enforcement
# ---------------------------------------------------------------------------

def test_return_unit_scale_validation():
    """Verifies unit scale validator catches and rejects improper return units."""
    strat = DualEmaAtrTrendStrategy()

    # Valid percentage points: e.g. [+1.5, -0.8, +4.2]
    valid_pct = np.array([1.5, -0.8, 4.2, -1.2, 0.5])
    assert strat.validate_return_units(valid_pct, ReturnUnit.PERCENTAGE_POINTS) is True

    # Valid decimal fractions: e.g. [+0.015, -0.008, +0.042]
    valid_dec = np.array([0.015, -0.008, 0.042, -0.012, 0.005])
    assert strat.validate_return_units(valid_dec, ReturnUnit.DECIMAL_FRACTION) is True

    # Error: passing percentage scale (e.g. 15.0) when decimal fraction declared
    with pytest.raises(ValueError, match="Declared DECIMAL_FRACTION but observed value"):
        strat.validate_return_units(np.array([15.0, 20.0, -10.0]), ReturnUnit.DECIMAL_FRACTION)

    # Error: passing decimal scale (e.g. 0.005) when percentage points declared
    with pytest.raises(ValueError, match="Declared PERCENTAGE_POINTS but maximum non-zero value"):
        strat.validate_return_units(np.array([0.005] * 20), ReturnUnit.PERCENTAGE_POINTS)


# ---------------------------------------------------------------------------
# 6. Research Simulation Runner & Offline Execution
# ---------------------------------------------------------------------------

def test_research_simulation_runner_offline_execution():
    """Verifies the runner executes next-bar open simulation with costs and zero broker calls."""
    strat = DualEmaAtrTrendStrategy()
    runner = ResearchSimulationRunner(strategy=strat, initial_capital=100000.0, max_open_positions=2)

    data = {
        "AAPL": create_mock_ohlcv(150, seed=1, drift=0.8),
        "BTCUSDT": create_mock_ohlcv(150, seed=2, drift=1.0)
    }

    res = runner.run_simulation(data)
    assert res["is_broker_connected"] is False
    assert "metrics" in res
    assert "trades" in res
    assert "equity_curve" in res
    assert res["return_unit"] == "percentage_points"
    assert len(res["equity_curve"]) > 50


# ---------------------------------------------------------------------------
# 7. Genuine Candidate Matrix for PBO / CSCV
# ---------------------------------------------------------------------------

def test_genuine_candidate_matrix_builder_and_incomplete_flag():
    """
    Verifies that GenuineCandidateMatrixBuilder assembles genuine return series
    and marks PBO INCOMPLETE when fewer than 4 genuine candidates are supplied.
    """
    strat1 = DualEmaAtrTrendStrategy()
    strat2 = TsMomBreakoutStrategy()
    strat3 = BbRsiMeanReversionStrategy()

    data = {"BTCUSDT": create_mock_ohlcv(120, seed=12, drift=0.5)}

    r1 = ResearchSimulationRunner(strat1).run_simulation(data)
    r2 = ResearchSimulationRunner(strat2).run_simulation(data)
    r3 = ResearchSimulationRunner(strat3).run_simulation(data)

    # With only 3 genuine candidates, must be marked INCOMPLETE
    matrix_info = GenuineCandidateMatrixBuilder.build_matrix([r1, r2, r3])
    assert matrix_info["is_synthetic"] is False
    assert matrix_info["n_candidates"] == 3
    assert matrix_info["is_sufficient_for_pbo"] is False
    assert matrix_info["status"] == "INCOMPLETE"
    assert "minimum 4 required" in matrix_info["reason"]


# ---------------------------------------------------------------------------
# 8. Holdout Fallback Import Fix Verification
# ---------------------------------------------------------------------------

def test_holdout_fallback_imports_fix():
    """Verifies that OutOfSampleEngine fallback branch imports are cleanly resolved."""
    engine = OutOfSampleEngine()
    # Provide asset_configs without prepared_df to trigger the fallback import statements
    # It will proceed past the imports and attempt to fetch or slice
    try:
        engine.evaluate_portfolio_holdout(
            asset_configs={"BTCUSDT": {"data": {"history_years": 1}, "asset": {"base_timeframe": "1h", "htf_timeframe": "4h"}}},
            portfolio_config={"portfolio": {"initial_capital": 100000.0}}
        )
    except ModuleNotFoundError as e:
        pytest.fail(f"Fallback branch threw ModuleNotFoundError: {e}")
    except Exception:
        # Pass: Any other business logic exception is expected if files/network are absent
        pass
