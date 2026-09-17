"""
Machine Learning Models Module.
Implements baselines, Logistic Regression, LightGBM, XGBoost, and model persistence.
"""

import os
import logging
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
import pandas as pd
import joblib

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score, brier_score_loss
import lightgbm as lgb
import xgboost as xgb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class MajorityClassBaseline:
    """Baseline model predicting the majority class probability from training set."""

    def __init__(self):
        self.majority_prob = 0.5

    def fit(self, X: np.ndarray, y: np.ndarray):
        self.majority_prob = float(np.mean(y))
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        p = np.full((len(X), 2), 1.0 - self.majority_prob)
        p[:, 1] = self.majority_prob
        return p


class ModelFactory:
    """Factory for building, training, and evaluating trading models."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.model_type = self.config.get("preferred_type", "lightgbm")
        self.seed = self.config.get("seed", 42)

    def build_model(self, model_type: Optional[str] = None):
        m_type = model_type or self.model_type

        if m_type == "logistic":
            params = self.config.get("logistic_params", {"C": 1.0, "max_iter": 1000, "random_state": self.seed})
            return LogisticRegression(**params)
        elif m_type == "lightgbm":
            params = self.config.get("lightgbm_params", {
                "n_estimators": 200, "learning_rate": 0.03, "max_depth": 5,
                "num_leaves": 31, "subsample": 0.8, "colsample_bytree": 0.8,
                "random_state": self.seed, "verbose": -1
            })
            return lgb.LGBMClassifier(**params)
        elif m_type == "xgboost":
            params = self.config.get("xgboost_params", {
                "n_estimators": 200, "learning_rate": 0.03, "max_depth": 4,
                "subsample": 0.8, "colsample_bytree": 0.8, "random_state": self.seed
            })
            return xgb.XGBClassifier(**params)
        elif m_type == "majority":
            return MajorityClassBaseline()
        else:
            raise ValueError(f"Unknown model type: {m_type}")

    def train_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        model_type: Optional[str] = None
    ) -> Any:
        """Trains model with optional early stopping on validation fold."""
        model = self.build_model(model_type)

        if isinstance(model, MajorityClassBaseline):
            model.fit(X_train, y_train)
            return model

        m_type = model_type or self.model_type
        if m_type == "lightgbm" and X_val is not None and y_val is not None:
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
            )
        elif m_type == "xgboost" and X_val is not None and y_val is not None:
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )
        else:
            model.fit(X_train, y_train)

        return model

    @staticmethod
    def evaluate_model(
        model: Any,
        X_eval: np.ndarray,
        y_eval: np.ndarray
    ) -> Dict[str, float]:
        """Calculates loss metrics (Brier score, LogLoss, ROC-AUC) on evaluation data."""
        if hasattr(model, "predict_proba"):
            probs = model.predict_proba(X_eval)[:, 1]
        else:
            probs = model.predict(X_eval)

        loss = log_loss(y_eval, probs, eps=1e-15)
        brier = brier_score_loss(y_eval, probs)
        try:
            auc = roc_auc_score(y_eval, probs)
        except Exception:
            auc = 0.50

        return {
            "log_loss": float(loss),
            "brier_score": float(brier),
            "roc_auc": float(auc)
        }

    @staticmethod
    def save_artifact(obj: Any, filepath: str):
        """Saves model or scaler artifact."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        joblib.dump(obj, filepath)
        logger.info(f"Saved artifact to {filepath}")

    @staticmethod
    def load_artifact(filepath: str) -> Any:
        """Loads model or scaler artifact."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Artifact not found at {filepath}")
        return joblib.load(filepath)
