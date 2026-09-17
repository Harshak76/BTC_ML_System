"""
Probability Calibration & Meta-Ensemble Module.
Calibrates raw machine learning model probabilities using Isotonic Regression or Platt Scaling.
Combines calibrated outputs into an ensemble score.
"""

import logging
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ModelCalibrator:
    """Calibrates model probability outputs using Isotonic Regression."""

    def __init__(self, method: str = "isotonic"):
        self.method = method
        self.calibrator = IsotonicRegression(out_of_bounds="clip") if method == "isotonic" else LogisticRegression()
        self.is_fitted = False

    def fit(self, raw_probs: np.ndarray, y_val: np.ndarray):
        """Fits probability calibrator on validation fold predictions."""
        if self.method == "isotonic":
            self.calibrator.fit(raw_probs, y_val)
        else:
            self.calibrator.fit(raw_probs.reshape(-1, 1), y_val)
        self.is_fitted = True
        logger.info(f"Fitted probability calibrator using method='{self.method}'")
        return self

    def calibrate(self, raw_probs: np.ndarray) -> np.ndarray:
        """Calibrates raw probability array."""
        if not self.is_fitted:
            logger.warning("Calibrator not fitted yet! Returning raw probabilities.")
            return raw_probs

        if self.method == "isotonic":
            calibrated = self.calibrator.predict(raw_probs)
        else:
            calibrated = self.calibrator.predict_proba(raw_probs.reshape(-1, 1))[:, 1]

        return np.clip(calibrated, 0.0, 1.0)


class EnsembleMetaModel:
    """Meta-ensemble that averages predictions across multiple calibrated models."""

    def __init__(self, models_and_calibrators: List[Tuple[Any, Optional[ModelCalibrator]]]):
        self.models_and_calibrators = models_and_calibrators

    def predict_proba(self, X: np.ndarray) -> Tuple[float, float]:
        """
        Returns (mean_calibrated_buy_prob, model_disagreement_std).
        """
        calibrated_probs = []

        for model, calibrator in self.models_and_calibrators:
            if hasattr(model, "predict_proba"):
                raw_prob = model.predict_proba(X)[:, 1]
            else:
                raw_prob = model.predict(X)

            if calibrator is not None:
                cal_prob = calibrator.calibrate(raw_prob)
            else:
                cal_prob = raw_prob

            calibrated_probs.append(cal_prob)

        probs_matrix = np.column_stack(calibrated_probs)
        mean_prob = float(np.mean(probs_matrix, axis=1)[-1]) if probs_matrix.ndim == 2 else float(np.mean(probs_matrix))
        disagreement = float(np.std(probs_matrix, axis=1)[-1]) if probs_matrix.ndim == 2 else float(np.std(probs_matrix))

        return mean_prob, disagreement
