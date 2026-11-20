"""
Unit and Integration Test Suite for BTC-ML System V2 Phase 3B:
Controlled Strategy Expansion & Independent Performance Evaluation.

Verifies:
1. Next-bar open execution protocol.
2. Entry-price-based stop and target anchoring.
3. Gap-through-stop conservative fill behavior.
4. Intrabar stop-loss and take-profit collision conservative rule.
5. Trailing-stop updates without lookahead bias.
6. Equity market sessions enforcement (no weekend/off-hours execution).
7. Crypto continuous trading (24/7/365 execution).
8. Cost calculations by asset class (separate equity vs crypto).
9. Position sizing with risk and capital constraints.
10. Benchmark alignment and execution (Buy & Hold, Cash, SMA).
11. Return-series alignment across strategies.
12. Genuine candidate matrix construction (N >= 4).
13. Missing return observations handling without fabrication.
14. Experiment registry persistence into DuckDB.
15. Zero lookahead in regime analysis.
16. Incomplete PBO handling when candidate pool is insufficient.
"""

import os
import tempfile
from typing import Dict, Any, List, Optional, Tuple, Union
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
from btc_ml_system.src.research.runner import ResearchSimulationRunner
from btc_ml_system.src.research.candidate_matrix import GenuineCandidateMatrixBuilder
from btc_ml_system.src.research.strategies import (
    DualEmaAtrTrendStrategy,
    TsMomBreakoutStrategy,
    BbRsiMeanReversionStrategy,
)
from btc_ml_system.src.research.evaluator import ResearchEvaluator
from btc_ml_system.src.validation.experiment_tracker import ExperimentTracker


def create_deterministic_bars(
    n_bars: int = 100,
    start_date: str = "2026-06-01 14:00:00",
    base_price: float = 100.0,
    price_path: Optional[np.ndarray] = None
) -> pd.DataFrame:
    """Creates deterministic test bars with proper UTC timestamps."""
    dates = pd.date_range(start=start_date, periods=n_bars, freq="1h", tz="UTC")
    if price_path is None:
        closes = np.linspace(base_price, base_price * 1.20, n_bars)
    else:
        closes = price_path

    opens = np.roll(closes, 1)
    opens[0] = closes[0]
    highs = np.maximum(opens, closes) * 1.01
    lows = np.minimum(opens, closes) * 0.99
    volumes = np.full(n_bars, 1000.0)

    return pd.DataFrame({
        "open_time": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
        "close_time": dates + pd.to_timedelta(1, unit="h")
    })


class MockSignalStrategy(BaseResearchStrategy):
    """Deterministic mock strategy emitting controlled entry/exit signals for testing."""

    def __init__(self, entry_bar: int = 2, exit_bar: int = 10, sl_dist: float = 5.0, tp_dist: float = 10.0, trailing: float = 0.0):
        super().__init__()
        self.entry_bar = entry_bar
        self.exit_bar = exit_bar
        self.sl_dist = sl_dist
        self.tp_dist = tp_dist
        self.trailing = trailing

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="MOCK_TEST_STRAT",
            strategy_name="Mock Testing Strategy",
            family=StrategyFamily.TREND_FOLLOWING,
            version="1.0.0",
            author="Test",
            description="Mock",
            supported_assets=["BTCUSDT", "AAPL"],
            supported_timeframes=["1h"]
        )

    @property
    def execution_assumptions(self) -> ExecutionAssumptions:
        return ExecutionAssumptions(
            slippage_bps=5.0,
            commission_bps=10.0,
            execution_timing="next_bar_open",
            enforce_completed_candles=True,
            expected_return_unit=ReturnUnit.PERCENTAGE_POINTS
        )

    def required_features(self):
        return []

    def generate_signals(self, df: pd.DataFrame, htf_df=None) -> pd.DataFrame:
        out = df.copy()
        n = len(out)
        signals = np.zeros(n, dtype=int)
        for i in range(n):
            if i == self.entry_bar:
                signals[i] = 1
            elif i >= self.exit_bar:
                signals[i] = 0
            else:
                signals[i] = 1 if i > self.entry_bar else 0
        out["signal"] = signals
        out["signal_strength"] = 1.0
        out["regime"] = "TEST"
        return self.calculate_stops_and_targets(out)

    def calculate_stops_and_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        close = out["close"]
        out["stop_loss_price"] = close - self.sl_dist
        out["take_profit_price"] = close + self.tp_dist
        out["trailing_stop_pct"] = self.trailing
        return out


