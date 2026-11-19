"""
Genuine Strategy Candidate Return Matrix Builder for CSCV / PBO Analysis.
Replaces synthetic Gaussian perturbations with authentic return series extracted
from independent quantitative strategy research runs.
"""

from typing import List, Dict, Any, Tuple
import numpy as np


class GenuineCandidateMatrixBuilder:
    """
    Constructs an authentic multi-strategy candidate return matrix for PBO / CSCV.
    Guarantees zero synthetic Gaussian noise or artificial perturbations.
    """

    MIN_GENUINE_CANDIDATES = 4

    @classmethod
    def build_matrix(
        cls,
        simulation_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Builds a T x N candidate return matrix from genuine research simulation runs.
        
        If fewer than MIN_GENUINE_CANDIDATES are provided, flags the candidate pool
        as INCOMPLETE for PBO analysis, enforcing quantitative integrity.
        """
        if not simulation_results:
            return {
                "candidates_matrix": None,
                "n_candidates": 0,
                "t_steps": 0,
                "is_sufficient_for_pbo": False,
                "status": "INCOMPLETE",
                "reason": "No simulation results provided."
            }

        candidate_ids = []
        return_series_list = []

        for res in simulation_results:
            strat_id = res.get("strategy_id", "unknown")
            rets = res.get("periodic_returns_pct")
            if rets is not None and len(rets) > 0:
                candidate_ids.append(strat_id)
                return_series_list.append(np.asarray(rets, dtype=float))

        n_candidates = len(return_series_list)
        if n_candidates == 0:
            return {
                "candidates_matrix": None,
                "n_candidates": 0,
                "t_steps": 0,
                "is_sufficient_for_pbo": False,
                "status": "INCOMPLETE",
                "reason": "Zero valid return series found in simulation results."
            }

        # Align length to minimum common length
        min_len = min(len(s) for s in return_series_list)
        if min_len < 30:
            return {
                "candidates_matrix": None,
                "n_candidates": n_candidates,
                "t_steps": min_len,
                "is_sufficient_for_pbo": False,
                "status": "INCOMPLETE",
                "reason": f"Sample length T={min_len} is too short for CSCV block partitioning (requires >= 30)."
            }

        candidates_matrix = np.zeros((min_len, n_candidates))
        for col_idx, s in enumerate(return_series_list):
            candidates_matrix[:, col_idx] = s[:min_len]

        is_sufficient = bool(n_candidates >= cls.MIN_GENUINE_CANDIDATES)

        return {
            "candidates_matrix": candidates_matrix,
            "candidate_ids": candidate_ids,
            "n_candidates": n_candidates,
            "t_steps": min_len,
            "is_sufficient_for_pbo": is_sufficient,
            "status": "VALID_CANDIDATES" if is_sufficient else "INCOMPLETE",
            "reason": (
                "Sufficient genuine candidates for CSCV evaluation."
                if is_sufficient else
                f"Candidate pool contains only {n_candidates} genuine candidates "
                f"(minimum {cls.MIN_GENUINE_CANDIDATES} required). PBO must be marked INCOMPLETE."
            ),
            "is_synthetic": False
        }
