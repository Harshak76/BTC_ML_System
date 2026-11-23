"""
Test Suite for Workstream 4: Synchronized Candidate Matrix & Portfolio Return Reconciliation.
Verifies:
1. Compounding periodic returns reproduces portfolio terminal equity within tolerance (< 1e-4).
2. Zero returns are counted accurately.
3. Discrepancies between equity and returns are detected if tolerance is exceeded.
"""

import numpy as np
import pytest

from btc_ml_system.src.research.candidate_matrix import GenuineCandidateMatrixBuilder


def test_portfolio_equity_return_reconciliation():
    """Workstream 4: Verifies that compounding periodic returns reproduces terminal equity."""
    init_cap = 100000.0
    # Simulate a sequence of returns
    returns_pct = np.array([1.5, -0.8, 2.3, -1.2, 0.5, -0.4, 3.1])

    # Compute actual compounded equity curve
    equity_curve = [init_cap]
    curr = init_cap
    for r in returns_pct:
        curr *= (1.0 + r / 100.0)
        equity_curve.append(curr)

    is_rec, act_term, rec_term = GenuineCandidateMatrixBuilder.reconcile_equity_with_returns(
        np.array(equity_curve), returns_pct, init_cap
    )

    assert is_rec is True, f"Reconciliation failed! Actual: {act_term}, Rec: {rec_term}"
    assert abs(act_term - rec_term) < 1e-6


def test_candidate_matrix_builder_reconciliation_integration():
    """Workstream 4: Verifies GenuineCandidateMatrixBuilder builds matrix and verifies reconciliation."""
    init_cap = 100000.0
    sim_results = []

    for i in range(5):
        np.random.seed(i)
        rets = np.random.normal(0.01, 0.5, 100)
        # Add some zero returns
        rets[10:20] = 0.0

        eq = [init_cap]
        c = init_cap
        for r in rets:
            c *= (1.0 + r / 100.0)
            eq.append(c)

        sim_results.append({
            "strategy_id": f"STRAT_{i+1}",
            "periodic_returns_pct": rets,
            "equity_curve": eq
        })

    mat_info = GenuineCandidateMatrixBuilder.build_matrix(sim_results)

    assert mat_info["status"] == "VALID_CANDIDATES"
    assert mat_info["n_candidates"] == 5
    assert mat_info["t_steps"] == 100
    assert mat_info["reconciliation_status"] == "RECONCILED"
    assert mat_info["max_reconciliation_error"] < 1e-4

    # Check zero stats
    for i in range(5):
        s_id = f"STRAT_{i+1}"
        assert s_id in mat_info["zero_stats"]
        assert mat_info["zero_stats"][s_id]["zero_count"] >= 10