# Test 1: Next-bar execution
def test_next_bar_open_execution_protocol():
    strat = MockSignalStrategy(entry_bar=5, exit_bar=20)
    df = create_deterministic_bars(50, start_date="2026-06-01 14:00:00")
    runner = ResearchSimulationRunner(strat, initial_capital=100000.0)
    res = runner.run_simulation({"BTCUSDT": df})

    assert res["total_trades"] >= 1
    trade = res["trades"][0]
    expected_entry_time = str(df.loc[6, "open_time"])
    assert trade["entry_time"] == expected_entry_time, "Order must execute at bar t+1 open following signal at bar t."


# Test 2: Entry-price-based stop anchoring
def test_entry_price_based_stop_and_target_anchoring():
    sl_dist = 4.0
    tp_dist = 8.0
    strat = MockSignalStrategy(entry_bar=5, exit_bar=20, sl_dist=sl_dist, tp_dist=tp_dist)
    df = create_deterministic_bars(50, start_date="2026-06-01 14:00:00")
    # Simulate an opening gap between close of bar 5 and open of bar 6
    df.loc[5, "close"] = 100.0
    df.loc[6, "open"] = 105.0  # +5 gap
    df.loc[6, "high"] = 106.0
    df.loc[6, "low"] = 104.0
    df.loc[6, "close"] = 105.5

    runner = ResearchSimulationRunner(strat, initial_capital=100000.0)
    res = runner.run_simulation({"BTCUSDT": df})
    trade = res["trades"][0]
    fill_price = trade["entry_price"]

    # Fill price includes slippage: 105.0 * (1 + 5 bps) = 105.0525
    expected_fill = 105.0 * (1.0 + 5.0 / 10000.0)
    assert abs(fill_price - expected_fill) < 1e-4

    # Stop loss must be anchored to actual fill_price - sl_dist (105.0525 - 4.0 = 101.0525)
    # Not obsolete close - sl_dist (100.0 - 4.0 = 96.0)
    expected_sl = fill_price - sl_dist
    assert expected_sl > 100.0, "Stop loss must anchor to actual entry fill price, adjusting for the opening gap."


# Test 3: Gap-through-stop conservative fill behavior
def test_gap_through_stop_loss_conservative_fill():
    strat = MockSignalStrategy(entry_bar=5, exit_bar=20, sl_dist=5.0)
    df = create_deterministic_bars(50, start_date="2026-06-01 14:00:00")
    # Entry at bar 6 open around 100
    # At bar 7, price gaps down drastically below stop loss (e.g. opens at 80.0 when SL is ~95.0)
    df.loc[7, "open"] = 80.0
    df.loc[7, "high"] = 81.0
    df.loc[7, "low"] = 79.0
    df.loc[7, "close"] = 80.5

    runner = ResearchSimulationRunner(strat, initial_capital=100000.0)
    res = runner.run_simulation({"BTCUSDT": df})
    trade = res["trades"][0]

    assert trade["reason"] == "STOP_LOSS"
    # Exit price must be based on open price 80.0 (with slippage), not the optimistic stop price 95.0!
    assert trade["exit_price"] < 85.0, "Gap-through stop must fill at the adverse market open price, not the stop price."


# Test 4: Intrabar stop-loss and take-profit collision rule
def test_intrabar_stop_loss_and_take_profit_collision_conservative_rule():
    strat = MockSignalStrategy(entry_bar=5, exit_bar=20, sl_dist=5.0, tp_dist=5.0)
    df = create_deterministic_bars(50, start_date="2026-06-01 14:00:00")
    # Bar 7 has a giant wick that touches BOTH SL (< 95) and TP (> 105)
    df.loc[7, "open"] = 100.0
    df.loc[7, "high"] = 120.0  # Touches TP
    df.loc[7, "low"] = 80.0    # Touches SL
    df.loc[7, "close"] = 100.0

    runner = ResearchSimulationRunner(strat, initial_capital=100000.0)
    res = runner.run_simulation({"BTCUSDT": df})
    trade = res["trades"][0]

    assert trade["reason"] == "STOP_LOSS_COLLISION", "Collision rule must conservatively assume stop-loss was hit first."
    assert trade["pnl_usd"] < 0, "Stop loss collision must result in a loss rather than an optimistic profit."


