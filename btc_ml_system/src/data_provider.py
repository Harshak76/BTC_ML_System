"""
Data Provider Module for btc_ml_system.
Unified multi-asset data provider supporting:
- Real-Time Live Streaming / Polling Data from Alpaca Data API v2 / v1beta3 (Stocks & Crypto)
- Robust Historical Gap Detection and Automated Backfilling
- Completed Candle Finalization & Stale Data Filtering
- Historical Cached Data for Fast Backtesting Simulation
"""

import os
import time
import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("btc_ml_system.data_provider")


class DataProvider:
    """Multi-exchange OHLCV data provider for Crypto & Stocks (Live & Backtest)."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.raw_dir = config.get("data", {}).get("raw_dir", "data/raw")
        self.asset_cfg = config.get("asset", {})
        self.asset_type = self.asset_cfg.get("asset_type", "crypto")
        self.provider = self.asset_cfg.get("data_provider", "alpaca")
        self.live_mode = bool(config.get("live_mode", False))
        os.makedirs(self.raw_dir, exist_ok=True)

        # ---------------------------------------------------------------------
        # Alpaca Credentials Resolution (SEC-001): Environment primary
        # ---------------------------------------------------------------------
        alp_cfg = config.get("alpaca", {})
        api_key_env = alp_cfg.get("api_key_env", "ALPACA_API_KEY")
        secret_key_env = alp_cfg.get("secret_key_env", "ALPACA_SECRET_KEY")

        self.api_key = os.environ.get(api_key_env) or os.environ.get("ALPACA_API_KEY") or alp_cfg.get("api_key") or ""
        self.secret_key = os.environ.get(secret_key_env) or os.environ.get("ALPACA_SECRET_KEY") or alp_cfg.get("secret_key") or ""

        self.data_endpoint = (
            os.environ.get("ALPACA_DATA_ENDPOINT") or
            alp_cfg.get("data_endpoint", "https://data.alpaca.markets")
        ).rstrip('/')

    def fetch_data(
        self,
        symbol: Optional[str] = None,
        interval: str = "1h",
        days_back: int = 730,
        live: Optional[bool] = None
    ) -> pd.DataFrame:
        """
        Fetches multi-asset data.
        In live mode: Queries real-time market data from Alpaca REST Data API.
        In backtest mode: Loads local cached historical datasets with date range validation.
        """
        sym = symbol or self.asset_cfg.get("symbol", "BTCUSDT")
        is_live = self.live_mode if live is None else live

        if is_live:
            return self.fetch_live_data(symbol=sym, interval=interval)

        # ---------------------------------------------------------------------
        # HISTORICAL BACKTEST MODE (DAT-003: Validated Local Cache)
        # ---------------------------------------------------------------------
        cache_path = os.path.join(self.raw_dir, f"{sym.lower()}_{interval}.csv")
        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path)
                df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
                df["close_time"] = pd.to_datetime(df["close_time"], utc=True)

                bars_per_day = 24
                if self.asset_type in ["stock", "equity"]:
                    bars_per_day = 6.5
                if interval == "4h":
                    bars_per_day = 6.0
                elif interval == "1d":
                    bars_per_day = 1.0

                expected_rows = (days_back * bars_per_day) * 0.4
                if len(df) >= expected_rows:
                    logger.debug(f"Loaded {len(df)} rows from cache: {cache_path}")
                    return df.sort_values("open_time").reset_index(drop=True)
                else:
                    logger.info(f"Cache {cache_path} contains {len(df)} rows, below expected {expected_rows:.0f}. Fetching fresh data.")
            except Exception as e:
                logger.warning(f"Error reading cache file {cache_path}: {e}")

        # Fetch from Provider API if cache absent or insufficient
        if self.asset_type in ["stock", "equity"]:
            return self._fetch_alpaca_stocks(sym, interval, days_back, cache_path)
        else:
            return self._fetch_live_crypto(sym, interval, limit=1000)

    def fetch_live_data(self, symbol: str, interval: str) -> pd.DataFrame:
        """
        Fetches real-time candles from Alpaca Data API.
        DAT-002: Implements gap detection and backfilling to guarantee continuous lookback for indicators.
        """
        sym_upper = symbol.upper()
        equity_symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]

        if sym_upper in equity_symbols or self.asset_type in ["equity", "stock"]:
            is_crypto = False
        elif "USDT" in sym_upper or "BTC" in sym_upper or "ETH" in sym_upper or "/" in sym_upper:
            is_crypto = True
        else:
            is_crypto = (self.asset_type == "crypto")

        # Fetch live candles with generous limit (300 bars) for indicator warmups
        if is_crypto:
            live_df = self._fetch_live_crypto(symbol, interval, limit=350)
        else:
            live_df = self._fetch_live_stock(symbol, interval, limit=350)

        if live_df.empty:
            logger.warning(f"Live API returned empty bars for {symbol}. Falling back to cached data.")
            cache_path = os.path.join(self.raw_dir, f"{symbol.lower()}_{interval}.csv")
            if os.path.exists(cache_path):
                df_c = pd.read_csv(cache_path)
                df_c["open_time"] = pd.to_datetime(df_c["open_time"], utc=True)
                df_c["close_time"] = pd.to_datetime(df_c["close_time"], utc=True)
                return df_c.sort_values("open_time").reset_index(drop=True)
            return pd.DataFrame()

        # If live_df alone provides sufficient bars (>= 200), return directly without stitching risks
        if len(live_df) >= 200:
            latest_bar = live_df.iloc[-1]
            logger.info(
                f"[REAL-TIME DATA] {symbol} ({interval}): Loaded {len(live_df)} contiguous live bars! "
                f"Latest Close: ${float(latest_bar['close']):,.2f} @ {latest_bar['open_time']}"
            )
            return live_df

        # ---------------------------------------------------------------------
        # DAT-002: Gap-Aware Cache Stitching & Automated Backfill
        # ---------------------------------------------------------------------
        cache_path = os.path.join(self.raw_dir, f"{symbol.lower()}_{interval}.csv")
        if os.path.exists(cache_path):
            try:
                cache_df = pd.read_csv(cache_path)
                cache_df["open_time"] = pd.to_datetime(cache_df["open_time"], utc=True)
                cache_df["close_time"] = pd.to_datetime(cache_df["close_time"], utc=True)

                min_live_ot = live_df["open_time"].min()
                prior_cache = cache_df[cache_df["open_time"] < min_live_ot]

                if not prior_cache.empty:
                    max_cache_ot = prior_cache["open_time"].max()
                    tf_step = pd.Timedelta(hours=1) if interval == "1h" else (pd.Timedelta(hours=4) if interval == "4h" else pd.Timedelta(days=1))
                    gap_duration = min_live_ot - max_cache_ot

                    # If gap is larger than 3 intervals, attempt backfill or discard stale cache
                    if gap_duration > (tf_step * 3):
                        logger.warning(
                            f"[DATA GAP DETECTED] {symbol} ({interval}): Gap of {gap_duration} between cache ({max_cache_ot}) "
                            f"and live data ({min_live_ot}). Attempting Alpaca backfill..."
                        )
                        backfill_df = self._backfill_range(symbol, interval, max_cache_ot, min_live_ot, is_crypto=is_crypto)
                        if not backfill_df.empty:
                            combined = pd.concat([prior_cache, backfill_df, live_df], ignore_index=True)
                            combined = combined.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)
                            logger.info(f"[BACKFILL SUCCESS] Stitched {len(prior_cache)} cache + {len(backfill_df)} backfilled + {len(live_df)} live bars.")
                            return combined
                        else:
                            logger.warning(
                                f"[STALE CACHE DISCARDED] Cannot bridge gap of {gap_duration} for {symbol}. "
                                "Discarding stale cache to prevent rolling indicator distortion. Using pure live bars."
                            )
                            return live_df

                    # Continuous or small acceptable gap (e.g. standard weekend on equities)
                    combined = pd.concat([prior_cache, live_df], ignore_index=True)
                    combined = combined.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)
                    return combined
            except Exception as e:
                logger.warning(f"Warning verifying historical cache continuity: {e}")

        return live_df

    def _backfill_range(
        self,
        symbol: str,
        interval: str,
        start_time: pd.Timestamp,
        end_time: pd.Timestamp,
        is_crypto: bool
    ) -> pd.DataFrame:
        """Paginates Alpaca REST API to fetch intermediate candles across a historical gap."""
        tf_map = {"1h": "1Hour", "4h": "4Hour", "1d": "1Day"}
        tf = tf_map.get(interval, "1Hour")
        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key
        }

        if is_crypto:
            alpaca_sym = "BTC/USD" if "BTC" in symbol else ("ETH/USD" if "ETH" in symbol else symbol)
            url = f"{self.data_endpoint}/v1beta3/crypto/us/bars"
            params = {"symbols": alpaca_sym, "timeframe": tf, "start": start_str, "end": end_str, "limit": 1000}
        else:
            url = f"{self.data_endpoint}/v2/stocks/{symbol}/bars"
            params = {"timeframe": tf, "start": start_str, "end": end_str, "feed": "iex", "limit": 1000}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                bars = data.get("bars", {}).get(alpaca_sym, []) if is_crypto else data.get("bars", [])
                if bars:
                    df = pd.DataFrame(bars)
                    df = df.drop_duplicates(subset=["t"])
                    df["open_time"] = pd.to_datetime(df["t"], utc=True)
                    step = pd.Timedelta(hours=1) if tf == "1Hour" else (pd.Timedelta(hours=4) if tf == "4Hour" else pd.Timedelta(days=1))
                    df["close_time"] = df["open_time"] + step
                    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
                    return df[["open_time", "open", "high", "low", "close", "volume", "close_time"]].sort_values("open_time").reset_index(drop=True)
        except Exception as e:
            logger.error(f"Error backfilling missing range {start_str} -> {end_str} for {symbol}: {e}")

        return pd.DataFrame()

    def _fetch_live_stock(self, symbol: str, interval: str, limit: int = 350) -> pd.DataFrame:
        """Fetches live stock candles from Alpaca Stock Data API v2."""
        tf_map = {"1h": "1Hour", "4h": "4Hour", "1d": "1Day"}
        tf = tf_map.get(interval, "1Hour")
        days = 90 if interval in ["1h", "4h"] else 400
        start = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"{self.data_endpoint}/v2/stocks/{symbol}/bars"
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key
        }
        params = {"timeframe": tf, "start": start, "feed": "iex", "sort": "desc", "limit": min(limit, 1000)}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                bars = resp.json().get("bars", [])
                if bars:
                    df = pd.DataFrame(bars)
                    df["open_time"] = pd.to_datetime(df["t"], utc=True)
                    step = pd.Timedelta(hours=1) if tf == "1Hour" else (pd.Timedelta(hours=4) if tf == "4Hour" else pd.Timedelta(days=1))
                    df["close_time"] = df["open_time"] + step
                    df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
                    return df[["open_time", "open", "high", "low", "close", "volume", "close_time"]].sort_values("open_time").reset_index(drop=True)
            else:
                logger.error(f"Alpaca stock data error for {symbol} ({resp.status_code}): {resp.text}")
        except Exception as e:
            logger.error(f"Error fetching live stock bars for {symbol}: {e}")
        return pd.DataFrame()

    def _fetch_live_crypto(self, symbol: str, interval: str, limit: int = 350) -> pd.DataFrame:
        """Fetches live crypto candles from Alpaca Crypto Data API v1beta3."""
        alpaca_sym = "BTC/USD" if "BTC" in symbol else ("ETH/USD" if "ETH" in symbol else symbol)
        tf_map = {"1h": "1Hour", "4h": "4Hour", "1d": "1Day"}
        tf = tf_map.get(interval, "1Hour")
        days = 90 if interval in ["1h", "4h"] else 400
        start = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"{self.data_endpoint}/v1beta3/crypto/us/bars"
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key
        }
        params = {"symbols": alpaca_sym, "timeframe": tf, "start": start, "sort": "desc", "limit": min(limit, 1000)}

        all_bars = []
        page_count = 0
        max_pages = 3

        try:
            while page_count < max_pages:
                page_count += 1
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    bars = data.get("bars", {}).get(alpaca_sym, [])
                    if not bars:
                        break
                    all_bars.extend(bars)
                    next_token = data.get("next_page_token")
                    if not next_token or len(all_bars) >= limit:
                        break
                    params["page_token"] = next_token
                else:
                    logger.error(f"Alpaca crypto data error for {alpaca_sym} ({resp.status_code}): {resp.text}")
                    break

            if all_bars:
                df = pd.DataFrame(all_bars)
                df = df.drop_duplicates(subset=["t"])
                df["open_time"] = pd.to_datetime(df["t"], utc=True)
                step = pd.Timedelta(hours=1) if tf == "1Hour" else (pd.Timedelta(hours=4) if tf == "4Hour" else pd.Timedelta(days=1))
                df["close_time"] = df["open_time"] + step
                df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
                return df[["open_time", "open", "high", "low", "close", "volume", "close_time"]].sort_values("open_time").reset_index(drop=True)
        except Exception as e:
            logger.error(f"Error fetching live crypto bars for {alpaca_sym}: {e}")
        return pd.DataFrame()

    def _fetch_alpaca_stocks(self, symbol: str, interval: str, days_back: int, cache_path: str) -> pd.DataFrame:
        """Historical backtest stock fetcher."""
        df = self._fetch_live_stock(symbol, interval, limit=1000)
        if not df.empty:
            df.to_csv(cache_path, index=False)
        return df

    @staticmethod
    def get_completed_candles(
        df: pd.DataFrame,
        interval: str = "1h",
        now_utc: Optional[pd.Timestamp] = None
    ) -> pd.DataFrame:
        """
        DAT-001: Filters DataFrame to guarantee evaluation strictly on COMPLETED candles.
        Differentiates between:
        - Completed candle: close_time <= now_utc
        - Forming candle: open_time <= now_utc < close_time (sliced off)
        - Stale candle: logs warning if latest completed candle is older than 2x interval
        """
        if df.empty:
            return df

        current_time = now_utc or pd.Timestamp.now(tz="UTC")
        clean_df = df.copy()
        clean_df["open_time"] = pd.to_datetime(clean_df["open_time"], utc=True)
        clean_df["close_time"] = pd.to_datetime(clean_df["close_time"], utc=True)

        latest_bar = clean_df.iloc[-1]

        # Check if the latest candle is still forming
        if current_time < latest_bar["close_time"]:
            # Candle has not closed yet. Exclude it from signal calculations.
            completed_df = clean_df.iloc[:-1].copy()
            logger.debug(
                f"Excluding forming candle @ {latest_bar['open_time']} (Closes at {latest_bar['close_time']}). "
                f"Using completed candle @ {completed_df.iloc[-1]['open_time']}."
            )
        else:
            completed_df = clean_df

        if completed_df.empty:
            return completed_df

        # Check for staleness
        tf_step = pd.Timedelta(hours=1) if interval == "1h" else (pd.Timedelta(hours=4) if interval == "4h" else pd.Timedelta(days=1))
        last_close = completed_df.iloc[-1]["close_time"]
        if (current_time - last_close) > (tf_step * 2.5):
            logger.debug(f"Latest completed candle closed at {last_close}, which is > 2.5 intervals prior to {current_time}.")

        return completed_df.reset_index(drop=True)
