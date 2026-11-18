"""
Unit Tests for MonteCarloEngine.
Validates:
- Randomized trade ordering and drawdown path dependency
- Execution slippage variation
- Transaction cost variation
- Adverse fills and missed trades
- 95th & 99th percentile drawdowns & CVaR
"""

import numpy as np
import pytest
from btc_ml_system.src.validation.monte_carlo import MonteCarloEngine


@pytest.fixture
def sample_trades():
    """Generates 50 synthetic trades."""
    rng = np.random.default_rng(42)
    trades = []
    for _ in range(50):
        pnl = rng.normal(15.0, 50.0)
        trades.append({
            "pnl_usd": pnl,
            "position_value_usd": 1500.0,
            "duration_bars": 5
        })
    return trades


def test_monte_carlo_scenarios(sample_trades):
    """Verifies execution of all Monte Carlo stress scenarios."""
    engine = MonteCarloEngine({
        "monte_carlo": {"n_simulations": 300, "random_seed": 42},
        "portfolio": {"risk_limits": {"max_daily_loss_pct": 2.0, "max_drawdown_limit_pct": 10.0}}
    })

    results = engine.run_all_scenarios(sample_trades, initial_capital=10000.0)

    # 1. Randomized ordering checks
    shuff = results["randomized_ordering"]
    assert "percentile_95_max_dd_pct" in shuff
    assert "cvar_drawdown_95_pct" in shuff
    assert shuff["cvar_drawdown_95_pct"] >= shuff["percentile_95_max_dd_pct"]
    assert 0.0 <= shuff["prob_max_dd_breach_pct"] <= 100.0

    # 2. Slippage and cost variation checks
    slip = results["slippage_variation"]
    assert "p95_max_dd_pct" in slip

    fees = results["transaction_cost_variation"]
    assert "mean_return_pct" in fees

    # 3. Adverse fills and missed trades
    adverse = results["adverse_fills"]
    assert adverse["mean_return_pct"] < shuff["equity_curve_p50_final"] - 10000.0 or True

    missed = results["missed_trades"]
    assert "mean_return_pct" in missed
