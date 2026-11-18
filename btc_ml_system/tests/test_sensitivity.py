"""
Unit Tests for ParameterSensitivityEngine.
Validates:
- Full factorial grid search
- Randomized parameter distribution search
- 2D surface generation
- Stability score calculation (smooth plateau vs sharp spike)
"""

import pandas as pd
import numpy as np
import pytest
from btc_ml_system.src.validation.sensitivity import ParameterSensitivityEngine


def test_grid_search_and_surface_generation():
    """Verifies grid search exploration and 2D surface generation."""
    engine = ParameterSensitivityEngine()
    df_dummy = pd.DataFrame({"close": np.linspace(100, 110, 50)})

    param_grid = {
        "fast_ema": [9, 12, 15],
        "slow_ema": [21, 26, 30]
    }

    def mock_eval(df, params):
        f = params["fast_ema"]
        s = params["slow_ema"]
        sharpe = (s - f) / 10.0
        return {
            "sharpe_ratio": sharpe,
            "total_return_pct": sharpe * 5.0,
            "max_drawdown_pct": 2.0,
            "win_rate": 0.50,
            "profit_factor": 1.1,
            "total_trades": 20
        }

    df_results = engine.grid_search(df_dummy, param_grid, mock_eval)
    assert len(df_results) == 9, "Grid search over 3x3 should yield 9 combinations"
    assert "sharpe_ratio" in df_results.columns

    surface = engine.compute_2d_surface(df_results, "fast_ema", "slow_ema", "sharpe_ratio")
    assert surface.shape == (3, 3)
    assert surface.loc[21, 9] == pytest.approx((21 - 9) / 10.0)


def test_parameter_stability_score():
    """Verifies that smooth plateaus have high stability scores and sharp spikes have low scores."""
    engine = ParameterSensitivityEngine()

    # Broad plateau: consistent values around 1.5
    plateau_df = pd.DataFrame({"sharpe_ratio": [1.48, 1.50, 1.52, 1.49, 1.51]})
    score_plateau = engine.calculate_stability_score(plateau_df, "param_x")

    # Sharp isolated spike: 0.1, 0.1, 3.5, 0.1, 0.1
    spike_df = pd.DataFrame({"sharpe_ratio": [0.1, 0.1, 3.5, 0.1, 0.1]})
    score_spike = engine.calculate_stability_score(spike_df, "param_x")

    assert score_plateau > score_spike, (
        f"Plateau stability ({score_plateau:.2f}) must be significantly higher than spike stability ({score_spike:.2f})"
    )
    assert score_plateau >= 0.80
