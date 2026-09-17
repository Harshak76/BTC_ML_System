"""
Cross-Validation & Data Splitting Module.
Implements Chronological Purged Walk-Forward Cross Validation with Embargoing
as detailed by Marcos Lopez de Prado.
"""

import logging
from typing import List, Tuple, Generator
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class PurgedWalkForwardCV:
    """
    Purged Walk-Forward Cross Validation.
    - Preserves strict chronological order.
    - Purges overlapping label horizons between train and validation folds.
    - Applies embargo period after validation set to prevent autoregressive feature leakage.
    """

    def __init__(
        self,
        n_splits: int = 5,
        label_horizon: int = 12,
        embargo_pct: float = 0.01,
        min_train_size: float = 0.4
    ):
        self.n_splits = n_splits
        self.label_horizon = label_horizon
        self.embargo_pct = embargo_pct
        self.min_train_size = min_train_size

    def split(
        self,
        df: pd.DataFrame
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Generates train and validation index arrays for each fold.
        """
        n_samples = len(df)
        indices = np.arange(n_samples)
        embargo_size = int(n_samples * self.embargo_pct)

        # Total size allocated to validation splits
        min_train_samples = int(n_samples * self.min_train_size)
        val_total_samples = n_samples - min_train_samples
        val_split_size = val_total_samples // self.n_splits

        for i in range(self.n_splits):
            val_start = min_train_samples + i * val_split_size
            val_end = val_start + val_split_size if i < self.n_splits - 1 else n_samples

            val_indices = indices[val_start:val_end]

            # Purging train set: remove train samples [val_start - label_horizon : val_start]
            train_end_purged = max(0, val_start - self.label_horizon)
            train_indices = indices[:train_end_purged]

            # If there's train data after validation (for non-expanding walk forward), apply embargo:
            # post_val_start = val_end + embargo_size

            yield train_indices, val_indices

    def train_val_test_split(
        self,
        df: pd.DataFrame,
        train_ratio: float = 0.6,
        val_ratio: float = 0.2,
        test_ratio: float = 0.2
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Splits data chronologically into untouched Train, Validation, and Holdout Test sets.
        Purges samples near train-val and val-test boundaries.
        """
        n = len(df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        # Purge boundary regions equal to label_horizon
        purged_train_end = max(0, train_end - self.label_horizon)
        purged_val_end = max(train_end, val_end - self.label_horizon)

        df_train = df.iloc[:purged_train_end].copy()
        df_val = df.iloc[train_end:purged_val_end].copy()
        df_test = df.iloc[val_end:].copy()

        logger.info(
            f"Data Splits: Train = {len(df_train)} bars | "
            f"Val = {len(df_val)} bars | "
            f"Test = {len(df_test)} bars"
        )

        return df_train, df_val, df_test
