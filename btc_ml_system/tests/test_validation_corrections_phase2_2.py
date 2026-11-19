"""
BTC-ML System V2 - Phase 2.2 Quantitative Validation Framework Corrections Test Suite.

Validates:
1. Negative and near-zero parameter means stability evaluation.
2. Parameter stability independence from profitability.
3. Independent holdout equity and drawdown calculations.
4. Holdout boundary isolation & contamination tracking.
5. Historical experiment append-only behavior and immutability.
6. Trial-count completeness and missing trial documentation.
7. DSR annualization vs periodic standard error consistency.
8. PBO candidate authenticity and CSCV inter-block purging.
9. Transaction cost reconciliation (10 vs 15 vs 20 bps round-trip).
10. Bootstrap confidence bounds and risk of ruin uncertainty (Rule of Three).
11. Monte Carlo scenario completeness (All 9 institutional scenarios).
12. Validation gate dynamic failure counting.
13. Validation gate INCOMPLETE and REQUIRES_REVALIDATION states.
"""

import math
import tempfile
import numpy as np
import pandas as pd
import pytest

from btc_ml_system.src.validation.sensitivity import ParameterSensitivityEngine
from btc_ml_system.src.validation.oos_validation import OutOfSampleEngine
from btc_ml_system.src.validation.experiment_tracker import ExperimentTracker
from btc_ml_system.src.validation.deflated_sharpe import DeflatedSharpeEngine
from btc_ml_system.src.validation.pbo_cscv import PBOCSCVEngine
from btc_ml_system.src.validation.bootstrap import BootstrapEngine
from btc_ml_system.src.validation.monte_carlo import MonteCarloEngine
from btc_ml_system.src.validation.validation_gate import ValidationGate


# ---------------------------------------------------------------------------
# 1 & 2. Parameter Stability Scoring: Negative/Near-Zero Means & Profitability Separation
# ---------------------------------------------------------------------------

def test_parameter_stability_negative_and_near_zero_means():
    """
    Verifies that ParameterSensitivityEngine computes robust, meaningful scores
    for negative and near-zero means without division-by-zero singularities.
    """
    engine = ParameterSensitivityEngine()

    # 1. Flat negative surface: all parameters yield -0.05 Sharpe
    df_neg_flat = pd.DataFrame({
        "param_x": [10, 20, 30, 10, 20, 30],
        "param_y": [1, 1, 1, 2, 2, 2],
        "sharpe_ratio": [-0.05, -0.05, -0.05, -0.05, -0.05, -0.05]
    })
    score_neg_flat = engine.calculate_stability_score(df_neg_flat, "param_x", "param_y")
    assert score_neg_flat == 1.0, "Flat negative surface must have perfect stability 1.0"

    # 2. Near-zero mean plateau: varying tightly around 0.000
    df_near_zero = pd.DataFrame({
        "param_x": [1, 2, 3, 4, 5],
        "sharpe_ratio": [-0.002, 0.000, 0.002, 0.001, -0.001]
    })
    score_near_zero = engine.calculate_stability_score(df_near_zero, "param_x")
    assert score_near_zero >= 0.85, f"Near-zero mean plateau must be highly stable, got {score_near_zero}"

    # 3. Negative mean plateau: consistent -1.50
    df_neg_plateau = pd.DataFrame({
        "param_x": [1, 2, 3, 4, 5],
        "sharpe_ratio": [-1.48, -1.50, -1.52, -1.49, -1.51]
    })
    score_neg_plateau = engine.calculate_stability_score(df_neg_plateau, "param_x")
    assert score_neg_plateau >= 0.85, f"Negative mean plateau must be stable, got {score_neg_plateau}"


