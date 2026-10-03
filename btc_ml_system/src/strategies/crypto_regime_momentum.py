"""
Specialized Crypto Regime & Squeeze Momentum Strategy (V4.2 Optimized) for btc_ml_system.
Designed specifically for Crypto assets (ETHUSDT, BTCUSDT):
- Filter 1: Strictly CALM Volatility Regime (Blocks choppy/HIGH regimes)
- Filter 2: 4h HTF EMA50 Slope Confirmation
- Filter 3: Bollinger Band Squeeze Bandwidth Filter (Bandwidth <= 0.05) & RSI Expansion (RSI >= 52)
- Filter 4: Upgraded 2.33x Risk-Reward Exit Multiple (SL 1.5x ATR, TP 3.5x ATR)
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from btc_ml_system.src.strategies.base_strategy import BaseStrategy
from btc_ml_system.src.direction import MultiTimeframeFilter

logger = logging.getLogger("btc_ml_system.strategies.crypto_regime_momentum")


class CryptoRegimeMomentumStrategy(BaseStrategy):
    """Optimized quantitative strategy module for Crypto assets using MultiTimeframeFilter."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.mtf_filter = MultiTimeframeFilter(config)
        self.bb_period = self.strat_cfg.get("bb_period", 20)
        self.bb_std_mult = self.strat_cfg.get("bb_std_mult", 2.0)
        self.max_bb_bandwidth = self.strat_cfg.get("max_bb_bandwidth", 0.05)
        self.rsi_period = self.strat_cfg.get("rsi_period", 14)
        self.min_rsi = self.strat_cfg.get("min_rsi", 52.0)

    def evaluate_htf_trend(self, df_htf: pd.DataFrame) -> pd.DataFrame:
        """Evaluates Higher Timeframe trend confirmation using MultiTimeframeFilter."""
        return self.mtf_filter.evaluate_htf_trend(df_htf)

    def evaluate_signals(self, df_ltf: pd.DataFrame, df_htf: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Evaluates Calm Regime Bollinger Squeeze Expansion Momentum rules on LTF crypto data with MultiTimeframeFilter.
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

        # 2. Bollinger Bands & Bandwidth Squeeze
        sma = close.rolling(self.bb_period).mean()
        std = close.rolling(self.bb_period).std()
        upper_bb = sma + (self.bb_std_mult * std)
        lower_bb = sma - (self.bb_std_mult * std)
        bb_bandwidth = (upper_bb - lower_bb) / sma.replace(0, 1e-10)
        df["bb_bandwidth"] = bb_bandwidth

        # 3. Squeeze & Momentum Expansion Entry Condition
        is_squeeze = (bb_bandwidth.shift(1) <= self.max_bb_bandwidth) | (bb_bandwidth <= self.max_bb_bandwidth * 1.2)
        is_momentum_break = (close > upper_bb) & (df["rsi"] >= self.min_rsi) & is_squeeze

        # Filter by volatility regime if classified
        if "vol_regime_favorable" in df.columns:
            is_momentum_break = is_momentum_break & df["vol_regime_favorable"]
        elif "volatility_regime" in df.columns:
            is_calm = df["volatility_regime"] == "CALM"
            is_momentum_break = is_momentum_break & is_calm

        df["direction_valid"] = is_momentum_break

        # Apply MultiTimeframeFilter for HTF confirmation
        df = self.mtf_filter.apply_filter(df, df_htf, signal_type="BUY")

        return df

