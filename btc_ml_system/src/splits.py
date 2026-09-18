"""
Splits Module for V2 btc_ml_system.
Includes:
- Purged Walk-Forward CV (Zero future leakage)
- Combinatorial Purged Cross-Validation (CPCV) (Marcos Lopez de Prado)
- Multiple Out-Of-Sample (OOS) testing windows
"""

import logging
from typing import Dict, Any, List, Tuple, Generator
import itertools
import numpy as np
import pandas as pd

logger = logging.getLogger("btc_ml_system.splits")


class DataSplitter:
    """Generates purged walk-forward and CPCV train/val/test splits."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.split_cfg = config.get("splits", {})
        self.n_splits = self.split_cfg.get("n_splits", 5)
        self.embargo_pct = self.split_cfg.get("embargo_pct", 0.01)
        self.label_horizon = self.split_cfg.get("label_horizon", 12)
        self.cpcv_groups = self.split_cfg.get("cpcv_n_groups", 6)
        self.cpcv_test_groups = self.split_cfg.get("cpcv_n_test_groups", 2)

    def purged_walk_forward_splits(
        self,
        df: pd.DataFrame
    ) -> Generator[Tuple[np.ndarray, np.ndarray, np.ndarray], None, None]:
        """
        Purged Walk-Forward Cross-Validation splits.
        Yields (train_indices, val_indices, test_indices).
        Includes purging (removing label overlap) and embargoing (removing post-test leak).
        """
        n = len(df)
        embargo = int(n * self.embargo_pct)
        purge = self.label_horizon

        segment_size = n // (self.n_splits + 2)

        for i in range(self.n_splits):
            train_end = (i + 2) * segment_size
            val_start = train_end + purge
            val_end = val_start + segment_size
            test_start = val_end + embargo + purge
            test_end = min(n, test_start + segment_size)

            if test_start >= n or val_start >= n:
                break

            train_idx = np.arange(0, max(0, train_end - purge))
            val_idx = np.arange(val_start, min(n, val_end))
            test_idx = np.arange(test_start, test_end)

            if len(train_idx) > 0 and len(val_idx) > 0 and len(test_idx) > 0:
                yield train_idx, val_idx, test_idx

    def cpcv_splits(
        self,
        df: pd.DataFrame
    ) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Combinatorial Purged Cross-Validation (CPCV) splits (V2 Addition).
        Splits data into N equal groups and tests all C(N, k) combinations as test set.
        """
        n = len(df)
        group_size = n // self.cpcv_groups
        groups = [np.arange(i * group_size, (i + 1) * group_size if i < self.cpcv_groups - 1 else n)
                  for i in range(self.cpcv_groups)]

        purge = self.label_horizon
        embargo = int(n * self.embargo_pct)

        all_combinations = list(itertools.combinations(range(self.cpcv_groups), self.cpcv_test_groups))
        splits = []

        for combo in all_combinations:
            test_indices = np.concatenate([groups[g] for g in combo])

            # Build train set with purging around test groups
            train_indices_list = []
            for g in range(self.cpcv_groups):
                if g not in combo:
                    g_idx = groups[g]
                    # Check overlap with any test group
                    valid_mask = np.ones(len(g_idx), dtype=bool)
                    for test_g in combo:
                        test_min, test_max = groups[test_g].min(), groups[test_g].max()
                        # Purge before test group
                        purge_mask = (g_idx >= test_min - purge) & (g_idx <= test_max + embargo + purge)
                        valid_mask = valid_mask & (~purge_mask)

                    train_indices_list.append(g_idx[valid_mask])

            if train_indices_list:
                train_indices = np.concatenate(train_indices_list)
                splits.append((train_indices, test_indices))

        logger.info(f"Generated {len(splits)} CPCV combinatorial splits across {self.cpcv_groups} groups.")
        return splits
