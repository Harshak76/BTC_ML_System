"""
Meta-Labeling Module for V2 btc_ml_system.
Implements secondary classifier to filter primary signals and compute dynamic bet sizes.
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

        logger.info(f"Training Meta-Labeling classifier on {len(X)} samples...")
        if sample_weight is not None:
            self.model.fit(X, meta_y, sample_weight=sample_weight)
        else:
            self.model.fit(X, meta_y)

        self.is_fitted = True

    def predict_meta_prob(self, X: pd.DataFrame) -> np.ndarray:
        """Predict probability that the primary trade signal will be successful."""
        if not self.enabled or not self.is_fitted:
            return np.ones(len(X))

        return self.model.predict_proba(X)[:, 1]

    def compute_bet_size(
        self,
        primary_prob: np.ndarray,
        meta_prob: np.ndarray,
        threshold: float = 0.50
    ) -> np.ndarray:
        """
        Calculates continuous bet size [0.0, 1.0] using meta-probability or probability ratio.
        Bet Size = 2 * P(Meta) - 1 bounded between 0 and 1.
        """
        if not self.enabled:
            # Standard binary sizing
            return np.where(primary_prob >= threshold, 1.0, 0.0)

        bet_sizes = np.zeros(len(primary_prob))
        for i in range(len(primary_prob)):
            if primary_prob[i] >= threshold:
                p_meta = meta_prob[i]
                # Scale bet: 2 * (p - 0.5) if p >= 0.5 else 0
                if p_meta >= 0.5:
                    bet_sizes[i] = min(1.0, max(0.0, 2.0 * (p_meta - 0.5)))
                else:
                    bet_sizes[i] = 0.0

        return bet_sizes
