"""
Dedicated 4-Hour BTC Trend & Volatility Regime Strategy (V4.5 Final Push) for btc_ml_system.
Operating on 4-hour candles to filter market noise and capture macro trends:
- Timeframe: 4h Base Candles / Daily HTF Trend
- Filter 1: Daily HTF EMA(50) slope confirmation
- Filter 2: 4h Volatility Regime (CALM & NORMAL allowed)
- Filter 3: 4h Volume Trend Confirmation (Volume >= 1.15x 24h average)
- Filter 4: 4h Trend Alignment (EMA20 > EMA50) + Donchian Channel / RSI Pullback Rebound
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from btc_ml_system.src.strategies.base_strategy import BaseStrategy
from btc_ml_system.src.direction import MultiTimeframeFilter

logger = logging.getLogger("btc_ml_system.strategies.btc_htf_trend")


class BtcHtfTrendStrategy(BaseStrategy):
    """Final 4-Hour Higher Timeframe Trend Strategy for Bitcoin using MultiTimeframeFilter."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.mtf_filter = MultiTimeframeFilter(config)
        self.rsi_period = self.strat_cfg.get("ltf_rsi_period", 14)
        self.rsi_oversold = self.strat_cfg.get("ltf_rsi_oversold", 45)
        self.ema_fast_p = self.strat_cfg.get("ltf_ema_fast", 20)
        self.ema_slow_p = self.strat_cfg.get("ltf_ema_slow", 50)
        self.donchian_period = self.strat_cfg.get("donchian_period", 20)
        self.min_vol_ratio = self.strat_cfg.get("min_vol_ratio", 1.15)

    def evaluate_htf_trend(self, df_htf: pd.DataFrame) -> pd.DataFrame:
        """Evaluates Daily HTF trend confirmation using MultiTimeframeFilter."""
        return self.mtf_filter.evaluate_htf_trend(df_htf)

    def evaluate_signals(self, df_ltf: pd.DataFrame, df_htf: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Evaluates 4h BTC Trend & Volume-Confirmed Momentum Entry rules with MultiTimeframeFilter.
        """
        df = df_ltf.copy()
        close = df["close"]
        high = df["high"]
        volume = df["volume"]

        # 1. 4h RSI (14)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/self.rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/self.rsi_period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        df["rsi"] = 100 - (100 / (1 + rs))

        # 2. 4h EMA Alignment (EMA20 > EMA50)
        ema20 = close.ewm(span=self.ema_fast_p, adjust=False).mean()
        ema50 = close.ewm(span=self.ema_slow_p, adjust=False).mean()
        df["ema20"] = ema20
        df["ema50"] = ema50
        is_ema_aligned = ema20 > ema50

        # 3. 4h Volume Trend Confirmation
        vol_sma = volume.rolling(24).mean().replace(0, 1e-10)
        vol_ratio = volume / vol_sma
        is_vol_confirmed = vol_ratio >= self.min_vol_ratio

        # 4. 4h Donchian Channel Breakout OR 4h RSI Pullback Rebound
        donchian_high = high.shift(1).rolling(self.donchian_period).max()
        is_donchian_break = close > donchian_high
        rsi_rebound = (df["rsi"].shift(1) <= self.rsi_oversold) & (df["rsi"] > df["rsi"].shift(1))

        is_selective_entry = (is_donchian_break | rsi_rebound) & is_ema_aligned & is_vol_confirmed

        df["direction_valid"] = is_selective_entry

        # Apply MultiTimeframeFilter for Daily HTF confirmation
        df = self.mtf_filter.apply_filter(df, df_htf, signal_type="BUY")

        return df

