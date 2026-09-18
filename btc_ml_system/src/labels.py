"""
Labeling Module for V2 btc_ml_system.
Includes:
- Dynamic Triple-Barrier Method (Marcos Lopez de Prado)
- 3-class target labeling (+1 LONG, -1 SHORT, 0 NEUTRAL)
- Meta-labeling target generation (Primary model active -> 1 if profitable trade, 0 otherwise)
- Sample weighting by volatility and return magnitude
"""

import logging
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger("btc_ml_system.labels")


class TripleBarrierLabeler:
    """Implements dynamic triple-barrier labeling with sample weighting and meta-labeling."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.lbl_cfg = config.get("labels", {})
        self.pt_mult = self.lbl_cfg.get("pt_multiplier", 1.5)
        self.sl_mult = self.lbl_cfg.get("sl_multiplier", 1.0)
        self.max_holding = self.lbl_cfg.get("max_vertical_barrier", 12)
        self.vol_window = self.lbl_cfg.get("volatility_window", 24)
        self.min_return = self.lbl_cfg.get("min_return", 0.002)

    def compute_daily_volatility(self, close: pd.Series) -> pd.Series:
        """Dynamic volatility estimator based on exponentially weighted standard deviation of log returns."""
        returns = np.log(close / close.shift(1))
        vol = returns.ewm(span=self.vol_window).std()
        return vol.fillna(0.01)

    def generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates triple-barrier labels for each bar.
        Returns original df enriched with:
        - target: +1 (PT hit first), -1 (SL hit first), 0 (Vertical barrier / hold)
        - target_binary: 1 if target == +1 else 0 (For long-only models)
        - sample_weight: Volatility & return magnitude scaled sample weight
        - pt_price, sl_price: Price targets computed dynamically
        """
        df = df.copy()
        close = df["close"]
        high = df["high"]
        low = df["low"]

        volatility = self.compute_daily_volatility(close)
        df["volatility"] = volatility

        n = len(df)
        labels = np.zeros(n, dtype=int)
        ret_magnitudes = np.zeros(n, dtype=float)

        close_arr = close.values
        high_arr = high.values
        low_arr = low.values
        vol_arr = volatility.values

        for i in range(n - self.max_holding):
            entry_price = close_arr[i]
            vol = vol_arr[i]

            # Dynamic barrier widths
            pt = entry_price * (1.0 + max(self.pt_mult * vol, self.min_return))
            sl = entry_price * (1.0 - max(self.sl_mult * vol, self.min_return))

            # Look forward up to max_holding bars
            future_highs = high_arr[i + 1 : i + 1 + self.max_holding]
            future_lows = low_arr[i + 1 : i + 1 + self.max_holding]

            pt_hit_idx = np.where(future_highs >= pt)[0]
            sl_hit_idx = np.where(future_lows <= sl)[0]

            first_pt = pt_hit_idx[0] if len(pt_hit_idx) > 0 else 999
            first_sl = sl_hit_idx[0] if len(sl_hit_idx) > 0 else 999

            if first_pt < first_sl:
                labels[i] = 1  # Profit Target hit first
                ret_magnitudes[i] = (pt - entry_price) / entry_price
            elif first_sl < first_pt:
                labels[i] = -1  # Stop Loss hit first
                ret_magnitudes[i] = (sl - entry_price) / entry_price
            else:
                labels[i] = 0  # Vertical barrier / exit at horizon
                ret_magnitudes[i] = abs((close_arr[i + self.max_holding] - entry_price) / entry_price)

        df["target"] = labels
        df["target_binary"] = np.where(labels == 1, 1, 0)
        df["ret_magnitude"] = ret_magnitudes

        # Sample Weighting (V2 Addition)
        vol_weights = df["volatility"] / (df["volatility"].mean() + 1e-10)
        mag_weights = df["ret_magnitude"] / (df["ret_magnitude"].mean() + 1e-10)
        df["sample_weight"] = (0.5 * vol_weights + 0.5 * mag_weights).clip(0.1, 5.0)

        return df

    def generate_meta_labels(
        self,
        df: pd.DataFrame,
        primary_preds: np.ndarray,
        min_primary_prob: float = 0.50
    ) -> pd.Series:
        """
        Meta-Labeling (V2 Addition):
        Secondary target = 1 if primary model took trade AND trade was profitable (target == +1),
        0 otherwise (trade resulted in loss or vertical barrier exit).
        """
        meta_target = np.zeros(len(df), dtype=int)
        for i in range(len(df)):
            if primary_preds[i] >= min_primary_prob:
                if df["target"].iloc[i] == 1:
                    meta_target[i] = 1  # True Positive (Profitable trade)
                else:
                    meta_target[i] = 0  # False Positive (Unprofitable trade)
            else:
                meta_target[i] = 0  # Abstain

        return pd.Series(meta_target, index=df.index, name="meta_target")
