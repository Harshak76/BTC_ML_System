"""
Unit Tests for ValidationGate.
Validates:
- Multi-criteria gate evaluation
- Correct classification of PASS, FAIL, and REQUIRES_APPROVAL
- Hard rejection when risk thresholds are breached
"""

import pytest
from btc_ml_system.src.validation.validation_gate import ValidationGate


def test_validation_gate_pass_scenario():
    """Verifies that a robust, statistically significant strategy passes the gate."""
    gate = ValidationGate()

    metrics = {"total_trades": 50, "total_return_pct": 12.0, "sharpe_ratio": 1.5, "max_drawdown_pct": 4.5}
    wf_res = {"consistency_ratio": 0.75}
    sens_res = {"stability_score": 0.85}
    oos_res = {"out_of_sample": {"total_return_pct": 4.0, "max_drawdown_pct": 3.5, "profit_factor": 1.4}}
    bs_res = {"prob_negative_return": 0.05}
    mc_res = {"randomized_ordering": {"percentile_95_max_dd_pct": 6.0}}
    cost_res = {"total_return_pct": 8.0}
    pbo_res = {"pbo": 0.15}
    dsr_res = {"deflated_sharpe_ratio": 0.92}

    res = gate.evaluate_gate(
        metrics=metrics,
        walk_forward_res=wf_res,
        sensitivity_res=sens_res,
        bootstrap_res=bs_res,
        monte_carlo_res=mc_res,
        oos_res=oos_res,
        pbo_res=pbo_res,
        dsr_res=dsr_res,
        cost_stress_res=cost_res
    )

    assert res["overall_status"] == "CERTIFIED_FOR_PAPER_TRADING"
    assert res["passed"] is True
    assert res["requires_approval"] is False


def test_validation_gate_fail_on_drawdown_or_pbo():
    """Verifies gate rejection when drawdown or PBO exceeds limits."""
    gate = ValidationGate()

    # Breaching Max Drawdown in Monte Carlo (14.0% > 10.0%) and high PBO (0.65 > 0.50)
    metrics = {"total_trades": 50}
    mc_res = {"randomized_ordering": {"percentile_95_max_dd_pct": 14.0}}
    pbo_res = {"pbo": 0.65}

    res = gate.evaluate_gate(
        metrics=metrics,
        monte_carlo_res=mc_res,
        pbo_res=pbo_res
    )

    assert res["overall_status"] == "REJECTED"
    assert res["passed"] is False


def test_validation_gate_requires_operator_approval():
    """Verifies that borderline DSR triggers REQUIRES_OPERATOR_APPROVAL."""
    gate = ValidationGate({"validation_gate": {"min_dsr": 0.80, "dsr_warning_threshold": 0.70}})

    metrics = {"total_trades": 50}
    # DSR is 0.74 (between warning 0.70 and pass 0.80)
    dsr_res = {"deflated_sharpe_ratio": 0.74}

    res = gate.evaluate_gate(
        metrics=metrics,
        dsr_res=dsr_res
    )

    assert res["overall_status"] == "REQUIRES_OPERATOR_APPROVAL"
    assert res["requires_approval"] is True
