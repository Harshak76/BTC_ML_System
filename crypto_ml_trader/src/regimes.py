"""
Market Regime Classification Module.
Detects trend vs range dynamics and volatility regimes using confirmed 4h HTF data.
Enforces HTF filter condition for long trades.
"""

import logging
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class RegimeDetector:
    """Classifies market regime into Bullish Trend, Bearish Trend, or Ranging/High Volatility."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.adx_threshold = self.config.get("adx_trend_threshold", 20.0)
        self.vol_high_quantile = self.config.get("volatility_high_quantile", 0.80)

    def detect_regime(self, row: pd.Series) -> Dict[str, Any]:
        """
        Detects regime for a single point-in-time observation (bar).
        Required fields in row:
        - htf_adx_14
        - htf_di_diff
        - htf_ema50_to_ema200
        - norm_atr_14
        """
        adx = row.get("htf_adx_14", 0.20) * 100.0 if "htf_adx_14" in row else 20.0
        di_diff = row.get("htf_di_diff", 0.0)
        ema_ratio = row.get("htf_ema50_to_ema200", 0.0)
        atr_norm = row.get("norm_atr_14", 0.02)

        is_trending = adx >= self.adx_threshold
        is_bullish = (di_diff > 0) and (ema_ratio >= -0.005)
        is_bearish = (di_diff < 0) and (ema_ratio < -0.005)

        if is_trending and is_bullish:
            regime = "BULLISH_TREND"
            permits_long = True
        elif is_trending and is_bearish:
            regime = "BEARISH_TREND"
            permits_long = False
        else:
            regime = "RANGING_NEUTRAL"
            # In ranging market, allow long if DI diff is positive
            permits_long = di_diff >= 0.0

        return {
            "regime": regime,
            "permits_long": permits_long,
            "adx": adx,
            "di_diff": di_diff,
            "ema_ratio": ema_ratio,
            "atr_norm": atr_norm
        }

    def annotate_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Annotates full dataframe with regime labels and permits_long flag."""
        df = df.copy()
        regimes = []
        permits_long_list = []

        for idx, row in df.iterrows():
            res = self.detect_regime(row)
            regimes.append(res["regime"])
            permits_long_list.append(res["permits_long"])

        df["market_regime"] = regimes
        df["htf_permits_long"] = permits_long_list

        logger.info(
            f"Regime breakdown: "
            f"BULLISH_TREND: {(df['market_regime'] == 'BULLISH_TREND').sum()} | "
            f"BEARISH_TREND: {(df['market_regime'] == 'BEARISH_TREND').sum()} | "
            f"RANGING_NEUTRAL: {(df['market_regime'] == 'RANGING_NEUTRAL').sum()}"
        )

        return df
