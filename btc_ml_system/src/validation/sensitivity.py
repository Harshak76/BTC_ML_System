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
        
        High score indicates a broad, robust plateau (insensitivity to parameter perturbation).
        Low score indicates fragile, overfitted isolated spikes or noisy erratic response surfaces.

        Mathematical Formulation (Phase 2.2 Correction):
        ------------------------------------------------
        Unlike naive Coefficient of Variation (std / mean), this formulation is translation-invariant
        and does not divide by the mean, making it mathematically valid for positive, negative, and
        near-zero performance metrics (e.g. Sharpe ratio, which is an interval-scale metric).

        1. Flat Surface Invariance:
           If Range = max(V) - min(V) < 1e-12:
               Stability = 1.0 (maximal stability; parameter perturbations induce 0 variance).
               Separation of stability from profitability: A consistently flat losing surface receives
               1.0 stability, but fails profitability in independent validation gate checks.

        2. Normalized Dispersion Component (S_disp):
           Measures metric spread relative to an institutional reference scale (sigma_0):
           S_disp = 1.0 / (1.0 + (std(V) / sigma_0))
           where sigma_0 is 0.25 for Sharpe ratio and Profit Factor, 5.0 for percentage returns.

        3. Spike Prominence & Plateau Penalty (S_plateau):
           Overfitting manifests as an isolated sharp peak with poor surrounding parameter performance:
           Spike_Prominence = (max(V) - Q75(V)) / Range
           Spike_Penalty = min(1.0, Range / (Range + sigma_0)) * Spike_Prominence
           S_plateau = 1.0 - Spike_Penalty

        4. Local Surface Smoothness (S_smooth):
           When grid topology is available (2D surface or sorted 1D sweep), neighbor gradients
           measure local curvature and penalize checkerboard / erratic noise.

        5. Final Composite Score:
           Composite S = clip(S_disp * S_plateau * S_smooth_factor, 0.0, 1.0).
        """
        if target_metric not in df_grid.columns:
            return 0.0

        vals = df_grid[target_metric].dropna().values
        if len(vals) < 3:
            return 0.0

        val_range = float(np.ptp(vals)) # max(vals) - min(vals)

        # 1. Perfectly flat surface (all values identical)
        if val_range < 1e-12:
            return 1.0

        # Institutional reference scale for metric variability
        if "return" in target_metric.lower():
            ref_scale = 5.0 # 5% return standard deviation
        elif target_metric.lower() in ("sharpe_ratio", "sortino_ratio", "profit_factor"):
            ref_scale = 0.25 # 0.25 Sharpe ratio variation
        else:
            ref_scale = 0.25

        # 2. Normalized Dispersion Component
        std_val = float(np.std(vals))
        s_disp = 1.0 / (1.0 + (std_val / ref_scale))

        # 3. Spike Prominence & Plateau Penalty
        q75 = float(np.percentile(vals, 75))
        max_val = float(np.max(vals))
        spike_prom = (max_val - q75) / val_range
        scale_weight = min(1.0, val_range / (val_range + ref_scale))
        spike_penalty = scale_weight * spike_prom
        s_plateau = max(0.0, 1.0 - spike_penalty)

        # 4. Optional Local Surface Roughness
        s_smooth = 1.0
        try:
            scale_weight = min(1.0, val_range / (val_range + ref_scale))
            if param_y and param_y in df_grid.columns and param_x in df_grid.columns:
                surface_df = df_grid.pivot_table(index=param_y, columns=param_x, values=target_metric, aggfunc="mean")
                surface_mat = surface_df.values
                r_diffs = []
                if surface_mat.shape[0] > 1:
                    r_diffs.append(np.nanmean(np.abs(np.diff(surface_mat, axis=0))))
                if surface_mat.shape[1] > 1:
                    r_diffs.append(np.nanmean(np.abs(np.diff(surface_mat, axis=1))))
                if r_diffs:
                    mean_diff = float(np.mean(r_diffs))
                    roughness = scale_weight * min(1.0, mean_diff / (val_range + 1e-12))
                    s_smooth = 1.0 - 0.5 * roughness
            elif param_x in df_grid.columns:
                sorted_df = df_grid.sort_values(param_x)
                s_vals = sorted_df[target_metric].dropna().values
                if len(s_vals) > 1:
                    diffs = np.abs(np.diff(s_vals))
                    roughness = scale_weight * min(1.0, float(np.mean(diffs)) / (val_range + 1e-12))
                    s_smooth = 1.0 - 0.5 * roughness
        except Exception:
            s_smooth = 1.0

        # Composite Score
        composite_stability = s_disp * s_plateau * s_smooth
        return float(np.clip(composite_stability, 0.0, 1.0))
