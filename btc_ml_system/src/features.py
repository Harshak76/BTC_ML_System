"""
Feature Engineering Module for V2 btc_ml_system.
Features generated strictly without lookahead bias.
Includes V2 additions:
- Multi-timeframe trend & returns
- Technical indicators (RSI, MACD, ADX, Volatility)
- Interaction features (RSI * Volatility, Volatility * Return)
- Volume imbalance & Buy/Sell pressure
- Volatility regime quantiles
- Feature stability tracking across splits
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger("btc_ml_system.features")


class FeatureEngineer:
    """Generates technical, statistical, and microstructural features."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.feat_cfg = config.get("features", {})
        self.returns_windows = self.feat_cfg.get("returns_windows", [1, 2, 3, 6, 12, 24, 48])
        self.rsi_period = self.feat_cfg.get("rsi_period", 14)
        self.macd_fast = self.feat_cfg.get("macd_fast", 12)
        self.macd_slow = self.feat_cfg.get("macd_slow", 26)
        self.macd_signal = self.feat_cfg.get("macd_signal", 9)
        self.adx_period = self.feat_cfg.get("adx_period", 14)
        self.vol_windows = self.feat_cfg.get("volatility_windows", [12, 24, 48])
        self.volume_windows = self.feat_cfg.get("volume_windows", [6, 24])

    def compute_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """RSI calculation using exponential moving average (Wilder style)."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))

    def compute_macd(self, series: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD line, signal line, and histogram."""
        ema_fast = series.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = series.ewm(span=self.macd_slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=self.macd_signal, adjust=False).mean()
        hist = macd - signal
        return macd, signal, hist

    def compute_adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average Directional Index (ADX)."""
        high, low, close = df["high"], df["low"], df["close"]
        plus_dm = high.diff()
        minus_dm = low.diff().abs()

        plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0.0)
        minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0.0)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        tr_smooth = pd.Series(tr).ewm(alpha=1/period, adjust=False).mean()
        plus_di = 100 * (pd.Series(plus_dm).ewm(alpha=1/period, adjust=False).mean() / (tr_smooth + 1e-10))
        minus_di = 100 * (pd.Series(minus_dm).ewm(alpha=1/period, adjust=False).mean() / (tr_smooth + 1e-10))

        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        return adx

    def create_features(self, df_1h: pd.DataFrame, df_4h: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Creates all features for 1h candles, including 4h HTF features via non-repainting merge_asof.
        """
        df = df_1h.copy()

        # 1. Log Returns
        for w in self.returns_windows:
            df[f"ret_{w}h"] = np.log(df["close"] / df["close"].shift(w))

        # 2. Technical Indicators
        df["rsi_14"] = self.compute_rsi(df["close"], self.rsi_period)
        macd, signal, hist = self.compute_macd(df["close"])
        df["macd"] = macd
        df["macd_signal"] = signal
        df["macd_hist"] = hist
        df["adx_14"] = self.compute_adx(df, self.adx_period)

        # 3. Volatility Features
        for w in self.vol_windows:
            df[f"vol_{w}h"] = df["ret_1h"].rolling(w).std() * np.sqrt(24 * 365)
            df[f"parkinson_vol_{w}h"] = np.sqrt(
                (1 / (4 * np.log(2))) * (np.log(df["high"] / df["low"]) ** 2).rolling(w).mean()
            ) * np.sqrt(24 * 365)

        # 4. Microstructure Features (V2 Additions)
        if "taker_buy_base" in df.columns and "volume" in df.columns:
            # Volume imbalance: (taker_buy - (vol - taker_buy)) / vol
            df["volume_imbalance"] = (2 * df["taker_buy_base"] - df["volume"]) / (df["volume"] + 1e-10)
            df["buy_sell_pressure"] = df["taker_buy_quote"] / (df["quote_volume"] + 1e-10)
        else:
            df["volume_imbalance"] = 0.0
            df["buy_sell_pressure"] = 0.5

        for w in self.volume_windows:
            df[f"vol_ratio_{w}h"] = df["volume"] / (df["volume"].rolling(w).mean() + 1e-10)

        # 5. Interaction Features (V2 Additions)
        if self.feat_cfg.get("interaction_features", True):
            df["rsi_x_vol24"] = df["rsi_14"] * df["vol_24h"]
            df["ret1_x_vol12"] = df["ret_1h"] * df["vol_12h"]
            df["adx_x_macd_hist"] = df["adx_14"] * df["macd_hist"]

        # 6. Volatility Quantiles (V2 Additions)
        if "vol_24h" in df.columns:
            vol_q25 = df["vol_24h"].expanding(min_periods=100).quantile(0.25)
            vol_q75 = df["vol_24h"].expanding(min_periods=100).quantile(0.75)
            df["vol_regime_quantile"] = np.where(df["vol_24h"] < vol_q25, 0, np.where(df["vol_24h"] > vol_q75, 2, 1))

        # 7. Higher Timeframe (4h) Features via pd.merge_asof
        if df_4h is not None and not df_4h.empty:
            df_htf = df_4h.copy()
            df_htf["htf_ret_4h"] = np.log(df_htf["close"] / df_htf["close"].shift(1))
            df_htf["htf_rsi"] = self.compute_rsi(df_htf["close"], 14)
            df_htf["htf_ema_fast"] = df_htf["close"].ewm(span=50, adjust=False).mean()
            df_htf["htf_ema_slow"] = df_htf["close"].ewm(span=200, adjust=False).mean()
            df_htf["htf_trend"] = np.where(df_htf["htf_ema_fast"] > df_htf["htf_ema_slow"], 1, -1)

            htf_cols = ["close_time", "htf_ret_4h", "htf_rsi", "htf_trend"]
            
            # Ensure UTC timezone alignment for merge_asof
            df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
            df_htf["close_time"] = pd.to_datetime(df_htf["close_time"], utc=True)

            df = pd.merge_asof(
                df.sort_values("close_time"),
                df_htf[htf_cols].sort_values("close_time"),
                on="close_time",
                direction="backward"
            )

        return df

    def get_feature_names(self, df: pd.DataFrame) -> List[str]:
        """Returns list of generated feature column names (excluding raw OHLCV metadata)."""
        exclude = ["open_time", "close_time", "open", "high", "low", "close", "volume",
                   "quote_volume", "trades", "taker_buy_base", "taker_buy_quote"]
        return [c for c in df.columns if c not in exclude]
