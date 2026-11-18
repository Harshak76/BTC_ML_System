"""
Probability of Backtest Overfitting (PBO) & Combinatorially Symmetric Cross-Validation (CSCV)
Reference:
Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014).
"The Probability of Backtest Overfitting". Journal of Computational Finance.

Mathematical Formulation:
- Divide T observations into an even number of blocks S.
- Construct all C(S, S/2) symmetric In-Sample (IS) and complementary Out-of-Sample (OOS) partitions.
- For each partition, select the in-sample optimal strategy n* and evaluate its relative rank in OOS.
- PBO is the empirical probability that the IS winner achieves an OOS rank <= 0.50 (below median).
"""

import logging
from typing import Dict, Any, List, Tuple, Optional, Union
import itertools
import numpy as np
import pandas as pd

logger = logging.getLogger("btc_ml_system.validation.pbo_cscv")


class PBOCSCVEngine:
    """
    Computes Probability of Backtest Overfitting (PBO) using Combinatorially Symmetric Cross-Validation (CSCV).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.pbo_cfg = self.config.get("pbo_cscv", {})
        # S must be an even integer (e.g. 8, 10, 16)
        self.n_blocks = int(self.pbo_cfg.get("n_blocks", 10))
        if self.n_blocks % 2 != 0:
            raise ValueError(f"n_blocks must be an even integer, got {self.n_blocks}")

        # Maximum combinations to sample if C(S, S/2) is large
        self.max_combinations = int(self.pbo_cfg.get("max_combinations", 1000))
        self.random_seed = int(self.pbo_cfg.get("random_seed", 42))

    def compute_pbo_from_returns_matrix(
        self,
        returns_matrix: Union[np.ndarray, pd.DataFrame],
        metric: str = "sharpe_ratio"
    ) -> Dict[str, Any]:
        """
        Calculates PBO and CSCV statistics.
        returns_matrix: shape (T, N), where T is number of chronological periods and N is candidate configurations.
        """
        if isinstance(returns_matrix, pd.DataFrame):
            matrix = returns_matrix.values
            col_names = list(returns_matrix.columns)
        else:
            matrix = np.array(returns_matrix)
            col_names = [f"config_{i}" for i in range(matrix.shape[1])]

        T, N = matrix.shape
        if N < 2:
            return {"error": "PBO requires at least N >= 2 candidate strategy configurations."}
        if T < self.n_blocks * 2:
            return {"error": f"T ({T}) is too short for {self.n_blocks} blocks."}

        S = self.n_blocks
        half_S = S // 2

        # 1. Slice T into S blocks
        block_size = T // S
        blocks = [matrix[i * block_size : (i + 1) * block_size if i < S - 1 else T] for i in range(S)]

        # 2. Generate all C(S, S/2) combinations
        all_combos = list(itertools.combinations(range(S), half_S))
        total_combos = len(all_combos)

        # Subsample combinations deterministically if total exceeds max_combinations
        if total_combos > self.max_combinations:
            rng = np.random.default_rng(self.random_seed)
            selected_indices = rng.choice(total_combos, size=self.max_combinations, replace=False)
            combos_to_eval = [all_combos[i] for i in selected_indices]
        else:
            combos_to_eval = all_combos

        logger.info(f"Computing CSCV across {len(combos_to_eval)} symmetric partitions for {N} strategy variants.")

        relative_ranks = []
        is_best_sharpes = []
        oos_best_sharpes = []
        is_winner_indices = []

        for combo in combos_to_eval:
            is_block_indices = set(combo)
            oos_block_indices = set(range(S)) - is_block_indices

            # Concatenate blocks
            is_data = np.concatenate([blocks[b] for b in sorted(list(is_block_indices))], axis=0)
            oos_data = np.concatenate([blocks[b] for b in sorted(list(oos_block_indices))], axis=0)

            # Performance metric vector for all N models on IS
            is_scores = self._compute_performance_vector(is_data, metric)
            # Performance metric vector for all N models on OOS
            oos_scores = self._compute_performance_vector(oos_data, metric)

            # In-Sample Winner: n* = argmax(is_scores)
            n_star = int(np.argmax(is_scores))
            is_winner_indices.append(n_star)

            # Performance of winner in OOS
            oos_winner_score = oos_scores[n_star]

            # Relative rank of n* in OOS:
            # Count how many configurations scored worse than n* in OOS
            num_worse = np.sum(oos_scores < oos_winner_score)
            num_ties = np.sum(oos_scores == oos_winner_score)
            rank = num_worse + 1 + 0.5 * (num_ties - 1)
            rel_rank = rank / (N + 1.0)

            relative_ranks.append(rel_rank)
            is_best_sharpes.append(is_scores[n_star])
            oos_best_sharpes.append(oos_winner_score)

        rel_ranks_arr = np.array(relative_ranks)
        # Probability of Backtest Overfitting: proportion of splits where relative rank <= 0.50
        pbo = float(np.mean(rel_ranks_arr <= 0.50))

        # Probability of Loss (proportion where OOS performance <= 0)
        prob_loss = float(np.mean(np.array(oos_best_sharpes) <= 0.0))

        # Performance Degradation
        mean_is_perf = float(np.mean(is_best_sharpes))
        mean_oos_perf = float(np.mean(oos_best_sharpes))
        degradation = mean_is_perf - mean_oos_perf

        # Log-odds / Logit distribution
        # clip rel_rank away from 0 and 1 to prevent inf
        clipped_ranks = np.clip(rel_ranks_arr, 1e-4, 1.0 - 1e-4)
        logits = np.log(clipped_ranks / (1.0 - clipped_ranks))

        return {
            "pbo": pbo,
            "n_configurations": N,
            "n_blocks": S,
            "total_partitions_evaluated": len(combos_to_eval),
            "prob_loss": prob_loss,
            "mean_in_sample_sharpe": mean_is_perf,
            "mean_out_of_sample_sharpe": mean_oos_perf,
            "performance_degradation": degradation,
            "median_relative_rank": float(np.median(rel_ranks_arr)),
            "p10_relative_rank": float(np.percentile(rel_ranks_arr, 10)),
            "p90_relative_rank": float(np.percentile(rel_ranks_arr, 90)),
            "mean_logit": float(np.mean(logits)),
            "is_overfitted": bool(pbo > 0.50),
            "interpretation": (
                f"PBO = {pbo:.1%}. There is a {pbo:.1%} empirical probability that the in-sample optimal strategy "
                f"will deliver below-median performance out-of-sample. "
                + ("HIGH RISK OF OVERFITTING." if pbo > 0.50 else "Acceptable generalizability.")
            )
        }

    def _compute_performance_vector(self, data: np.ndarray, metric: str) -> np.ndarray:
        """Computes metric for all columns in data."""
        # data: shape (T_sub, N)
        T_sub, N = data.shape
        if metric == "sharpe_ratio":
            means = np.mean(data, axis=0)
            stds = np.std(data, axis=0, ddof=1)
            # Annualization approx (hourly 252*24)
            sharpes = np.where(stds > 1e-12, (means / stds) * np.sqrt(252 * 24), 0.0)
            return sharpes
        elif metric == "total_return":
            cum_returns = np.prod(1.0 + data, axis=0) - 1.0
            return cum_returns
        else:
            return np.mean(data, axis=0)