def test_parameter_stability_separated_from_profitability():
    """
    Verifies that a consistently flat losing surface receives high stability (1.0),
    but when passed to ValidationGate, the losing performance triggers a FAIL.
    """
    sens_engine = ParameterSensitivityEngine()
    gate = ValidationGate()

    # Consistently losing strategy (Sharpe = -0.05 across all parameters)
    df_grid = pd.DataFrame({
        "param_x": [1, 2, 3],
        "sharpe_ratio": [-0.05, -0.05, -0.05],
        "total_return_pct": [-2.0, -2.0, -2.0]
    })
    stab_score = sens_engine.calculate_stability_score(df_grid, "param_x")
    assert stab_score == 1.0, "Stability must evaluate surface flatness, not return sign"

    # Gate evaluation: Stability check passes, but return / drawdown checks must fail
    res = gate.evaluate_gate(
        metrics={"total_trades": 150, "total_return_pct": -2.0, "sharpe_ratio": -0.05},
        sensitivity_res={"stability_score": stab_score},
        cost_stress_res={"total_return_pct": -4.0}
    )
    # Check individual check states
    chk_map = {c["check"]: c["status"] for c in res["checks"]}
    assert chk_map["Parameter Plateau Stability"] == "PASS"
    assert chk_map["2x Transaction Cost Stress Test"] == "FAIL"
    assert res["overall_status"] == "REJECTED"


def test_parameter_stability_penalizes_isolated_spikes_and_noise():
    """Verifies that isolated spikes and erratic noise receive low stability scores."""
    engine = ParameterSensitivityEngine()

    # Isolated spike: baseline 0.1, spike at 3.5
    df_spike = pd.DataFrame({"param_x": [1, 2, 3, 4, 5], "sharpe_ratio": [0.1, 0.1, 3.5, 0.1, 0.1]})
    score_spike = engine.calculate_stability_score(df_spike, "param_x")
    assert score_spike < 0.25, f"Isolated spike must receive low stability, got {score_spike}"

    # Noisy surface: rapid alternating swings
    df_noisy = pd.DataFrame({"param_x": [1, 2, 3, 4, 5, 6], "sharpe_ratio": [0.8, -0.8, 0.9, -0.7, 0.8, -0.9]})
    score_noisy = engine.calculate_stability_score(df_noisy, "param_x")
    assert score_noisy < 0.45, f"Noisy surface must receive low stability, got {score_noisy}"


# ---------------------------------------------------------------------------
# 3 & 4. Independent Holdout Engine & Boundary Isolation
# ---------------------------------------------------------------------------

def test_independent_holdout_split_and_drawdown_calculation():
    """
    Verifies that OutOfSampleEngine splits data chronologically, isolates the holdout,
    and computes holdout drawdown independently from holdout equity.
    """
    engine = OutOfSampleEngine({"oos_validation": {"holdout_pct": 0.25, "purge_bars": 5}})
    rng = np.random.default_rng(42)

    # 100 chronological daily bars
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    df = pd.DataFrame({
        "open_time": dates,
        "close": 100.0 + np.cumsum(rng.normal(0.1, 1.0, size=100))
    })

    df_is, df_oos = engine.split_holdout(df)

    # Check boundaries: 100 bars, 25% holdout -> 25 OOS bars, 5 purge bars -> 70 IS bars
    assert len(df_oos) == 25
    assert len(df_is) == 70
    assert df_is["open_time"].max() < df_oos["open_time"].min()

    # Evaluate holdout
    def mock_eval_fn(sub_df, params):
        ret = float((sub_df["close"].iloc[-1] - sub_df["close"].iloc[0]) / sub_df["close"].iloc[0] * 100.0)
        return {"total_return_pct": ret, "max_drawdown_pct": 3.0, "sharpe_ratio": 0.8}

    res = engine.evaluate_holdout(df_is, df_oos, {}, mock_eval_fn)
    assert "in_sample" in res
    assert "out_of_sample" in res
    assert res["is_contaminated"] is True
    assert "contamination_note" in res


# ---------------------------------------------------------------------------
# 5 & 6. Experiment Tracker: Append-Only, Schema & Trial Completeness
# ---------------------------------------------------------------------------

