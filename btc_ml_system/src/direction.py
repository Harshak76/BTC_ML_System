"""
Directional Filter Module for V3 btc_ml_system.
Implements the fixed single directional rule:
1. Price must be above EMA(50)
2. EMA(50) must be sloping upward
"""

import logging
from typing import Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger("btc_ml_system.direction")


class DirectionalFilter:
    """Evaluates the fixed EMA(50) directional condition."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.dir_cfg = config.get("direction_filter", {})
        self.ema_period = self.dir_cfg.get("ema_period", 50)
        self.slope_lookback = self.dir_cfg.get("slope_lookback", 3)
        self.require_price_above = self.dir_cfg.get("require_price_above_ema", True)
        self.require_slope_up = self.dir_cfg.get("require_ema_sloping_up", True)

    def evaluate_direction(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates EMA(50) and evaluates price > EMA and EMA slope > 0.
        Adds columns:
        - ema_50: Exponential moving average (50)
        - ema_slope: Difference over slope_lookback bars
        - direction_valid: Boolean flag True if all directional conditions pass
        """
        df = df.copy()
        close = df["close"]

        ema = close.ewm(span=self.ema_period, adjust=False).mean()
        slope = ema.diff(self.slope_lookback)

        df["ema_50"] = ema
        df["ema_slope"] = slope

        price_above = close > ema
        slope_up = slope > 0

        valid = pd.Series(True, index=df.index)
        if self.require_price_above:
            valid = valid & price_above
        if self.require_slope_up:
            valid = valid & slope_up

        df["direction_valid"] = valid
        return df
