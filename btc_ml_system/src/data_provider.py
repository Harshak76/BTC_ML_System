"""
Data Provider Module for V4.0 btc_ml_system.
Unified multi-asset data provider supporting Binance REST API (Crypto) and Alpaca REST API (Stocks & Crypto).
"""

import os
import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
import requests

logger = logging.getLogger("btc_ml_system.data_provider")


class DataProvider:
    """Multi-exchange historical OHLCV data provider for Crypto & Stocks."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.raw_dir = config.get("data", {}).get("raw_dir", "data/raw")
        self.asset_cfg = config.get("asset", {})
        self.asset_type = self.asset_cfg.get("asset_type", "crypto")
        self.provider = self.asset_cfg.get("data_provider", "binance")
        os.makedirs(self.raw_dir, exist_ok=True)

    def fetch_data(self, symbol: Optional[str] = None, interval: str = "1h", days_back: int = 730) -> pd.DataFrame:
        """
        Fetches or loads cached multi-asset data based on configuration provider.
        """
        sym = symbol or self.asset_cfg.get("symbol", "BTCUSDT")
        cache_path = os.path.join(self.raw_dir, f"{sym.lower()}_{interval}.csv")

        # Load local cache if sufficient
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
                expected_rows = (days_back * bars_per_day) * 0.5  # Estimate minimum rows
                if len(df) >= expected_rows:
                    logger.info(f"Loaded {len(df)} rows from cache: {cache_path}")
                    return df.sort_values("open_time").reset_index(drop=True)
            except Exception as e:
                logger.warning(f"Error reading cache file {cache_path}: {e}")

        # Fetch from Provider API
        if self.provider == "binance" or self.asset_type == "crypto":
            return self._fetch_binance(sym, interval, days_back, cache_path)
        else:
            return self._fetch_alpaca_stocks(sym, interval, days_back, cache_path)

    def _fetch_binance(self, symbol: str, interval: str, days_back: int, cache_path: str) -> pd.DataFrame:
        """Fetches crypto data from Binance public REST API."""
        logger.info(f"Fetching Binance REST klines for {symbol} ({interval})...")
        end_time = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
        start_time = int((pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days_back)).timestamp() * 1000)

        url = "https://api.binance.com/api/v3/klines"
        all_klines = []
        curr_start = start_time

        while curr_start < end_time:
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": curr_start,
                "limit": 1000
            }
            try:
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code != 200:
                    break
                data = resp.json()
                if not data:
                    break
                all_klines.extend(data)
                curr_start = data[-1][6] + 1
            except Exception as e:
                logger.error(f"Binance API fetch error: {e}")
                break

        if not all_klines:
            logger.warning("No data retrieved from Binance REST API.")
            return pd.DataFrame()

        df = pd.DataFrame(all_klines, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
        ])

        cols = ["open", "high", "low", "close", "volume"]
        for col in cols:
            df[col] = df[col].astype(float)

        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)

        res_df = df[["open_time", "open", "high", "low", "close", "volume", "close_time"]].sort_values("open_time").reset_index(drop=True)
        res_df.to_csv(cache_path, index=False)
        logger.info(f"Saved {len(res_df)} rows to {cache_path}")
        return res_df

    def _fetch_alpaca_stocks(self, symbol: str, interval: str, days_back: int, cache_path: str) -> pd.DataFrame:
        """Fetches stock data from Alpaca REST Data API or generates sample market data if API keys missing."""
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if api_key and secret_key:
            logger.info(f"Fetching Alpaca Stock Data for {symbol} ({interval})...")
            headers = {
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": secret_key
            }
            end_date = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d")
            start_date = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days_back)).strftime("%Y-%m-%d")
            tf_map = {"1h": "1Hour", "4h": "4Hour", "1d": "1Day"}
            tf = tf_map.get(interval, "1Hour")

            url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
            params = {"timeframe": tf, "start": start_date, "end": end_date, "limit": 10000, "feed": "sip"}
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                if resp.status_code == 200:
                    bars = resp.json().get("bars", [])
                    if bars:
                        bdf = pd.DataFrame(bars)
                        bdf["open_time"] = pd.to_datetime(bdf["t"], utc=True)
                        bdf["close_time"] = bdf["open_time"] + pd.Timedelta(hours=1)
                        bdf = bdf.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
                        res_df = bdf[["open_time", "open", "high", "low", "close", "volume", "close_time"]].sort_values("open_time").reset_index(drop=True)
                        res_df.to_csv(cache_path, index=False)
                        return res_df
            except Exception as e:
                logger.error(f"Alpaca Data API error: {e}")

        logger.warning(f"Alpaca API credentials missing or request failed. Generating synthetic data for testing {symbol}...")
        dates = pd.date_range(end=pd.Timestamp.now(tz="UTC"), periods=days_back * 7, freq="1h")
        np.random.seed(42)
        returns = np.random.normal(0.0002, 0.015, len(dates))
        price = 150.0 * np.exp(np.cumsum(returns))
        df = pd.DataFrame({
            "open_time": dates,
            "open": price * (1 - np.random.uniform(0, 0.002, len(dates))),
            "high": price * (1 + np.random.uniform(0.001, 0.008, len(dates))),
            "low": price * (1 - np.random.uniform(0.001, 0.008, len(dates))),
            "close": price,
            "volume": np.random.uniform(10000, 50000, len(dates)),
            "close_time": dates + pd.Timedelta(minutes=59)
        })
        df.to_csv(cache_path, index=False)
        return df
