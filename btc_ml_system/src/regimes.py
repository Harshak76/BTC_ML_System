"""
Volatilty Regime Classifier for V3 btc_ml_system.
Classifies market environment strictly into CALM, NORMAL, and HIGH Volatility states.
"""

import logging
from typing import Dict, Any
from enum import Enum
import pandas as pd
import numpy as np

logger = logging.getLogger("btc_ml_system.regimes")


class VolatilityRegimeState(str, Enum):
    CALM = "CALM"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


class VolatilityRegimeClassifier:
    """Classifies market into CALM, NORMAL, and HIGH Volatility regimes."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.vol_cfg = config.get("volatility_regime", {})
        self.window = self.vol_cfg.get("window", 24)
        self.calm_q = self.vol_cfg.get("calm_quantile", 0.33)
        self.high_q = self.vol_cfg.get("high_quantile", 0.67)
        self.allowed_regimes = self.vol_cfg.get("allowed_regimes", ["CALM", "NORMAL"])

    def predict_regimes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Classifies each bar into CALM, NORMAL, or HIGH using expanding quantile thresholds.
        """
        df = df.copy()
        if "ret_1h" in df.columns:
            vol = df["ret_1h"].rolling(self.window).std() * np.sqrt(24 * 365)
        else:
            vol = df["close"].pct_change().rolling(self.window).std() * np.sqrt(24 * 365)

        q_calm = vol.expanding(min_periods=50).quantile(self.calm_q)
        q_high = vol.expanding(min_periods=50).quantile(self.high_q)

        states = []
        is_favorable = []

        for i in range(len(df)):
            v = vol.iloc[i]
            qc = q_calm.iloc[i]
            qh = q_high.iloc[i]

            if pd.isna(v) or pd.isna(qc):
                state = VolatilityRegimeState.NORMAL.value
            elif v <= qc:
                state = VolatilityRegimeState.CALM.value
            elif v >= qh:
                state = VolatilityRegimeState.HIGH.value
            else:
                state = VolatilityRegimeState.NORMAL.value

            states.append(state)
            is_favorable.append(state in self.allowed_regimes)

        df["volatility_regime"] = states
        df["vol_regime_favorable"] = is_favorable
        return df


# Backward Compatibility Alias for V2/V2.1 calls
class RegimeDetector:
    def __init__(self, config: Dict[str, Any]):
        self.classifier = VolatilityRegimeClassifier(config)

    def detect_regimes(self, df: pd.DataFrame) -> pd.DataFrame:
        df_res = self.classifier.predict_regimes(df)
        df_res["regime"] = df_res["volatility_regime"]
        return df_res

    def get_regime_parameters(self, regime_str: str) -> Dict[str, float]:
        if regime_str in ["CALM", "NORMAL"]:
            return {"buy_prob_threshold": 0.50, "position_size_multiplier": 1.0}
        return {"buy_prob_threshold": 0.80, "position_size_multiplier": 0.0}
