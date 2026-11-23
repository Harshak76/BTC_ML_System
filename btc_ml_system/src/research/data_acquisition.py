"""
Authentic Equity Data Acquisition Module for Phase 3B.2.
Retrieves authentic 1-hour OHLCV market data for AAPL, MSFT, NVDA, TSLA, and AMZN
from Alpaca Market Data API v2, with split adjustment, pagination, and data manifest generation.
"""

import os
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
import requests

from dotenv import load_dotenv

# Load credentials from .env
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def compute_sha256(filepath: Path) -> str:
    """Computes SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def fetch_symbol_bars(
    symbol: str,
    api_key: str,
    secret_key: str,
    start: str = "2024-01-02T13:00:00Z",
    end: str = "2026-09-18T21:00:00Z",
    timeframe: str = "1Hour",
    adjustment: str = "split"
) -> List[Dict[str, Any]]:
    """Fetches all bars for a symbol with pagination from Alpaca Market Data v2."""
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/bars"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": secret_key
    }
    params = {
        "timeframe": timeframe,
        "start": start,
        "end": end,
        "adjustment": adjustment,
        "limit": 1000
    }

    all_bars = []
    page_token = None
    while True:
        if page_token:
            params["page_token"] = page_token
        elif "page_token" in params:
            del params["page_token"]

        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"Alpaca API error {resp.status_code} for {symbol}: {resp.text}")

        data = resp.json()
        bars = data.get("bars", [])
        if not bars:
            break
        all_bars.extend(bars)
        page_token = data.get("next_page_token")
        if not page_token:
            break

    return all_bars


def acquire_all_equities(
    symbols: List[str] = None,
    output_dir: Path = None
) -> Dict[str, Any]:
    """Acquires authentic historical data for all requested equity symbols."""
    if symbols is None:
        symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]
    if output_dir is None:
        output_dir = Path(__file__).resolve().parents[3] / "data" / "authentic_raw"

    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("ALPACA_API_KEY", "")
    secret_key = os.environ.get("ALPACA_SECRET_KEY", "")
    if not api_key or not secret_key:
        raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be configured in environment.")

    manifest = {
        "provider": "Alpaca Market Data API v2",
        "retrieval_timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
        "timeframe": "1h",
        "adjustment": "split",
        "timezone": "UTC",
        "symbols": {}
    }

    for sym in symbols:
        print(f"Fetching authentic data for {sym}...")
        t0 = time.time()
        raw_bars = fetch_symbol_bars(sym, api_key, secret_key)
        elapsed = time.time() - t0
        print(f"Retrieved {len(raw_bars)} bars for {sym} in {elapsed:.2f}s")

        # Convert to standardized DataFrame
        records = []
        for b in raw_bars:
            t_open = pd.to_datetime(b["t"]).tz_convert("UTC")
            t_close = t_open + pd.Timedelta(hours=1)
            records.append({
                "open_time": str(t_open),
                "open": float(b["o"]),
                "high": float(b["h"]),
                "low": float(b["l"]),
                "close": float(b["c"]),
                "volume": float(b["v"]),
                "close_time": str(t_close)
            })

        df = pd.DataFrame(records)
        df["open_time_dt"] = pd.to_datetime(df["open_time"])
        df = df.sort_values("open_time_dt").drop_duplicates(subset=["open_time"]).reset_index(drop=True)
        df = df.drop(columns=["open_time_dt"])

        out_file = output_dir / f"{sym.lower()}_1h.csv"
        df.to_csv(out_file, index=False)
        file_hash = compute_sha256(out_file)

        manifest["symbols"][sym] = {
            "symbol": sym,
            "filename": out_file.name,
            "row_count": len(df),
            "start_time": df["open_time"].iloc[0] if len(df) > 0 else None,
            "end_time": df["open_time"].iloc[-1] if len(df) > 0 else None,
            "initial_close": df["close"].iloc[0] if len(df) > 0 else None,
            "terminal_close": df["close"].iloc[-1] if len(df) > 0 else None,
            "sha256": file_hash,
            "duplicates_removed": len(raw_bars) - len(df),
            "corporate_action_treatment": "split_adjusted",
            "validation_status": "ACQUIRED_AUTHENTIC"
        }

    # Save manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Data acquisition complete. Manifest saved to {manifest_path}")
    return manifest


if __name__ == "__main__":
    acquire_all_equities()
