"""
Data Ingestion Module for Binance Public REST API and Apify Alternative Data Platform.
Fetches historical OHLCV klines, orderbook snapshots, and trade datasets.
Saves raw dataset storage and download manifests.
"""

import os
import time
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
BINANCE_DEPTH_URL = "https://api.binance.com/api/v3/depth"
BINANCE_TRADES_URL = "https://api.binance.com/api/v3/trades"

KLINE_COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "number_of_trades",
    "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"
]


class BinanceDataIngestor:
    """Handles fetching historical kline data from Binance public REST API."""

    def __init__(self, base_url: str = BINANCE_KLINES_URL):
        self.base_url = base_url
        self.session = requests.Session()

    def fetch_klines_chunk(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: Optional[int] = None,
        limit: int = 1000
    ) -> List[List[Any]]:
        """Fetch a single chunk of up to limit klines from Binance."""
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "startTime": start_ms,
            "limit": limit
        }
        if end_ms is not None:
            params["endTime"] = end_ms

        for attempt in range(5):
            try:
                response = self.session.get(self.base_url, params=params, timeout=15)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    logger.warning("Rate limit hit (429). Sleeping for 10 seconds...")
                    time.sleep(10)
                else:
                    logger.warning(f"Binance API returned status {response.status_code}: {response.text}")
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.warning(f"Fetch attempt {attempt + 1} failed with error: {e}")
                time.sleep(2 ** attempt)

        raise RuntimeError(f"Failed to fetch klines for {symbol} {interval} after 5 retries.")

    def fetch_historical_klines(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Fetch complete historical klines between start_time and end_time with pagination."""
        if end_time is None:
            end_time = datetime.now(timezone.utc)

        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        logger.info(f"Fetching {symbol} {interval} klines from {start_time} to {end_time}...")
        all_klines = []
        current_start = start_ms

        while current_start < end_ms:
            klines = self.fetch_klines_chunk(symbol, interval, current_start, end_ms, limit=1000)
            if not klines:
                break

            all_klines.extend(klines)
            last_close_time = klines[-1][6]
            current_start = last_close_time + 1

            if len(klines) < 1000:
                break

            time.sleep(0.1) # Be gentle on public API rate limits

        if not all_klines:
            logger.warning(f"No klines retrieved for {symbol} {interval}.")
            return pd.DataFrame(columns=KLINE_COLUMNS)

        df = pd.DataFrame(all_klines, columns=KLINE_COLUMNS)
        numeric_cols = [
            "open", "high", "low", "close", "volume",
            "quote_asset_volume", "number_of_trades",
            "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume"
        ]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
        df = df.drop(columns=["ignore"])
        df = df.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)

        logger.info(f"Successfully fetched {len(df)} candles for {symbol} {interval}.")
        return df

    def save_dataset(
        self,
        df: pd.DataFrame,
        symbol: str,
        interval: str,
        output_dir: str = "data/raw",
        manifest_dir: str = "data/manifests"
    ) -> str:
        """Saves raw dataset to CSV and records download manifest."""
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(manifest_dir, exist_ok=True)

        filename = f"{symbol.lower()}_{interval}.csv"
        filepath = os.path.join(output_dir, filename)
        df.to_csv(filepath, index=False)

        # Compute SHA256 file hash for integrity tracking
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            hasher.update(f.read())
        file_hash = hasher.hexdigest()

        manifest = {
            "symbol": symbol.upper(),
            "interval": interval,
            "download_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "start_time_utc": df["open_time"].min().isoformat() if not df.empty else None,
            "end_time_utc": df["open_time"].max().isoformat() if not df.empty else None,
            "row_count": len(df),
            "file_name": filename,
            "file_path": os.path.abspath(filepath),
            "sha256": file_hash
        }

        manifest_path = os.path.join(manifest_dir, f"{symbol.lower()}_{interval}_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Dataset saved to {filepath} | Manifest written to {manifest_path}")
        return filepath


class ApifyDataIngestor:
    """
    Handles fetching alternative market datasets (order book, trade depth, sentiment)
    using the Apify Platform API and Apify Actors.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("APIFY_API_KEY")
        self.client = None
        try:
            from apify_client import ApifyClient
            self.client = ApifyClient(self.api_key)
            logger.info("Initialized ApifyClient successfully.")
        except ImportError:
            logger.warning("apify-client package not installed. Falling back to direct HTTP REST calls.")

    def run_actor_and_fetch_dataset(
        self,
        actor_id: str,
        run_input: Dict[str, Any],
        timeout_secs: int = 300
    ) -> List[Dict[str, Any]]:
        """Runs an Apify Actor and retrieves items from the output dataset."""
        logger.info(f"Starting Apify Actor run for '{actor_id}'...")

        if self.client is not None:
            run = self.client.actor(actor_id).call(run_input=run_input, timeout_secs=timeout_secs)
            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                logger.warning("No dataset ID returned from Apify run.")
                return []
            items = list(self.client.dataset(dataset_id).iterate_items())
            logger.info(f"Retrieved {len(items)} items from Apify dataset {dataset_id}.")
            return items
        else:
            # HTTP Direct Fallback
            url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={self.api_key}"
            res = requests.post(url, json=run_input, timeout=30)
            if res.status_code not in (200, 201):
                logger.error(f"Apify API returned error {res.status_code}: {res.text}")
                return []
            run_data = res.json().get("data", {})
            dataset_id = run_data.get("defaultDatasetId")
            dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={self.api_key}"
            items_res = requests.get(dataset_url, timeout=30)
            return items_res.json() if items_res.status_code == 200 else []

    def fetch_orderbook_snapshot(self, symbol: str = "BTCUSDT", limit: int = 100) -> pd.DataFrame:
        """Fetches orderbook depth snapshot (bids & asks) via Apify or Binance Depth API."""
        logger.info(f"Fetching orderbook snapshot for {symbol} (limit={limit})...")
        try:
            resp = requests.get(BINANCE_DEPTH_URL, params={"symbol": symbol.upper(), "limit": limit}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                bids = pd.DataFrame(data.get("bids", []), columns=["price", "qty"]).astype(float)
                bids["side"] = "bid"
                asks = pd.DataFrame(data.get("asks", []), columns=["price", "qty"]).astype(float)
                asks["side"] = "ask"
                df = pd.concat([bids, asks], ignore_index=True)
                df["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
                df["symbol"] = symbol.upper()
                return df
        except Exception as e:
            logger.warning(f"Direct depth fetch failed: {e}. Trying Apify actor fallback...")

        # Fallback to Apify Actor
        items = self.run_actor_and_fetch_dataset(
            actor_id="apify/web-scraper",
            run_input={"startUrls": [{"url": f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit={limit}"}]}
        )
        return pd.DataFrame(items)

    def save_alternative_dataset(
        self,
        df: pd.DataFrame,
        dataset_type: str = "orderbook",
        symbol: str = "BTCUSDT",
        output_dir: str = "data/raw",
        manifest_dir: str = "data/manifests"
    ) -> str:
        """Saves alternative dataset (orderbook/trades) to CSV and records download manifest."""
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(manifest_dir, exist_ok=True)

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{symbol.lower()}_{dataset_type}_{timestamp_str}.csv"
        filepath = os.path.join(output_dir, filename)
        df.to_csv(filepath, index=False)

        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            hasher.update(f.read())
        file_hash = hasher.hexdigest()

        manifest = {
            "symbol": symbol.upper(),
            "dataset_type": dataset_type,
            "download_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "row_count": len(df),
            "file_name": filename,
            "file_path": os.path.abspath(filepath),
            "sha256": file_hash
        }

        manifest_path = os.path.join(manifest_dir, f"{symbol.lower()}_{dataset_type}_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Alternative dataset saved to {filepath} | Manifest written to {manifest_path}")
        return filepath


def run_ingestion(
    symbol: str = "BTCUSDT",
    days: int = 365,
    output_dir: str = "data/raw",
    use_apify: bool = False,
    apify_key: Optional[str] = None
):
    """CLI entry point for running data ingestion."""
    ingestor = BinanceDataIngestor()
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    # Ingest 1h base timeframe
    df_1h = ingestor.fetch_historical_klines(symbol, "1h", start_time, end_time)
    ingestor.save_dataset(df_1h, symbol, "1h", output_dir=output_dir)

    # Ingest 4h higher timeframe
    df_4h = ingestor.fetch_historical_klines(symbol, "4h", start_time, end_time)
    ingestor.save_dataset(df_4h, symbol, "4h", output_dir=output_dir)

    if use_apify:
        logger.info("Using Apify Data Ingestor to fetch orderbook snapshot...")
        apify_ingestor = ApifyDataIngestor(api_key=apify_key)
        df_ob = apify_ingestor.fetch_orderbook_snapshot(symbol=symbol)
        if not df_ob.empty:
            apify_ingestor.save_alternative_dataset(df_ob, dataset_type="orderbook", symbol=symbol, output_dir=output_dir)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest historical klines and orderbook data from Binance and Apify.")
    parser.add_argument("--symbol", type=str, default="BTCUSDT", help="Trading symbol (e.g. BTCUSDT)")
    parser.add_argument("--days", type=int, default=365, help="Number of historical days to fetch")
    parser.add_argument("--output_dir", type=str, default="data/raw", help="Output directory for raw CSVs")
    parser.add_argument("--use_apify", action="store_true", help="Fetch orderbook/alternative data via Apify")
    parser.add_argument("--apify_key", type=str, default=None, help="Apify API key")
    args = parser.parse_args()

    run_ingestion(
        symbol=args.symbol,
        days=args.days,
        output_dir=args.output_dir,
        use_apify=args.use_apify,
        apify_key=args.apify_key
    )
