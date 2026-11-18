"""
Unit Tests for BootstrapEngine.
Validates:
- Trade-return IID bootstrap resampling
- Moving block bootstrap
- Stationary bootstrap (geometric random block lengths)
- Confidence intervals and reproducibility with fixed seed
- Risk of ruin computation
"""

import numpy as np
import pytest
from btc_ml_system.src.validation.bootstrap import BootstrapEngine


@pytest.fixture
def sample_trade_history():
    """Generates synthetic trades with known positive expectancy."""
    rng = np.random.default_rng(42)
    trades = []
    for _ in range(100):
        # 55% win rate, win = $50, loss = -$40
        if rng.uniform(0, 1) < 0.55:
            pnl = 50.0 + rng.normal(0, 5)
        else:
            pnl = -40.0 + rng.normal(0, 5)
        trades.append({"pnl_usd": pnl, "pnl": pnl})
    return trades


def test_trade_iid_bootstrap(sample_trade_history):
    """Verifies trade IID bootstrap calculations, confidence intervals, and reproducibility."""
    engine = BootstrapEngine({"bootstrap": {"n_iterations": 500, "random_seed": 123}})

    res1 = engine.trade_bootstrap(sample_trade_history, initial_capital=10000.0)
    res2 = engine.trade_bootstrap(sample_trade_history, initial_capital=10000.0)

    # Reproducibility check with identical seed
    assert res1["mean_return_pct"] == pytest.approx(res2["mean_return_pct"])
    assert res1["mean_win_rate"] == pytest.approx(res2["mean_win_rate"])
    assert res1["ci_95_return"] == res2["ci_95_return"]

    # Plausibility checks
    assert res1["mean_win_rate"] == pytest.approx(0.55, abs=0.05)
    assert res1["ci_95_return"][0] < res1["mean_return_pct"] < res1["ci_95_return"][1]
    assert 0.0 <= res1["prob_negative_return"] <= 1.0
    assert 0.0 <= res1["prob_ruin_pct"] <= 100.0


def test_block_and_stationary_bootstrap():
    """Verifies block and stationary bootstrap on returns series."""
    engine = BootstrapEngine({"bootstrap": {"n_iterations": 200, "random_seed": 99}})
    returns = np.random.normal(0.0005, 0.01, 300)

    block_res = engine.block_bootstrap(returns, block_size=12)
    assert "mean_cum_return_pct" in block_res
    assert "ci_95_cum_return" in block_res

    stat_res = engine.stationary_bootstrap(returns, expected_block_size=12)
    assert "mean_cum_return_pct" in stat_res
    assert "ci_95_cum_return" in stat_res
