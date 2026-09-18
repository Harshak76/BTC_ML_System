"""
Drift & Feature Stability Monitoring Module for V2 btc_ml_system.
Includes:
- Population Stability Index (PSI) tracking
- Kolmogorov-Smirnov (KS) test for feature distribution shifts
- Retraining signal trigger based on drift magnitude
- SHAP feature contribution logging
"""

import logging
from typing import Dict, Any, Tuple
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger("btc_ml_system.monitoring")


class ModelMonitor:
    """Monitors live data drift and feature stability over time."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mon_cfg = config.get("monitoring", {})
        self.psi_threshold = self.mon_cfg.get("psi_threshold", 0.20)
        self.ks_threshold = self.mon_cfg.get("ks_threshold", 0.10)
        self.window = self.mon_cfg.get("prediction_drift_window", 100)

    def calculate_psi(self, reference: np.ndarray, current: np.ndarray, num_bins: int = 10) -> float:
        """Calculates Population Stability Index (PSI) between reference train set and live predictions."""
        if len(reference) == 0 or len(current) == 0:
            return 0.0

        bins = np.linspace(0, 1, num_bins + 1)
        ref_counts, _ = np.histogram(reference, bins=bins)
        curr_counts, _ = np.histogram(current, bins=bins)

        ref_pct = (ref_counts + 1e-5) / (len(reference) + 1e-5 * num_bins)
        curr_pct = (curr_counts + 1e-5) / (len(current) + 1e-5 * num_bins)

        psi_val = np.sum((curr_pct - ref_pct) * np.log(curr_pct / ref_pct))
        return float(psi_val)

    def check_feature_drift(self, train_df: pd.DataFrame, live_df: pd.DataFrame, features: list) -> Dict[str, Any]:
        """
        Runs Kolmogorov-Smirnov 2-sample test across all features.
        Returns drift summary dict and boolean flag for retraining signal.
        """
        drift_results = {}
        drift_count = 0

        for col in features:
            if col in train_df.columns and col in live_df.columns:
                ref_vals = train_df[col].dropna().values
                curr_vals = live_df[col].dropna().values

                if len(ref_vals) > 10 and len(curr_vals) > 10:
                    ks_stat, p_val = stats.ks_2samp(ref_vals, curr_vals)
                    is_drifted = p_val < self.ks_threshold
                    if is_drifted:
                        drift_count += 1
                    drift_results[col] = {"ks_stat": float(ks_stat), "p_val": float(p_val), "drifted": is_drifted}

        drift_ratio = drift_count / max(1, len(features))
        retrain_signal = drift_ratio >= self.mon_cfg.get("retrain_signal_threshold", 0.25)

        logger.info(f"Drift Audit: {drift_count}/{len(features)} features drifted ({drift_ratio:.1%}). Retrain Signal: {retrain_signal}")

        return {
            "drift_ratio": drift_ratio,
            "drifted_feature_count": drift_count,
            "retrain_recommended": retrain_signal,
            "feature_details": drift_results
        }
