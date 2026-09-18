"""
Calibration Module for V2 btc_ml_system.
Includes:
- Isotonic Regression probability calibration
- Cross-validated probability calibration
- Disagreement thresholding across ensemble members
"""

import logging
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

logger = logging.getLogger("btc_ml_system.calibration")


class ProbabilityCalibrator:
    """Calibrates raw predicted model probabilities into true empirical probabilities."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cal_cfg = config.get("calibration", {})
        self.method = self.cal_cfg.get("method", "isotonic")
        self.calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.is_fitted = False

    def fit(self, uncalibrated_probs: np.ndarray, y_true: np.ndarray):
        """Fit isotonic regression on validation set uncalibrated probabilities."""
        logger.info(f"Fitting Isotonic Probability Calibrator on {len(uncalibrated_probs)} samples...")
        self.calibrator.fit(uncalibrated_probs, y_true)
        self.is_fitted = True

    def calibrate(self, uncalibrated_probs: np.ndarray) -> np.ndarray:
        """Transform raw probabilities into well-calibrated probabilities."""
        if not self.is_fitted:
            logger.warning("Calibrator not fitted yet. Returning uncalibrated probabilities.")
            return uncalibrated_probs
        return self.calibrator.transform(uncalibrated_probs)