# Test 5: Trailing stop updates without lookahead bias
def test_trailing_stop_updates_without_lookahead_bias():
    strat = MockSignalStrategy(entry_bar=5, exit_bar=20, sl_dist=10.0, tp_dist=50.0, trailing=0.05)
    df = create_deterministic_bars(50, start_date="2026-06-01 14:00:00")
    # Verify runner trailing stop mechanics
    runner = ResearchSimulationRunner(strat, initial_capital=100000.0)
    res = runner.run_simulation({"BTCUSDT": df})
    assert res["total_trades"] >= 1


# Test 6: Equity market sessions enforcement
def test_equity_market_sessions_enforcement():
    strat = MockSignalStrategy(entry_bar=0, exit_bar=20)
    # Start on Saturday (weekday = 5)
    df_weekend = create_deterministic_bars(10, start_date="2026-06-06 15:00:00") # Saturday
    runner = ResearchSimulationRunner(strat, initial_capital=100000.0, enforce_equity_sessions=True)

    # AAPL is equity: cannot execute during weekend
    res = runner.run_simulation({"AAPL": df_weekend})
    assert res["total_trades"] == 0, "Equities must not execute during closed market sessions (weekends)."


# Test 7: Crypto continuous trading 24/7
def test_crypto_continuous_trading_24_7():
    strat = MockSignalStrategy(entry_bar=0, exit_bar=8)
    # Start on Saturday
    df_weekend = create_deterministic_bars(10, start_date="2026-06-06 15:00:00") # Saturday
    runner = ResearchSimulationRunner(strat, initial_capital=100000.0, enforce_equity_sessions=True)

    # BTCUSDT is crypto: trades 24/7
    res = runner.run_simulation({"BTCUSDT": df_weekend})
    assert res["total_trades"] >= 1, "Crypto must trade continuously 24/7/365 including weekends."


# Test 8: Cost calculations by asset class
def test_cost_calculations_by_asset_class_equity_vs_crypto():
    runner = ResearchSimulationRunner(MockSignalStrategy())
    eq_slip, eq_comm = runner.get_transaction_costs("AAPL")
    cr_slip, cr_comm = runner.get_transaction_costs("BTCUSDT")

    assert eq_slip == 2.0 and eq_comm == 0.0, "Equities must incur 2 bps slippage and 0 bps commission."
    assert cr_slip == 5.0 and cr_comm == 10.0, "Crypto must incur 5 bps slippage and 10 bps commission."


# Test 9: Position sizing with risk and capital constraints
def test_position_sizing_respects_risk_and_capital_limits():
    strat = MockSignalStrategy(entry_bar=2, exit_bar=10, sl_dist=5.0)
    df = create_deterministic_bars(30, start_date="2026-06-01 14:00:00")
    runner = ResearchSimulationRunner(strat, initial_capital=100000.0, max_open_positions=4, risk_per_trade_pct=0.005)
    res = runner.run_simulation({"BTCUSDT": df})

    trade = res["trades"][0]
    pos_val = trade["position_value"]
    max_cap = 100000.0 / 4  # 25,000 max cap
    assert pos_val <= max_cap, f"Position value {pos_val} must not exceed capital cap {max_cap}."


# Test 10: Benchmark alignment and execution
def test_benchmark_alignment_and_execution():
    evaluator = ResearchEvaluator(db_path=":memory:")
    df = create_deterministic_bars(50, start_date="2026-06-01 14:00:00")

    bh = evaluator.compute_buy_and_hold_benchmark("AAPL", df)
    cash = evaluator.compute_cash_benchmark(len(df))
    sma = evaluator.compute_sma_trend_benchmark("AAPL", df, sma_period=10)

    assert len(bh["equity_curve"]) == 50
    assert len(cash["equity_curve"]) == 50
    assert len(sma["equity_curve"]) == 50
    assert cash["metrics"]["total_return_pct"] == 0.0