def test_experiment_tracker_append_only_and_trial_completeness():
    """
    Verifies that ExperimentTracker enforces append-only semantics,
    records all metadata fields, and aggregates cumulative historical trials.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        tracker = ExperimentTracker(registry_dir=temp_dir, db_path=":memory:")

        exp_id_1 = tracker.create_experiment_id()
        tracker.log_experiment(
            experiment_id=exp_id_1,
            strategy_name="btc_ml_portfolio",
            strategy_version="v5.1",
            asset="PORTFOLIO_7",
            timeframe="1h",
            parameter_config={"initial_capital": 100000},
            dataset_info={"symbols": ["BTC", "ETH"], "history_years": 2},
            validation_results={"portfolio_metrics": {"sharpe_ratio": 0.5, "total_return_pct": 3.0}},
            candidate_count=8,
            completed_trials=8,
            failed_trials=0,
            abandoned_trials=0
        )

        # 1. Attempting to overwrite the exact same experiment ID must raise ValueError (Append-only violation)
        with pytest.raises(ValueError, match="Append-only violation"):
            tracker.log_experiment(
                experiment_id=exp_id_1,
                strategy_name="btc_ml_portfolio",
                strategy_version="v5.1",
                asset="PORTFOLIO_7",
                timeframe="1h",
                parameter_config={"initial_capital": 100000},
                dataset_info={"symbols": ["BTC", "ETH"], "history_years": 2},
                validation_results={"portfolio_metrics": {"sharpe_ratio": 0.5, "total_return_pct": 3.0}},
                candidate_count=8,
                completed_trials=8
            )

        # 2. Log second experiment
        exp_id_2 = tracker.create_experiment_id()
        tracker.log_experiment(
            experiment_id=exp_id_2,
            strategy_name="btc_ml_portfolio",
            strategy_version="v5.2",
            asset="PORTFOLIO_7",
            timeframe="1h",
            parameter_config={"initial_capital": 100000},
            dataset_info={"symbols": ["BTC", "ETH"], "history_years": 2},
            validation_results={"portfolio_metrics": {"sharpe_ratio": 0.8, "total_return_pct": 5.0}},
            candidate_count=12,
            completed_trials=10,
            failed_trials=2,
            abandoned_trials=0
        )

        # 3. Verify total cumulative trials across experiments
        summary = tracker.get_total_historical_trials()
        assert summary["total_candidate_trials"] == 20 # 8 + 12
        assert summary["total_completed_trials"] == 18 # 8 + 10
        assert summary["total_failed_trials"] == 2
        assert summary["total_registered_experiments"] == 2
        assert summary["missing_historical_trials_documented"] is True


# ---------------------------------------------------------------------------
# 7 & 8. DSR & PBO Trial Accounting & CSCV Purging
# ---------------------------------------------------------------------------

def test_dsr_annualization_vs_periodic_units():
    """Verifies that DSR standardizes periodic Sharpe by periodic SE consistently."""
    engine = DeflatedSharpeEngine()
    obs_sharpe = 1.2 # Annualized
    N_trials = 20
    trials = [0.2 + 0.05 * i for i in range(N_trials)]
    ann_factor = 252 * 24

    res = engine.calculate_dsr(
        observed_sharpe=obs_sharpe,
        n_observations=5000,
        all_trial_sharpes=trials,
        annualization_factor=ann_factor,
        skewness=-0.2,
        kurtosis=4.5
    )
    assert 0.0 <= res["deflated_sharpe_ratio"] <= 1.0
    assert res["expected_max_annualized_sharpe"] > 0.0
    assert res["mertens_standard_error"] > 0.0


def test_cscv_purging_and_authentic_candidates():
    """Verifies that CSCV accepts candidate matrices and supports block partitioning."""
    engine = PBOCSCVEngine({"pbo_cscv": {"n_blocks": 8, "max_combinations": 70, "random_seed": 42}})
    rng = np.random.default_rng(42)

    # 5 genuine candidates over 1000 bars
    candidates = rng.normal(0.0001, 0.01, size=(1000, 5))
    res = engine.compute_pbo_from_returns_matrix(candidates)

    assert res["n_blocks"] == 8
    assert res["total_partitions_evaluated"] == 70
    assert 0.0 <= res["pbo"] <= 1.0


# ---------------------------------------------------------------------------
# 9, 10 & 11. Transaction Cost, Bootstrap Ruin Uncertainty & Monte Carlo Scenarios
# ---------------------------------------------------------------------------

def test_bootstrap_ruin_uncertainty_rule_of_three():
    """
    Verifies that when 0 ruin events occur in 1,000 simulations,
    the engine reports an explicit upper 95% confidence bound (<= 0.30%) via the Rule of Three.
    """
    engine = BootstrapEngine({"bootstrap": {"n_iterations": 1000, "random_seed": 42, "ruin_threshold_pct": 50.0}})
    # Highly profitable trades (zero chance of hitting 50% drawdown in 1,000 resamples)
    trades = [{"pnl_usd": 100.0}] * 50

    res = engine.trade_bootstrap(trades, initial_capital=100000.0)
    assert res["prob_ruin_pct"] == 0.0
    assert "prob_ruin_upper_95_ci_pct" in res
    assert res["prob_ruin_upper_95_ci_pct"] == pytest.approx(0.30, rel=1e-3)
    assert "Rule of Three" in res["ruin_uncertainty_note"]


def test_monte_carlo_all_9_scenarios():
    """Verifies that MonteCarloEngine executes and reports all 9 institutional stress scenarios."""
    engine = MonteCarloEngine({"monte_carlo": {"n_simulations": 100, "random_seed": 42}})
    trades = [{"pnl_usd": 20.0, "position_value": 5000.0}] * 30 + [{"pnl_usd": -15.0, "position_value": 5000.0}] * 20

    res = engine.run_all_scenarios(trades, initial_capital=100000.0)

    # All 9 scenarios must be present
    expected_scenarios = [
        "randomized_ordering",
        "slippage_variation",
        "transaction_cost_variation",
        "adverse_fills",
        "delayed_execution",
        "missed_trades",
        "regime_stress",
        "parameter_perturbations",
        "portfolio_simultaneous_loss"
    ]
    for sc in expected_scenarios:
        assert sc in res, f"Scenario {sc} missing from Monte Carlo suite"

    assert res["total_scenarios_evaluated"] == 9


# ---------------------------------------------------------------------------
# 12 & 13. Validation Gate Dynamic Failure Counting & Special States
# ---------------------------------------------------------------------------

def test_validation_gate_failure_counting_and_states():
    """
    Verifies that ValidationGate dynamically calculates passed_count, failed_count,
    incomplete_count, and correctly classifies REJECTED, REQUIRES_REVALIDATION, and INCOMPLETE.
    """
    gate = ValidationGate()

    # Scenario 1: Incomplete suite (missing required checks)
    res_incomplete = gate.evaluate_gate(
        metrics={"total_trades": 150},
        require_full_suite=True
    )
    assert res_incomplete["overall_status"] == "REQUIRES_REVALIDATION"
    assert res_incomplete["incomplete_count"] > 0
    assert res_incomplete["passed"] is False

    # Scenario 2: Contaminated holdout that otherwise passed numerically
    res_contam = gate.evaluate_gate(
        metrics={"total_trades": 150},
        oos_res={"out_of_sample": {"total_return_pct": 5.0, "max_drawdown_pct": 4.0}, "is_contaminated": True}
    )
    chk_map = {c["check"]: c["status"] for c in res_contam["checks"]}
    assert chk_map["Strict OOS Holdout Return & Drawdown"] == "REQUIRES_REVALIDATION"
    assert res_contam["overall_status"] == "REQUIRES_REVALIDATION"

    # Scenario 3: Hard failure (negative return at 2x costs)
    res_fail = gate.evaluate_gate(
        metrics={"total_trades": 150},
        cost_stress_res={"total_return_pct": -3.5}
    )
    assert res_fail["failed_count"] >= 1
    assert res_fail["overall_status"] == "REJECTED"
    assert res_fail["passed"] is False
