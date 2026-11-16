"""
Data Provider Module for btc_ml_system.
Unified multi-asset data provider supporting:
- Real-Time Live Streaming / Polling Data from Alpaca Data API v2 / v1beta3 (Stocks & Crypto)
- Historical Cached Data for Fast Backtesting Simulation
"""

import os
import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
import requests

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

        # Alpaca Credentials Resolution
        alp_cfg = config.get("alpaca", {})
        self.api_key = os.environ.get("ALPACA_API_KEY") or alp_cfg.get("api_key", "PKOJMWUCJSH433JAYP2L74MLNN")
        self.secret_key = os.environ.get("ALPACA_SECRET_KEY") or alp_cfg.get("secret_key", "ACKUpw6mrJHSTFWXAo7szZfqShR6TTfnvYQJ21K2GW8k")

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
        In backtest mode: Loads local cached historical datasets.
        """
        sym = symbol or self.asset_cfg.get("symbol", "BTCUSDT")
        is_live = self.live_mode if live is None else live

        if is_live:
            return self.fetch_live_data(symbol=sym, interval=interval)

        # ---------------------------------------------------------------------
        # HISTORICAL BACKTEST MODE (Fast Local Cache)
        # ---------------------------------------------------------------------
        cache_path = os.path.join(self.raw_dir, f"{sym.lower()}_{interval}.csv")
        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path)
                df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
                df["close_time"] = pd.to_datetime(df["close_time"], utc=True)
                bars_per_day = 24
                if self.asset_type == "stock":
                    bars_per_day = 7.0 * (252.0 / 365.0)
                if interval == "4h":
                    bars_per_day = 6.0
                elif interval == "1d":
                    bars_per_day = 1.0 if self.asset_type != "stock" else (252.0 / 365.0)
                expected_rows = (days_back * bars_per_day) * 0.5
                if len(df) >= expected_rows:
                    logger.debug(f"Loaded {len(df)} rows from cache: {cache_path}")
                    return df.sort_values("open_time").reset_index(drop=True)
            except Exception as e:
                logger.warning(f"Error reading cache file {cache_path}: {e}")

        # Fetch from Provider API if cache absent
        if self.asset_type == "stock":
            return self._fetch_alpaca_stocks(sym, interval, days_back, cache_path)
        else:
            return self._fetch_live_crypto(sym, interval, limit=1000)

    def fetch_live_data(self, symbol: str, interval: str) -> pd.DataFrame:
        """
        Fetches real-time candles from Alpaca Data API.
        Ensures technical indicators have historical lookback by overlaying live bars
        onto the historical baseline so the most recent bar is always the live market candle.
        """
        sym_upper = symbol.upper()
        equity_symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]
        
        if sym_upper in equity_symbols or self.asset_type in ["equity", "stock"]:
            is_crypto = False
        elif "USDT" in sym_upper or "BTC" in sym_upper or "ETH" in sym_upper or "/" in sym_upper:
            is_crypto = True
        else:
            is_crypto = (self.asset_type == "crypto")

        if is_crypto:
            live_df = self._fetch_live_crypto(symbol, interval, limit=200)
        else:
            live_df = self._fetch_live_stock(symbol, interval, limit=200)

        if live_df.empty:
            logger.warning(f"Live API returned empty bars for {symbol}. Falling back to cached data.")
            cache_path = os.path.join(self.raw_dir, f"{symbol.lower()}_{interval}.csv")
            if os.path.exists(cache_path):
                return pd.read_csv(cache_path)
            return pd.DataFrame()

        # Merge with historical cache if needed so indicators (e.g. EMA200, ATR14) have sufficient warmup
        cache_path = os.path.join(self.raw_dir, f"{symbol.lower()}_{interval}.csv")
        if os.path.exists(cache_path) and len(live_df) < 150:
            try:
                cache_df = pd.read_csv(cache_path)
                cache_df["open_time"] = pd.to_datetime(cache_df["open_time"], utc=True)
                cache_df["close_time"] = pd.to_datetime(cache_df["close_time"], utc=True)

                min_live_ot = live_df["open_time"].min()
                prior_cache = cache_df[cache_df["open_time"] < min_live_ot]
                combined = pd.concat([prior_cache, live_df], ignore_index=True)
                combined = combined.sort_values("open_time").reset_index(drop=True)

                latest_bar = combined.iloc[-1]
                logger.info(
                    f"[REAL-TIME DATA] {symbol} ({interval}): Live candle loaded! "
                    f"Bar Time: {latest_bar['open_time']} | Latest Close: ${float(latest_bar['close']):,.2f} "
                    f"(Merged {len(prior_cache)} warmup bars + {len(live_df)} live bars)"
                )
                return combined
            except Exception as e:
                logger.warning(f"Warning merging cache with live data: {e}")

        latest_bar = live_df.iloc[-1]
        logger.info(
            f"[REAL-TIME DATA] {symbol} ({interval}): Live candle loaded! "
            f"Bar Time: {latest_bar['open_time']} | Latest Close: ${float(latest_bar['close']):,.2f} "
            f"({len(live_df)} live bars)"
        )
        return live_df

    def _fetch_live_stock(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        """Fetches live stock candles from Alpaca Stock Data API v2."""
        tf_map = {"1h": "1Hour", "4h": "4Hour", "1d": "1Day"}
        tf = tf_map.get(interval, "1Hour")
        days = 45 if interval in ["1h", "4h"] else 300
        start = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key
        }
        params = {"timeframe": tf, "start": start, "feed": "iex", "sort": "desc", "limit": limit}

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

    def _fetch_live_crypto(self, symbol: str, interval: str, limit: int = 200) -> pd.DataFrame:
        """Fetches live crypto candles from Alpaca Crypto Data API v1beta3."""
        alpaca_sym = "BTC/USD" if "BTC" in symbol else ("ETH/USD" if "ETH" in symbol else symbol)
        tf_map = {"1h": "1Hour", "4h": "4Hour", "1d": "1Day"}
        tf = tf_map.get(interval, "1Hour")
        days = 60 if interval in ["1h", "4h"] else 365
        start = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        url = "https://data.alpaca.markets/v1beta3/crypto/us/bars"
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key
        }
        params = {"symbols": alpaca_sym, "timeframe": tf, "start": start, "sort": "desc", "limit": min(limit, 1000)}

        all_bars = []
        page_count = 0
        max_pages = 5

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