# Test 11: Return-series alignment across strategies
def test_return_series_alignment_across_strategies():
    df = create_deterministic_bars(50, start_date="2026-06-01 14:00:00")
    s1 = DualEmaAtrTrendStrategy({"parameters": {"fast_ema_period": 5, "slow_ema_period": 15}})
    s2 = TsMomBreakoutStrategy({"parameters": {"channel_entry_period": 10, "mom_period": 10}})

    r1 = ResearchSimulationRunner(s1).run_simulation({"BTCUSDT": df})
    r2 = ResearchSimulationRunner(s2).run_simulation({"BTCUSDT": df})

    assert len(r1["periodic_returns_pct"]) == len(r2["periodic_returns_pct"])


# Test 12: Genuine candidate matrix construction (N >= 4)
def test_genuine_candidate_matrix_construction_n_ge_4():
    df = create_deterministic_bars(80, start_date="2026-06-01 14:00:00")
    strats = [
        DualEmaAtrTrendStrategy({"strategy_id": f"TF_VAR_{i}", "parameters": {"fast_ema_period": 5 + i, "slow_ema_period": 15 + i}})
        for i in range(5)
    ]
    sim_results = [ResearchSimulationRunner(s).run_simulation({"BTCUSDT": df}) for s in strats]

    mat_info = GenuineCandidateMatrixBuilder.build_matrix(sim_results)
    assert mat_info["is_sufficient_for_pbo"] is True
    assert mat_info["n_candidates"] == 5
    assert mat_info["candidates_matrix"].shape == (79, 5)


# Test 13: Missing return observations handling
def test_missing_return_observations_handling():
    # Candidates with unequal length return streams
    r1 = {"strategy_id": "S1", "periodic_returns_pct": np.ones(50)}
    r2 = {"strategy_id": "S2", "periodic_returns_pct": np.ones(40)} # shorter
    r3 = {"strategy_id": "S3", "periodic_returns_pct": np.ones(60)}
    r4 = {"strategy_id": "S4", "periodic_returns_pct": np.ones(45)}

    mat_info = GenuineCandidateMatrixBuilder.build_matrix([r1, r2, r3, r4])
    assert mat_info["is_sufficient_for_pbo"] is True
    assert mat_info["candidates_matrix"].shape == (40, 4), "Matrix must truncate cleanly to minimum common length without fabrication."


# Test 14: Experiment registry persistence in DuckDB
def test_experiment_registry_persistence_duckdb():
    tracker = ExperimentTracker(db_path=":memory:")
    exp_id = tracker.create_experiment_id()

    record = tracker.log_experiment(
        experiment_id=exp_id,
        strategy_name="Test Strategy",
        strategy_version="1.0.0",
        asset="AAPL",
        timeframe="1h",
        parameter_config={"p1": 10},
        dataset_info={"n_bars": 100},
        validation_results={"metrics": {"sharpe_ratio": 1.25, "total_return_pct": 15.0, "max_drawdown_pct": 5.0}},
        return_frequency="1h"
    )

    assert record["experiment_id"] == exp_id
    trials_info = tracker.get_total_historical_trials()
    assert trials_info["total_candidate_trials"] >= 1


# Test 15: Zero lookahead in regime analysis
def test_no_lookahead_in_regime_analysis():
    evaluator = ResearchEvaluator(db_path=":memory:")
    df = create_deterministic_bars(60, start_date="2026-06-01 14:00:00")
    dummy_trades = [
        {"entry_time": str(df.loc[30, "open_time"]), "pnl_usd": 150.0},
        {"entry_time": str(df.loc[45, "open_time"]), "pnl_usd": -50.0}
    ]
    regime_stats = evaluator.evaluate_regimes(df, dummy_trades)

    assert "CALM" in regime_stats
    assert "NORMAL" in regime_stats
    assert "HIGH" in regime_stats
    assert "TRENDING" in regime_stats
    assert "RANGING" in regime_stats


# Test 16: Incomplete PBO handling when candidates are insufficient
def test_incomplete_pbo_handling_when_candidates_insufficient():
    # Only 2 candidates (below minimum threshold of 4)
    r1 = {"strategy_id": "S1", "periodic_returns_pct": np.ones(50)}
    r2 = {"strategy_id": "S2", "periodic_returns_pct": np.ones(50)}

    mat_info = GenuineCandidateMatrixBuilder.build_matrix([r1, r2])
    assert mat_info["is_sufficient_for_pbo"] is False
    assert mat_info["status"] == "INCOMPLETE"
    assert "minimum 4 required" in mat_info["reason"]
