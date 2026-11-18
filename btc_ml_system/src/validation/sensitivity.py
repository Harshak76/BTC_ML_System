"""
Parameter Sensitivity and Stability Surface Engine for BTC-ML System V2.
Features:
- Grid Search and Random Search exploration over parameter spaces
- 1D sensitivity curves & 2D sensitivity surfaces / heatmaps
- Parameter stability score (penalizing sharp spikes and rewarding smooth plateaus)
- Regime-conditioned sensitivity analysis (CALM, NORMAL, HIGH)
- Strict preservation of the frozen baseline configuration
"""

import logging
from typing import Dict, Any, List, Tuple, Callable, Optional, Union
import itertools
import numpy as np
import pandas as pd

logger = logging.getLogger("btc_ml_system.validation.sensitivity")


class ParameterSensitivityEngine:
    """
    Evaluates strategy parameter robustness, stability surfaces, and regime consistency.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def grid_search(
        self,
        df: pd.DataFrame,
        param_grid: Dict[str, List[Any]],
        eval_fn: Callable[[pd.DataFrame, Dict[str, Any]], Dict[str, Any]],
        regime_col: Optional[str] = "volatility_regime"
    ) -> pd.DataFrame:
        """
        Executes full factorial grid search over parameter combinations.
        Returns DataFrame with parameters, overall metrics, and regime-partitioned metrics.
        """
        keys = list(param_grid.keys())
        combinations = list(itertools.product(*[param_grid[k] for k in keys]))
        logger.info(f"Starting parameter grid search over {len(combinations)} combinations across {keys}.")

        results = []
        for combo in combinations:
            params = dict(zip(keys, combo))
            metrics = eval_fn(df, params)

            record = dict(params)
            record["sharpe_ratio"] = metrics.get("sharpe_ratio", 0.0)
            record["total_return_pct"] = metrics.get("total_return_pct", 0.0)
            record["max_drawdown_pct"] = metrics.get("max_drawdown_pct", 0.0)
            record["win_rate"] = metrics.get("win_rate", 0.0)
            record["profit_factor"] = metrics.get("profit_factor", 1.0)
            record["total_trades"] = metrics.get("total_trades", 0)

            # Regime stability if regime column is present in df
            if regime_col and regime_col in df.columns:
                for reg in ["CALM", "NORMAL", "HIGH"]:
                    df_reg = df[df[regime_col] == reg]
                    if len(df_reg) > 20:
                        reg_metrics = eval_fn(df_reg, params)
                        record[f"ret_{reg.lower()}"] = reg_metrics.get("total_return_pct", 0.0)
                        record[f"sharpe_{reg.lower()}"] = reg_metrics.get("sharpe_ratio", 0.0)
                    else:
                        record[f"ret_{reg.lower()}"] = np.nan
                        record[f"sharpe_{reg.lower()}"] = np.nan

            results.append(record)

        df_results = pd.DataFrame(results)
        return df_results

    def random_search(
        self,
        df: pd.DataFrame,
        param_distributions: Dict[str, Union[List[Any], Tuple[float, float]]],
        eval_fn: Callable[[pd.DataFrame, Dict[str, Any]], Dict[str, Any]],
        n_iter: int = 50,
        random_seed: int = 42
    ) -> pd.DataFrame:
        """
        Executes randomized search across parameter distributions.
        """
        rng = np.random.default_rng(random_seed)
        results = []

        for _ in range(n_iter):
            params = {}
            for k, dist in param_distributions.items():
                if isinstance(dist, list):
                    params[k] = rng.choice(dist)
                elif isinstance(dist, tuple) and len(dist) == 2:
                    if isinstance(dist[0], int) and isinstance(dist[1], int):
                        params[k] = int(rng.integers(dist[0], dist[1] + 1))
                    else:
                        params[k] = float(rng.uniform(dist[0], dist[1]))
                else:
                    params[k] = dist

            metrics = eval_fn(df, params)
            rec = dict(params)
            rec["sharpe_ratio"] = metrics.get("sharpe_ratio", 0.0)
            rec["total_return_pct"] = metrics.get("total_return_pct", 0.0)
            rec["max_drawdown_pct"] = metrics.get("max_drawdown_pct", 0.0)
            rec["profit_factor"] = metrics.get("profit_factor", 1.0)
            rec["total_trades"] = metrics.get("total_trades", 0)
            results.append(rec)

        return pd.DataFrame(results)

    def compute_2d_surface(
        self,
        df_grid: pd.DataFrame,
        param_x: str,
        param_y: str,
        target_metric: str = "sharpe_ratio"
    ) -> pd.DataFrame:
        """
        Pivots grid search results into a 2D matrix / surface for heatmap visualization.
        """
        surface = df_grid.pivot(index=param_y, columns=param_x, values=target_metric)
        return surface

    def calculate_stability_score(
        self,
        df_grid: pd.DataFrame,
        param_x: str,
        param_y: Optional[str] = None,
        target_metric: str = "sharpe_ratio"
    ) -> float:
        """
        Calculates parameter stability score in [0.0, 1.0].
        High score indicates a broad, robust plateau.
        Low score indicates fragile, overfitted isolated spikes.
        Calculated as 1 - Coefficient of Variation (capped at 0).
        """
        vals = df_grid[target_metric].dropna().values
        if len(vals) < 3:
            return 0.0

        mean_val = np.mean(vals)
        std_val = np.std(vals)

        if mean_val <= 0:
            return 0.0

        cv = std_val / mean_val
        # Stability score: smooth surfaces have low CV, high stability score
        stability = max(0.0, min(1.0, 1.0 / (1.0 + cv)))
        return float(stability)
