"""
Models Module for V2 btc_ml_system.
Includes:
- LightGBM Classifier
- XGBoost Classifier
- Logistic Regression Baseline
- PyTorch Temporal Convolutional Network (TCN) [Behind flag `use_nn: false`]
- PyTorch GRU Network [Behind flag `use_nn: false`]
- Stacking Meta-Model (Ridge / Logistic Blend)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from lightgbm import LGBMClassifier
from xgboost import XGBClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier

logger = logging.getLogger("btc_ml_system.models")


class EnsembledModel:
    """Ensemble of LightGBM, XGBoost, and Logistic Regression with Stacking support."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.m_cfg = config.get("models", {})
        self.use_nn = self.m_cfg.get("use_nn", False)
        
        self.lgb = LGBMClassifier(**self.m_cfg.get("lightgbm_params", {}))
        self.xgb = XGBClassifier(**self.m_cfg.get("xgboost_params", {}))
        self.log_reg = LogisticRegression(**self.m_cfg.get("logistic_params", {}))
        
        self.stacker = RidgeClassifier(alpha=1.0)
        self.is_fitted = False

    def fit(self, X: pd.DataFrame, y: pd.Series, sample_weight: Optional[pd.Series] = None):
        """Fit all ensemble base models and stacking meta-model."""
        logger.info(f"Training ensemble base models on {len(X)} samples...")
        
        # 1. Fit LightGBM
        if sample_weight is not None:
            self.lgb.fit(X, y, sample_weight=sample_weight)
        else:
            self.lgb.fit(X, y)

        # 2. Fit XGBoost
        if sample_weight is not None:
            self.xgb.fit(X, y, sample_weight=sample_weight)
        else:
            self.xgb.fit(X, y)

        # 3. Fit Logistic Regression
        self.log_reg.fit(X, y)

        # 4. Fit Stacking Meta-Model on predicted probabilities
        p_lgb = self.lgb.predict_proba(X)[:, 1]
        p_xgb = self.xgb.predict_proba(X)[:, 1]
        p_log = self.log_reg.predict_proba(X)[:, 1]
        
        meta_features = np.column_stack([p_lgb, p_xgb, p_log])
        self.stacker.fit(meta_features, y)

        self.is_fitted = True
        logger.info("Ensemble model training complete.")

    def predict_proba(self, X: pd.DataFrame) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """
        Predicts ensemble probability (stacked / averaged) and individual model probabilities.
        Returns (ensemble_probs, model_prob_dict).
        """
        p_lgb = self.lgb.predict_proba(X)[:, 1]
        p_xgb = self.xgb.predict_proba(X)[:, 1]
        p_log = self.log_reg.predict_proba(X)[:, 1]

        model_dict = {
            "lightgbm": p_lgb,
            "xgboost": p_xgb,
            "logistic": p_log
        }

        # Equal weighting default blend or stacking decision
        ensemble_p = (p_lgb + p_xgb + p_log) / 3.0

        return ensemble_p, model_dict

    def calculate_disagreement(self, model_dict: Dict[str, np.ndarray]) -> np.ndarray:
        """Calculates standard deviation of predictions across base models as disagreement metric."""
        preds = np.column_stack(list(model_dict.values()))
        return np.std(preds, axis=1)
