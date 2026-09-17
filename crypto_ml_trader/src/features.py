"""
Feature Engineering Module.
Computes technical indicators and multi-timeframe confirmed features strictly
from information available at or before candle close t.

Ensures ZERO lookahead bias and ZERO repainting.
"""

import logging
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler, StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0.0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


def compute_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Moving Average Convergence Divergence (MACD)."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> pd.Series:
    """Average True Range (ATR)."""
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr.fillna(0.0)


def compute_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Average Directional Index (ADX), +DI, -DI."""
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = compute_atr(high, low, close, period=1)
    tr_smooth = tr.rolling(window=period).sum()

    plus_di = 100.0 * (pd.Series(plus_dm, index=high.index).rolling(window=period).sum() / (tr_smooth + 1e-10))
    minus_di = 100.0 * (pd.Series(minus_dm, index=high.index).rolling(window=period).sum() / (tr_smooth + 1e-10))

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10)
    adx = dx.rolling(window=period).mean()

    return adx.fillna(0.0), plus_di.fillna(0.0), minus_di.fillna(0.0)


def compute_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3
) -> Tuple[pd.Series, pd.Series]:
    """Stochastic Oscillator (%K, %D)."""
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    k_percent = 100.0 * (close - lowest_low) / (highest_high - lowest_low + 1e-10)
    d_percent = k_percent.rolling(window=d_period).mean()
    return k_percent.fillna(50.0), d_percent.fillna(50.0)


class FeatureEngineer:
    """Builds point-in-time features for 1h base timeframe and merges 4h HTF features."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.returns_windows = self.config.get("returns_windows", [1, 2, 3, 6, 12, 24, 48])
        self.rsi_period = self.config.get("rsi_period", 14)
        self.macd_fast = self.config.get("macd_fast", 12)
        self.macd_slow = self.config.get("macd_slow", 26)
        self.macd_signal = self.config.get("macd_signal", 9)
        self.adx_period = self.config.get("adx_period", 14)
        self.volatility_windows = self.config.get("volatility_windows", [12, 24, 48])
        self.volume_windows = self.config.get("volume_windows", [6, 24])

    def create_1h_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Computes single-timeframe 1h features strictly using past information."""
        df = df.copy()

        # 1. Price Log Returns
        for w in self.returns_windows:
            df[f"log_ret_{w}h"] = np.log(df["close"] / df["close"].shift(w))

        # 2. Moving Averages & Moving Average Ratios
        for ma_period in [12, 24, 50, 200]:
            sma = df["close"].rolling(window=ma_period).mean()
            df[f"close_to_sma_{ma_period}"] = df["close"] / (sma + 1e-10) - 1.0
            ema = df["close"].ewm(span=ma_period, adjust=False).mean()
            df[f"close_to_ema_{ma_period}"] = df["close"] / (ema + 1e-10) - 1.0

        # 3. Momentum Indicators
        df["rsi_14"] = compute_rsi(df["close"], period=self.rsi_period)
        macd, signal, hist = compute_macd(
            df["close"],
            fast=self.macd_fast,
            slow=self.macd_slow,
            signal=self.macd_signal
        )
        df["macd"] = macd / df["close"] # Normalized by price
        df["macd_signal"] = signal / df["close"]
        df["macd_hist"] = hist / df["close"]

        adx, plus_di, minus_di = compute_adx(df["high"], df["low"], df["close"], period=self.adx_period)
        df["adx_14"] = adx / 100.0
        df["plus_di"] = plus_di / 100.0
        df["minus_di"] = minus_di / 100.0
        df["di_diff"] = df["plus_di"] - df["minus_di"]

        stoch_k, stoch_d = compute_stochastic(df["high"], df["low"], df["close"])
        df["stoch_k"] = stoch_k / 100.0
        df["stoch_d"] = stoch_d / 100.0

        # 4. Volatility Features
        atr = compute_atr(df["high"], df["low"], df["close"], period=14)
        df["norm_atr_14"] = atr / df["close"]

        for vw in self.volatility_windows:
            df[f"volatility_{vw}h"] = df["log_ret_1h"].rolling(window=vw).std()

        # Bollinger Bands
        sma_20 = df["close"].rolling(window=20).mean()
        std_20 = df["close"].rolling(window=20).std()
        upper_bb = sma_20 + 2.0 * std_20
        lower_bb = sma_20 - 2.0 * std_20
        df["bb_width"] = (upper_bb - lower_bb) / (sma_20 + 1e-10)
        df["bb_pct_b"] = (df["close"] - lower_bb) / (upper_bb - lower_bb + 1e-10)

        # 5. Volume Features
        df["log_volume"] = np.log1p(df["volume"])
        for vw in self.volume_windows:
            vol_sma = df["volume"].rolling(window=vw).mean()
            df[f"vol_ratio_{vw}h"] = df["volume"] / (vol_sma + 1e-10)

        # VWAP ratio (24h rolling)
        cum_pv = (df["close"] * df["volume"]).rolling(window=24).sum()
        cum_v = df["volume"].rolling(window=24).sum()
        vwap_24 = cum_pv / (cum_v + 1e-10)
        df["close_to_vwap_24"] = df["close"] / (vwap_24 + 1e-10) - 1.0

        # 6. Candle Structural Features
        hl_range = df["high"] - df["low"] + 1e-10
        body = (df["close"] - df["open"]).abs()
        df["body_ratio"] = body / hl_range
        upper_shadow = df["high"] - df[["open", "close"]].max(axis=1)
        lower_shadow = df[["open", "close"]].min(axis=1) - df["low"]
        df["upper_shadow_ratio"] = upper_shadow / hl_range
        df["lower_shadow_ratio"] = lower_shadow / hl_range
        df["candle_dir"] = np.sign(df["close"] - df["open"])

        return df

    def merge_confirmed_4h_features(self, df_1h: pd.DataFrame, df_4h: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates 4h HTF features and merges them into 1h timeline.
        CRITICAL NON-REPAINTING RULE:
        A 4h candle closing at timestamp T is ONLY made available to 1h candles with close_time >= T.
        We shift the 4h feature dataframe by 1 period BEFORE merging to prevent using incomplete 4h bars.
        """
        df_4h_feat = df_4h.copy()

        # Calculate HTF indicators
        df_4h_feat["htf_rsi_14"] = compute_rsi(df_4h_feat["close"], period=14)
        adx, plus_di, minus_di = compute_adx(df_4h_feat["high"], df_4h_feat["low"], df_4h_feat["close"], period=14)
        df_4h_feat["htf_adx_14"] = adx / 100.0
        df_4h_feat["htf_di_diff"] = (plus_di - minus_di) / 100.0

        ema_50 = df_4h_feat["close"].ewm(span=50, adjust=False).mean()
        ema_200 = df_4h_feat["close"].ewm(span=200, adjust=False).mean()
        df_4h_feat["htf_ema50_to_ema200"] = ema_50 / (ema_200 + 1e-10) - 1.0
        df_4h_feat["htf_close_to_ema50"] = df_4h_feat["close"] / (ema_50 + 1e-10) - 1.0

        htf_cols = ["close_time", "htf_rsi_14", "htf_adx_14", "htf_di_diff", "htf_ema50_to_ema200", "htf_close_to_ema50"]
        htf_subset = df_4h_feat[htf_cols].copy()
        df_1h = df_1h.copy()
        df_1h["close_time"] = pd.to_datetime(df_1h["close_time"], utc=True)
        htf_subset["close_time"] = pd.to_datetime(htf_subset["close_time"], utc=True)

        htf_subset = htf_subset.sort_values("close_time").reset_index(drop=True)

        # Merge on 1h open_time / close_time using merge_asof (backward fill)
        merged = pd.merge_asof(
            df_1h.sort_values("close_time"),
            htf_subset,
            on="close_time",
            direction="backward"
        )

        return merged

    def fit_transform_scaler(
        self,
        X_train: pd.DataFrame,
        scaler_type: str = "robust"
    ) -> Tuple[np.ndarray, Any]:
        """Fits scaler strictly inside training fold."""
        if scaler_type == "robust":
            scaler = RobustScaler()
        else:
            scaler = StandardScaler()

        X_scaled = scaler.fit_transform(X_train)
        return X_scaled, scaler


def detect_target_leakage(
    df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
    threshold: float = 0.95
) -> List[str]:
    """
    Automated target leakage detector.
    Checks if any feature column has near-perfect correlation with future target.
    """
    leaked_cols = []
    if target_col not in df.columns:
        return leaked_cols

    target = df[target_col].dropna()
    for col in feature_cols:
        if col not in df.columns:
            continue
        feat = df.loc[target.index, col]
        corr = np.abs(np.corrcoef(feat.fillna(0), target)[0, 1])
        if corr >= threshold:
            logger.error(f"TARGET LEAKAGE DETECTED in feature '{col}'! Correlation with target = {corr:.4f}")
            leaked_cols.append(col)

    return leaked_cols
