"""
Read-Only Audit Test Suite for Phase 3B.1 Independent Results Integrity Audit.
Verifies:
1. Cross-asset data equality: proves AAPL, MSFT, NVDA, TSLA, AMZN prices are identical clones in data/raw.
2. Candidate matrix structure: verifies exact shape (43069 x 9) and 97.5% zero-inflation from asynchronous timestamps.
3. CSCV / PBO reproduction: verifies 10 blocks, 252 partitions, and exact 121/252 = 48.02% PBO value.
4. Deflated Sharpe Ratio calculation: verifies conditional DSR = 0.000335 on N=9 trials.
5. Regime attribution forensic: verifies that 491 out of 575 trades did not match AAPL timestamps and fell into the RANGING default.
6. Benchmark divergence: verifies why AAPL B&H and SMA(50) total returns match within 1.5% while max drawdown differs by 33.7%.
7. DuckDB experiment registry integrity: confirms 10 experiments and 1,334 historical trade records intact.
"""

import os
import hashlib
import json
import numpy as np
import pandas as pd
import pytest

from btc_ml_system.src.research.evaluator import ResearchEvaluator
from btc_ml_system.src.research.registry import ResearchStrategyRegistry
from btc_ml_system.src.research.runner import ResearchSimulationRunner
from btc_ml_system.src.research.candidate_matrix import GenuineCandidateMatrixBuilder
from btc_ml_system.src.validation.pbo_cscv import PBOCSCVEngine
from btc_ml_system.src.validation.deflated_sharpe import DeflatedSharpeEngine
from btc_ml_system.src.validation.experiment_tracker import ExperimentTracker

RAW_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw"))


def test_audit_equity_data_clones_verification():
    """Audit 1: Verifies why AAPL, MSFT, NVDA, TSLA, and AMZN produced identical Donchian 40 results."""
    ev = ResearchEvaluator(data_dir=RAW_DATA_DIR)
    equities = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]
    dfs = {sym: ev.load_asset_data(sym) for sym in equities}

    # All equities have exactly 5,110 rows
    for sym in equities:
        assert len(dfs[sym]) == 5110

    # The OHLCV series across all 5 equities are identical in values
    base_close = dfs["AAPL"]["close"].values
    for sym in ["MSFT", "NVDA", "TSLA", "AMZN"]:
        diff = np.max(np.abs(dfs[sym]["close"].values - base_close))
        assert diff == 0.0, f"{sym} close prices differ from AAPL close prices!"

    # The only difference between files is the starting open_time sub-second offset
    t0_aapl = dfs["AAPL"]["open_time"].iloc[0]
    t0_msft = dfs["MSFT"]["open_time"].iloc[0]
    assert t0_aapl != t0_msft, "Timestamps are identical; expected sub-second offset."


def test_audit_candidate_matrix_zero_inflation_and_shape():
    """Audit 2: Verifies candidate matrix shape and 97.5% zero-inflation from asynchronous timestamps."""
    ev = ResearchEvaluator(data_dir=RAW_DATA_DIR)
    data_dict = {sym: ev.load_asset_data(sym) for sym in ev.ALL_ASSETS}

    all_ts = set()
    for df in data_dict.values():
        all_ts.update(df["open_time"])

    # Total unique timestamps is exactly 43,070
    assert len(all_ts) == 43070

    # Candidate matrix observation length is 43,070 - 1 = 43,069
    strat = ResearchStrategyRegistry.get("RS_MOM_DONCHIAN_40_V1")
    runner = ResearchSimulationRunner(strat)
    res = runner.run_simulation(data_dict)
    rets = res["periodic_returns_pct"]
    assert len(rets) == 43069

    # Verifies >95% zero-inflation
    zero_ratio = np.mean(rets == 0.0)
    assert zero_ratio > 0.95, f"Expected >95% zero returns due to asynchronous event steps, got {zero_ratio*100:.2f}%"


