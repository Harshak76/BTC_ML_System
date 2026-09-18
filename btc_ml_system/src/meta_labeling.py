"""
Meta-Labeling Module for V2.1 btc_ml_system.
Implements secondary classifier to filter primary signals and compute dynamic bet sizes.
Includes logging diagnostics for zero bet size occurrences and fallback minimum bet sizing.
Ref: Marcos Lopez de Prado - Advances in Financial Machine Learning (Chapter 3 & 10)
"""

import logging
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

logger = logging.getLogger("btc_ml_system.meta_labeling")


class MetaLabeler:
    """Secondary meta-classifier to filter primary signals and dynamically scale position sizes."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.meta_cfg = config.get("meta_labeling", {})
        self.enabled = self.meta_cfg.get("enabled", True)
        self.bet_method = self.meta_cfg.get("bet_size_method", "meta_prob")
        self.min_bet_size = self.meta_cfg.get("min_bet_size", 0.10)
        self.model = LGBMClassifier(
            n_estimators=150,
            learning_rate=0.03,
            max_depth=3,
            random_state=42,
            verbose=-1
        )
        self.is_fitted = False

    def fit(self, X: pd.DataFrame, meta_y: pd.Series, sample_weight: Optional[pd.Series] = None):
        """Fit secondary meta-model on primary side predictions and features."""
        if not self.enabled:
            return

        # Check if meta_y has both classes (0 and 1)
        unique_classes = np.unique(meta_y)
        if len(unique_classes) < 2:
            logger.warning(f"Meta-labeling target only has single class {unique_classes}. Disabling meta-model fitting.")
            self.is_fitted = False
            return

        logger.info(f"Training Meta-Labeling classifier on {len(X)} samples...")
        if sample_weight is not None:
            self.model.fit(X, meta_y, sample_weight=sample_weight)
        else:
            self.model.fit(X, meta_y)

        self.is_fitted = True

    def predict_meta_prob(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probability that the primary trade signal will be successful."""
        if not self.enabled or not self.is_fitted:
            return np.ones(len(X)) * 0.50

        return self.model.predict_proba(X)[:, 1]

    def compute_bet_size(
        self,
        primary_prob: np.ndarray,
        meta_prob: np.ndarray,
        threshold: float = 0.50
    ) -> np.ndarray:
        """
        Calculates continuous bet size [0.0, 1.0] using meta-probability.
        Provides diagnostic logging of zero bet reasons.
        """
        if not self.enabled:
            return np.where(primary_prob >= threshold, 1.0, 0.0)

        bet_sizes = np.zeros(len(primary_prob))
        zero_reasons = {"primary_below_threshold": 0, "meta_prob_below_0.5": 0}

        for i in range(len(primary_prob)):
            if primary_prob[i] >= threshold:
                p_meta = meta_prob[i]
                if p_meta >= 0.5:
                    bet = 2.0 * (p_meta - 0.5)
                    bet_sizes[i] = min(1.0, max(self.min_bet_size, bet))
                else:
                    zero_reasons["meta_prob_below_0.5"] += 1
                    bet_sizes[i] = 0.0
            else:
                zero_reasons["primary_below_threshold"] += 1
                bet_sizes[i] = 0.0

        if sum(zero_reasons.values()) > 0:
            logger.debug(f"Bet sizing zero reasons: {zero_reasons}")

        return bet_sizes
