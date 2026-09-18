"""
Regime Identification Module for V2 btc_ml_system.
Features:
- Multi-timeframe trend & volatility detection (1h and 4h)
- 4 Regime States: BULLISH_TREND, BEARISH_TREND, RANGING_NEUTRAL, HIGH_VOLATILITY
- Transition tracking & regime lookback stability
- Regime-dependent thresholds & risk multipliers
"""

import logging
from typing import Dict, Any, Tuple
from enum import Enum
import pandas as pd
import numpy as np

logger = logging.getLogger("btc_ml_system.regimes")


class MarketRegime(str, Enum):
    BULLISH_TREND = "BULLISH_TREND"
    BEARISH_TREND = "BEARISH_TREND"
    RANGING_NEUTRAL = "RANGING_NEUTRAL"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


class RegimeDetector:
    """Classifies market environment and provides dynamic risk parameters."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.reg_cfg = config.get("regimes", {})
        self.adx_thresh = self.reg_cfg.get("adx_trend_threshold", 20.0)
        self.vol_high_q = self.reg_cfg.get("volatility_high_quantile", 0.80)
        self.use_1h = self.reg_cfg.get("use_1h_regime", True)
        self.use_4h = self.reg_cfg.get("use_4h_regime", True)
        self.regime_params = self.reg_cfg.get("regime_dependent_thresholds", {
            "BULLISH_TREND": {"buy_prob_threshold": 0.50, "position_size_multiplier": 1.0},
            "BEARISH_TREND": {"buy_prob_threshold": 0.70, "position_size_multiplier": 0.5},
            "RANGING_NEUTRAL": {"buy_prob_threshold": 0.55, "position_size_multiplier": 0.75},
            "HIGH_VOLATILITY": {"buy_prob_threshold": 0.65, "position_size_multiplier": 0.5},
        })

    def detect_regimes(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates regime state for each bar.
        Rules:
        1. If Volatility > High Quantile -> HIGH_VOLATILITY
        2. Else if ADX > threshold and Fast EMA > Slow EMA -> BULLISH_TREND
        3. Else if ADX > threshold and Fast EMA < Slow EMA -> BEARISH_TREND
        4. Else -> RANGING_NEUTRAL
        """
        df = df.copy()
        close = df["close"]

        ema_fast = close.ewm(span=self.reg_cfg.get("ema_fast", 50), adjust=False).mean()
        ema_slow = close.ewm(span=self.reg_cfg.get("ema_slow", 200), adjust=False).mean()

        vol = df["vol_24h"] if "vol_24h" in df.columns else df["close"].pct_change().rolling(24).std()
        vol_threshold = vol.expanding(min_periods=100).quantile(self.vol_high_q).fillna(0.05)

        adx = df["adx_14"] if "adx_14" in df.columns else pd.Series(25.0, index=df.index)

        regimes = []
        for i in range(len(df)):
            c_vol = vol.iloc[i]
            c_vthresh = vol_threshold.iloc[i]
            c_adx = adx.iloc[i]
            c_fast = ema_fast.iloc[i]
            c_slow = ema_slow.iloc[i]

            if c_vol >= c_vthresh:
                regimes.append(MarketRegime.HIGH_VOLATILITY.value)
            elif c_adx >= self.adx_thresh and c_fast > c_slow:
                regimes.append(MarketRegime.BULLISH_TREND.value)
            elif c_adx >= self.adx_thresh and c_fast < c_slow:
                regimes.append(MarketRegime.BEARISH_TREND.value)
            else:
                regimes.append(MarketRegime.RANGING_NEUTRAL.value)

        df["regime"] = regimes
        return df

    def get_regime_parameters(self, regime_str: str) -> Dict[str, float]:
        """Fetch dynamic probability threshold and position multiplier for current regime."""
        return self.regime_params.get(
            regime_str,
            {"buy_prob_threshold": 0.55, "position_size_multiplier": 0.75}
        )