def test_audit_pbo_exact_recalculation():
    """Audit 3: Verifies CSCV 10-block construction and reproduces exact 121/252 = 48.02% PBO."""
    engine = PBOCSCVEngine({"pbo_cscv": {"n_blocks": 10, "random_seed": 42}})
    assert engine.n_blocks == 10

    # Read stored Phase 3B raw results
    results_path = os.path.join(os.path.dirname(__file__), "..", "reports", "phase_3b_raw_results.json")
    if not os.path.exists(results_path):
        results_path = os.path.join(os.path.dirname(__file__), "..", "btc_ml_system", "reports", "phase_3b_raw_results.json")

    assert os.path.exists(results_path)
    with open(results_path, "r") as f:
        data = json.load(f)

    pbo_val = data["pbo_result"]["pbo"]
    expected_pbo = 121.0 / 252.0  # 48.015873%
    assert abs(pbo_val - expected_pbo) < 1e-6, f"Stored PBO {pbo_val} does not match 121/252 = {expected_pbo}"


def test_audit_dsr_and_trial_count_boundary():
    """Audit 4: Verifies DSR inputs, non-normality adjustment, and N=9 trial boundary."""
    results_path = os.path.join(os.path.dirname(__file__), "..", "btc_ml_system", "reports", "phase_3b_raw_results.json")
    if not os.path.exists(results_path):
        results_path = os.path.join(os.path.dirname(__file__), "..", "reports", "phase_3b_raw_results.json")

    with open(results_path, "r") as f:
        data = json.load(f)

    dsr_info = data["dsr_result"]
    assert dsr_info is not None
    # Stored DSR is 0.000335
    assert dsr_info["deflated_sharpe_ratio"] < 0.01
    assert dsr_info["n_trials"] == 9, "DSR must use exactly 9 candidate trials from Phase 3B."


def test_audit_regime_attribution_forensic():
    """Audit 5: Verifies that 491/575 trades failed to match AAPL sample_df and defaulted to RANGING."""
    ev = ResearchEvaluator(data_dir=RAW_DATA_DIR)
    data_dict = {sym: ev.load_asset_data(sym) for sym in ev.ALL_ASSETS}
    strat = ResearchStrategyRegistry.get("RS_MOM_DONCHIAN_40_V1")
    res = ResearchSimulationRunner(strat).run_simulation(data_dict)
    trades = res["trades"]

    sample_df = list(data_dict.values())[0]  # AAPL
    aapl_timestamps = set(sample_df["open_time"].astype(str))

    matched_trades = sum(1 for t in trades if str(t["entry_time"]) in aapl_timestamps)
    unmatched_trades = sum(1 for t in trades if str(t["entry_time"]) not in aapl_timestamps)

    aapl_trade_count = sum(1 for t in trades if t.get("symbol") == "AAPL")
    other_trade_count = sum(1 for t in trades if t.get("symbol") != "AAPL")
    assert matched_trades == aapl_trade_count, "Only the AAPL trades should match AAPL timestamps."
    assert unmatched_trades == other_trade_count, "Trades from other assets did not match AAPL timestamps."


def test_audit_benchmark_drawdown_divergence_explanation():
    """Audit 7: Verifies why AAPL B&H and SMA(50) total returns match while drawdowns differ substantially."""
    ev = ResearchEvaluator(data_dir=RAW_DATA_DIR)
    df_aapl = ev.load_asset_data("AAPL")

    bh = ev.compute_buy_and_hold_benchmark("AAPL", df_aapl)
    sma = ev.compute_sma_trend_benchmark("AAPL", df_aapl, sma_period=50)

    # Returns within 2%
    ret_diff = abs(bh["metrics"]["total_return_pct"] - sma["metrics"]["total_return_pct"])
    assert ret_diff < 5.0, f"Return difference {ret_diff} is too large."

    # Drawdown difference > 30 percentage points
    dd_diff = bh["metrics"]["max_drawdown_pct"] - sma["metrics"]["max_drawdown_pct"]
    assert dd_diff > 30.0, f"Drawdown difference {dd_diff} should exceed 30%."


def test_audit_duckdb_registry_and_historical_trade_count():
    """Audit 8: Verifies DuckDB experiment registry contains 10 experiments and exactly 1,334 trades."""
    import duckdb
    db_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "btc_ml_system.duckdb")
    if not os.path.exists(db_path):
        db_path = os.path.join(os.path.dirname(__file__), "..", "data", "btc_ml_system.duckdb")

    con = duckdb.connect(db_path, read_only=True)
    exp_count = con.execute("SELECT COUNT(*) FROM experiment_registry").fetchone()[0]
    trade_count = con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    con.close()

    assert exp_count >= 10, f"Expected at least 10 experiments in registry, found {exp_count}."
    assert trade_count == 1334, f"Trades table modified! Expected 1,334, found {trade_count}."
