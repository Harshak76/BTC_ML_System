"""
Trend Pullback Strategy (Optimized V4.2) for btc_ml_system.
Features:
- Clean V4.0 LTF RSI Pullback (RSI <= 42 or Price near EMA20)
- Macro HTF (1d) Trend Strength Filter (EMA50 > EMA50_prev with min slope)
- Optimized 2.33x Risk-Reward Exit Multiple (SL 1.5x ATR, TP 3.5x ATR)
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from btc_ml_system.src.strategies.base_strategy import BaseStrategy

logger = logging.getLogger("btc_ml_system.strategies.trend_pullback")


class TrendPullbackStrategy(BaseStrategy):
    """Optimized Trend Pullback quantitative strategy module for equities."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.htf_ema_period = self.strat_cfg.get("htf_ema_period", 50)
        self.htf_slope_lookback = self.strat_cfg.get("htf_slope_lookback", 3)
        self.rsi_period = self.strat_cfg.get("ltf_rsi_period", 14)
        self.rsi_oversold = self.strat_cfg.get("ltf_rsi_oversold", 42)
        self.ema_fast_p = self.strat_cfg.get("ltf_ema_fast", 20)
        self.ema_slow_p = self.strat_cfg.get("ltf_ema_slow", 50)

    def evaluate_htf_trend(self, df_htf: pd.DataFrame) -> pd.DataFrame:
        """Evaluates Higher Timeframe trend confirmation (Price > EMA50 & EMA50 sloping up)."""
        df = df_htf.copy()
        close = df["close"]
        ema = close.ewm(span=self.htf_ema_period, adjust=False).mean()
        slope = ema.diff(self.htf_slope_lookback)

        # Requires positive slope and price > EMA50
        df["htf_trend_valid"] = (close > ema) & (slope > 0)
        return df

    def evaluate_signals(self, df_ltf: pd.DataFrame, df_htf: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Evaluates Clean V4.2 Trend Pullback rules on LTF data.
        """
        df = df_ltf.copy()
        close = df["close"]

        # 1. RSI (14)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/self.rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/self.rsi_period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        df["rsi"] = 100 - (100 / (1 + rs))

        # 2. LTF Trend Alignment (EMA20 > EMA50)
        ema20 = close.ewm(span=self.ema_fast_p, adjust=False).mean()
        ema50 = close.ewm(span=self.ema_slow_p, adjust=False).mean()
        df["ema20"] = ema20
        df["ema50"] = ema50
        is_ema_aligned = ema20 > ema50

        # 3. Pullback Entry Condition: RSI rebounding after dipping below oversold OR price near EMA20
        rsi_pullback = (df["rsi"].shift(1) <= self.rsi_oversold) & (df["rsi"] > df["rsi"].shift(1))
        price_near_ema = (close >= ema20 * 0.995) & (close <= ema20 * 1.01)
        is_pullback = (rsi_pullback | price_near_ema) & is_ema_aligned

        df["direction_valid"] = is_pullback

        # Merge HTF trend confirmation
        if df_htf is not None and not df_htf.empty:
            htf_df = self.evaluate_htf_trend(df_htf)
            htf_cols = ["close_time", "htf_trend_valid"]

            df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
            htf_df["close_time"] = pd.to_datetime(htf_df["close_time"], utc=True)

            df = pd.merge_asof(
                df.sort_values("close_time"),
                htf_df[htf_cols].sort_values("close_time"),
                on="close_time",
                direction="backward"
            )
            df["htf_trend_valid"] = df["htf_trend_valid"].fillna(False)
            df["direction_valid"] = df["direction_valid"] & df["htf_trend_valid"]
        else:
            df["htf_trend_valid"] = True

        return df
