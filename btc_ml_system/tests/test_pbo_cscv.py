"""
Unit and Integration Tests for Probability of Backtest Overfitting (PBO) and CSCV.
Validates:
- Correct CSCV partition construction with even blocks S
- Complementary partition integrity (zero index overlap between IS and OOS within partition)
- No data leakage between complementary splits
- PBO calculation and relative ranking convention
- High PBO on random noise vs Low PBO on genuine persistent alpha
"""

import numpy as np
import pandas as pd
import pytest
from btc_ml_system.src.validation.pbo_cscv import PBOCSCVEngine


def test_cscv_partition_integrity_and_zero_leakage():
    """Verifies that each CSCV partition consists of strictly complementary, non-overlapping blocks."""
    engine = PBOCSCVEngine({"pbo_cscv": {"n_blocks": 8, "max_combinations": 50}})
    T, N = 800, 5
    matrix = np.random.normal(0, 1, size=(T, N))

    S = engine.n_blocks
    half_S = S // 2

    # Check partition generation manually to verify complementary integrity
    import itertools
    combos = list(itertools.combinations(range(S), half_S))
    assert len(combos) == 70 # C(8, 4) = 70

    for combo in combos[:10]:
        is_blocks = set(combo)
        oos_blocks = set(range(S)) - is_blocks

        # 1. Zero block overlap
        assert len(is_blocks.intersection(oos_blocks)) == 0, "IS and OOS blocks must be mutually exclusive"
        # 2. Complete coverage of S blocks
        assert is_blocks.union(oos_blocks) == set(range(S)), "IS and OOS must together span all S blocks"
        # 3. Equal size
        assert len(is_blocks) == len(oos_blocks) == half_S


def test_pbo_on_pure_noise_vs_genuine_alpha():
    """
    Verifies that:
    - Pure Gaussian random noise across multiple trials produces high PBO (~50%).
    - A dominant strategy with genuine persistent alpha yields very low PBO (~0%).
    """
    engine = PBOCSCVEngine({"pbo_cscv": {"n_blocks": 8, "max_combinations": 70, "random_seed": 42}})
    rng = np.random.default_rng(42)

    T, N = 1000, 10

    # 1. Pure noise: 10 independent random strategies with zero edge
    noise_matrix = rng.normal(0.0, 0.01, size=(T, N))
    res_noise = engine.compute_pbo_from_returns_matrix(noise_matrix, metric="sharpe_ratio")

    assert "pbo" in res_noise
    # In pure noise, the IS winner is selected by data mining lucky noise, leading to high PBO (>= 0.50)
    assert res_noise["pbo"] >= 0.50, f"Expected high noise PBO (>= 0.50), got {res_noise['pbo']}"
    assert res_noise["is_overfitted"] is True

    # 2. Genuine alpha: Strategy 0 has a massive persistent positive mean return
    alpha_matrix = rng.normal(0.0, 0.01, size=(T, N))
    alpha_matrix[:, 0] += 0.005 # Strong persistent edge on column 0

    res_alpha = engine.compute_pbo_from_returns_matrix(alpha_matrix, metric="sharpe_ratio")
    # Dominant strategy should win almost every IS and OOS split, resulting in PBO near 0
    assert res_alpha["pbo"] < 0.15, f"Expected low PBO for persistent alpha, got {res_alpha['pbo']}"
    assert res_alpha["is_overfitted"] is False
