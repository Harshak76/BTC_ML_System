"""
Directional Filter & 4h Higher Timeframe Confirmation Module for V3.3 btc_ml_system.
Includes:
- Market Structure Breakout Logic:
  1. Price closes above recent 20-bar high (by at least 0.4% breakout buffer in V3.3)
  2. Breakout candle body is strong (>= 50% of total bar range, bullish candle)
  3. Breakout volume is above average (>= 1.35x 24h rolling volume average in V3.3)
  4. 1h Short-Term Trend Quality (EMA20 > EMA50)
- Hard 4h Higher Timeframe Trend Confirmation (4h Close > 4h EMA50 & 4h EMA50 sloping up)
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger("btc_ml_system.direction")


class DirectionalFilter:
    """Evaluates Market Structure Breakout filters, 1h short-term trend quality, and 4h HTF trend confirmation."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.dir_cfg = config.get("direction_filter", {})
        self.htf_cfg = config.get("htf_confirmation", {})

        # Market Structure Breakout parameters
        self.lookback = self.dir_cfg.get("lookback_period", 20)
        self.vol_sma_period = self.dir_cfg.get("volume_sma_period", 24)
        self.min_vol_ratio = self.dir_cfg.get("min_volume_ratio", 1.35)
        self.min_body_ratio = self.dir_cfg.get("min_body_ratio", 0.50)
        # Support both config key names ('breakout_buffer_pct' or 'min_breakout_pct')
        self.min_breakout_pct = self.dir_cfg.get("breakout_buffer_pct", self.dir_cfg.get("min_breakout_pct", 0.004))

        # 1h Short-term Trend Quality parameters
        self.require_ema_alignment = self.dir_cfg.get("require_ema_alignment", True)
        self.ema_fast_p = self.dir_cfg.get("ema_fast", 20)
        self.ema_slow_p = self.dir_cfg.get("ema_slow", 50)

        # 4h HTF parameters
        self.htf_enabled = self.htf_cfg.get("enabled", True)
        self.htf_ema_period = self.htf_cfg.get("ema_period", 50)
        self.htf_slope_lookback = self.htf_cfg.get("slope_lookback", 3)

    def evaluate_htf_confirmation(self, df_4h: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates 4h HTF EMA(50) and slope.
        Returns DataFrame with 'htf_trend_valid' boolean column.
        """
        df = df_4h.copy()
        close = df["close"]
        ema = close.ewm(span=self.htf_ema_period, adjust=False).mean()
        slope = ema.diff(self.htf_slope_lookback)

        df["htf_ema_50"] = ema
        df["htf_ema_slope"] = slope

        price_above = close > ema
        slope_up = slope > 0

        df["htf_trend_valid"] = price_above & slope_up
        return df

    def evaluate_direction(self, df_1h: pd.DataFrame, df_4h: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Evaluates 1h Market Structure Breakout rules + 1h EMA alignment, and merges 4h HTF confirmation non-repainting.
        """
        df = df_1h.copy()
        close = df["close"]
        open_p = df["open"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # Rule 1: 20-bar rolling high (excluding current bar) + Stricter Breakout Buffer (0.4%)
        rolling_high = high.shift(1).rolling(self.lookback).max()
        breakout_thresh = rolling_high * (1.0 + self.min_breakout_pct)
        is_breakout = close > breakout_thresh

        # Rule 2: Strong candle body ratio >= 50% (No Dojis, Bullish candle)
        candle_range = (high - low).replace(0, 1e-10)
        candle_body = (close - open_p).abs()
        body_ratio = candle_body / candle_range
        is_strong_body = (close > open_p) & (body_ratio >= self.min_body_ratio)

        # Rule 3: Above average volume >= 1.35x 24h average
        vol_sma = volume.rolling(self.vol_sma_period).mean().replace(0, 1e-10)
        vol_ratio = volume / vol_sma
        is_high_volume = vol_ratio >= self.min_vol_ratio

        # Rule 4: 1h Short-Term Trend Quality (EMA20 > EMA50)
        if self.require_ema_alignment:
            ema20 = close.ewm(span=self.ema_fast_p, adjust=False).mean()
            ema50 = close.ewm(span=self.ema_slow_p, adjust=False).mean()
            is_ema_aligned = ema20 > ema50
        else:
            is_ema_aligned = True

        # Combine 1h Market Structure Breakout & Trend Alignment Conditions
        dir_valid = is_breakout & is_strong_body & is_high_volume & is_ema_aligned
        df["direction_valid"] = dir_valid

        # Hard 4h HTF Confirmation merge (non-repainting via merge_asof)
        if self.htf_enabled and df_4h is not None and not df_4h.empty:
            htf_df = self.evaluate_htf_confirmation(df_4h)
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


class MultiTimeframeFilter:
    """
    Multi-Timeframe Confirmation Filter for BTC-ML-System.
    Evaluates Higher Timeframe (HTF) trend alignment using configurable EMAs and strength levels.
    
    Trend definitions on Higher Timeframe:
    - Bullish: Price > EMA(50) AND EMA(50) > EMA(200)
    - Bearish: Price < EMA(50) AND EMA(50) < EMA(200)

    Filter Strengths:
    - Strict: Requires Price > EMA(50) > EMA(200) AND EMA(50) slope > 0 (bullish), or Price < EMA(50) < EMA(200) AND EMA(50) slope < 0 (bearish).
    - Medium (Default): Requires Price > EMA(50) > EMA(200) (bullish), or Price < EMA(50) < EMA(200) (bearish).
    - Light: Requires Price > EMA(50) OR EMA(50) > EMA(200) (bullish), or Price < EMA(50) OR EMA(50) < EMA(200) (bearish).
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mtf_cfg = config.get("multi_timeframe_filter", config.get("htf_confirmation", {}))
        self.enabled = self.mtf_cfg.get("enabled", True)
        self.strength = str(self.mtf_cfg.get("strength", "Medium")).title()
        self.ema_fast_p = self.mtf_cfg.get("ema_fast", self.mtf_cfg.get("ema_period", 50))
        self.ema_slow_p = self.mtf_cfg.get("ema_slow", 200)
        self.slope_lookback = self.mtf_cfg.get("slope_lookback", 3)

    def evaluate_htf_trend(self, df_htf: pd.DataFrame) -> pd.DataFrame:
        """
        Calculates EMA(50) and EMA(200) on HTF dataset and determines HTF trend.
        Returns HTF DataFrame with 'htf_bullish', 'htf_bearish', 'htf_trend_valid' boolean columns.
        """
        if df_htf is None or df_htf.empty:
            return pd.DataFrame()

        df = df_htf.copy()
        close = df["close"]

        ema_fast = close.ewm(span=self.ema_fast_p, adjust=False).mean()
        ema_slow = close.ewm(span=self.ema_slow_p, adjust=False).mean()
        slope_fast = ema_fast.diff(self.slope_lookback)

        df["htf_ema_fast"] = ema_fast
        df["htf_ema_slow"] = ema_slow
        df["htf_ema_slope"] = slope_fast

        if self.strength == "Strict":
            htf_bullish = (close > ema_fast) & (ema_fast > ema_slow) & (slope_fast > 0)
            htf_bearish = (close < ema_fast) & (ema_fast < ema_slow) & (slope_fast < 0)
        elif self.strength == "Light":
            htf_bullish = (close > ema_fast) | (ema_fast > ema_slow)
            htf_bearish = (close < ema_fast) | (ema_fast < ema_slow)
        else:  # "Medium" (Default)
            htf_bullish = (close > ema_fast) & (ema_fast > ema_slow)
            htf_bearish = (close < ema_fast) & (ema_fast < ema_slow)

        df["htf_bullish"] = htf_bullish
        df["htf_bearish"] = htf_bearish
        df["htf_trend_valid"] = htf_bullish
        return df

    def apply_filter(self, df_ltf: pd.DataFrame, df_htf: Optional[pd.DataFrame] = None, signal_type: str = "BUY") -> pd.DataFrame:
        """
        Merges HTF trend non-repainting using pd.merge_asof and applies MTF filtering.
        """
        df = df_ltf.copy()

        if not self.enabled:
            if df_htf is not None and not df_htf.empty:
                # Fallback to legacy single EMA(50) + slope HTF confirmation baseline
                htf_df = df_htf.copy()
                close = htf_df["close"]
                ema = close.ewm(span=self.ema_fast_p, adjust=False).mean()
                slope = ema.diff(self.slope_lookback)
                htf_df["htf_bullish"] = (close > ema) & (slope > 0)
                htf_df["htf_bearish"] = (close < ema) & (slope < 0)
                htf_df["htf_trend_valid"] = htf_df["htf_bullish"]
                htf_cols = ["close_time", "htf_bullish", "htf_bearish", "htf_trend_valid"]

                df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
                htf_df["close_time"] = pd.to_datetime(htf_df["close_time"], utc=True)

                merged = pd.merge_asof(
                    df.sort_values("close_time"),
                    htf_df[htf_cols].sort_values("close_time"),
                    on="close_time",
                    direction="backward"
                )
                merged["htf_bullish"] = merged["htf_bullish"].fillna(False)
                merged["htf_bearish"] = merged["htf_bearish"].fillna(False)
                merged["htf_trend_valid"] = merged["htf_trend_valid"].fillna(False)
                merged["direction_valid"] = merged.get("direction_valid", True) & merged["htf_trend_valid"]
                return merged
            else:
                df["htf_trend_valid"] = True
                df["htf_bullish"] = True
                df["htf_bearish"] = True
                return df

        if df_htf is None or df_htf.empty:
            df["htf_trend_valid"] = True
            df["htf_bullish"] = True
            df["htf_bearish"] = True
            return df

        htf_df = self.evaluate_htf_trend(df_htf)
        htf_cols = ["close_time", "htf_bullish", "htf_bearish", "htf_trend_valid"]

        df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
        htf_df["close_time"] = pd.to_datetime(htf_df["close_time"], utc=True)

        merged = pd.merge_asof(
            df.sort_values("close_time"),
            htf_df[htf_cols].sort_values("close_time"),
            on="close_time",
            direction="backward"
        )
        merged["htf_bullish"] = merged["htf_bullish"].fillna(False)
        merged["htf_bearish"] = merged["htf_bearish"].fillna(False)
        merged["htf_trend_valid"] = merged["htf_trend_valid"].fillna(False)

        # Apply filtering rule
        if signal_type.upper() in ["BUY", "LONG"]:
            required_mask = merged["htf_bullish"]
        elif signal_type.upper() in ["SELL", "SHORT"]:
            required_mask = merged["htf_bearish"]
        else:
            required_mask = merged["htf_trend_valid"]

        # Log any signals that were valid on LTF but blocked by MTF
        if "direction_valid" in merged.columns:
            filtered_mask = merged["direction_valid"] & (~required_mask)
            filtered_count = int(filtered_mask.sum())
            if filtered_count > 0:
                logger.info(
                    f"MultiTimeframeFilter [{self.strength} mode]: Filtered out {filtered_count} signals "
                    f"where LTF generated '{signal_type}' but HTF trend was not confirmed."
                )

        merged["direction_valid"] = merged.get("direction_valid", True) & required_mask
        merged["htf_trend_valid"] = required_mask

        return merged


class SessionFilter:
    """
    Session Filter for btc_ml_system.
    Restricts trade entries to specific UTC hour ranges (e.g. US Session 14:00 - 22:00 UTC).
    Configurable in YAML:
      session_filter:
        enabled: true / false
        start_hour: 14
        end_hour: 22
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sess_cfg = config.get("session_filter", {})
        self.enabled = bool(self.sess_cfg.get("enabled", False))
        self.start_hour = int(self.sess_cfg.get("start_hour", 14))
        self.end_hour = int(self.sess_cfg.get("end_hour", 22))

    def is_session_valid(self, timestamp: pd.Timestamp) -> bool:
        """Checks if given timestamp falls within allowed UTC session hours."""
        if not self.enabled:
            return True

        ts = pd.to_datetime(timestamp, utc=True)
        hour = ts.hour

        if self.start_hour <= self.end_hour:
            return self.start_hour <= hour < self.end_hour
        else:
            return (hour >= self.start_hour) or (hour < self.end_hour)

    def apply_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds 'session_valid' column to DataFrame and updates 'direction_valid' if enabled.
        """
        df = df.copy()
        if not self.enabled:
            df["session_valid"] = True
            return df

        timestamps = pd.to_datetime(df["open_time"], utc=True)
        hours = timestamps.dt.hour

        if self.start_hour <= self.end_hour:
            valid_mask = (hours >= self.start_hour) & (hours < self.end_hour)
        else:
            valid_mask = (hours >= self.start_hour) | (hours < self.end_hour)

        df["session_valid"] = valid_mask

        if "direction_valid" in df.columns:
            filtered_mask = df["direction_valid"] & (~valid_mask)
            filtered_count = int(filtered_mask.sum())
            if filtered_count > 0:
                logger.info(
                    f"SessionFilter: Filtered out {filtered_count} signals outside "
                    f"allowed session window ({self.start_hour:02d}:00–{self.end_hour:02d}:00 UTC)."
                )

        return df


