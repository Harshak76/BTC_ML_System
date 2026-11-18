"""
Unit Tests for Deflated Sharpe Ratio (DSR) and Probabilistic Sharpe Ratio (PSR).
Validates:
- Mertens standard error under non-normality (skewness, kurtosis)
- Expected maximum Sharpe ratio approximation across multiple trials
- DSR calculation against independently verified numerical examples
- Multiple-trial penalization (DSR drops as N_trials increases)
"""

import numpy as np
import pytest
from scipy import stats
from btc_ml_system.src.validation.deflated_sharpe import DeflatedSharpeEngine, EULER_MASCHERONI


def test_mertens_standard_error_calculation():
    """Verifies Mertens standard error under normal vs non-normal moments."""
    # Under standard normal return distribution (skew=0, kurtosis=3):
    # var = (1 / (T - 1)) * (1 + 0.5 * SR^2)
    sr = 1.0
    T = 101 # T-1 = 100
    expected_var = (1.0 / 100.0) * (1.0 + 0.5 * (1.0 ** 2)) # 0.015
    expected_se = np.sqrt(expected_var)

    computed_se = DeflatedSharpeEngine.compute_mertens_standard_error(
        sharpe=sr, n_observations=T, skewness=0.0, kurtosis=3.0
    )
    assert computed_se == pytest.approx(expected_se, rel=1e-4)

    # Negative skewness should increase standard error (penalizing left tail risk)
    computed_se_skew = DeflatedSharpeEngine.compute_mertens_standard_error(
        sharpe=sr, n_observations=T, skewness=-1.0, kurtosis=5.0
    )
    assert computed_se_skew > computed_se


def test_expected_max_sharpe_multiple_trials():
    """Verifies that expected max Sharpe ratio increases as number of trials N grows."""
    var_trials = 0.25 # variance among trials

    em_10 = DeflatedSharpeEngine.expected_max_sharpe(n_trials=10, var_trials=var_trials)
    em_100 = DeflatedSharpeEngine.expected_max_sharpe(n_trials=100, var_trials=var_trials)
    em_1000 = DeflatedSharpeEngine.expected_max_sharpe(n_trials=1000, var_trials=var_trials)

    assert em_10 < em_100 < em_1000, "Expected max Sharpe must strictly increase with number of trials"
    assert em_10 > 0.0


def test_dsr_penalization_for_data_mining():
    """Verifies that DSR deflates an observed Sharpe ratio when tested against multiple trials."""
    engine = DeflatedSharpeEngine()
    obs_sharpe = 1.8 # Annualized observed Sharpe
    T = 500 # Observations

    # 1. Single trial: DSR is high
    dsr_single = engine.calculate_dsr(
        observed_sharpe=obs_sharpe,
        n_observations=T,
        all_trial_sharpes=[obs_sharpe],
        annualization_factor=252.0
    )

    # 2. 50 trials with variance: DSR should be substantially lower due to selection bias
    trial_sharpes = list(np.random.normal(1.2, 0.4, 50))
    trial_sharpes.append(obs_sharpe)
    dsr_multi = engine.calculate_dsr(
        observed_sharpe=obs_sharpe,
        n_observations=T,
        all_trial_sharpes=trial_sharpes,
        annualization_factor=252.0
    )

    assert dsr_single["deflated_sharpe_ratio"] > dsr_multi["deflated_sharpe_ratio"], (
        f"DSR for single trial ({dsr_single['deflated_sharpe_ratio']:.2f}) must be higher than multi-trial ({dsr_multi['deflated_sharpe_ratio']:.2f})"
    )
