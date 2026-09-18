"""
Paper Trader Module for V2 btc_ml_system.
Simulates real-time paper trading loop fetching live 1h klines from Binance and executing mock orders.
"""

import time
import logging
from typing import Dict, Any
import pandas as pd

from btc_ml_system.src.data_ingestion import DataIngestion
from btc_ml_system.src.inference import LiveInferencePipeline

logger = logging.getLogger("btc_ml_system.paper_trader")


class PaperTrader:
    """Paper trading engine running live simulation against Binance public REST endpoint."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ingestion = DataIngestion(config)
        self.pipeline = LiveInferencePipeline(config)
        self.symbol = config.get("asset", {}).get("primary_symbol", "BTCUSDT")
        self.htf_symbol = config.get("asset", {}).get("secondary_symbol", "ETHUSDT")

    def run_tick(self) -> Dict[str, Any]:
        """Runs a single live paper-trading tick iteration."""
        logger.info(f"Running live paper trader tick for {self.symbol}...")
        df_1h = self.ingestion.fetch_binance_klines(symbol=self.symbol, interval="1h", start_str="30 days ago")
        df_4h = self.ingestion.fetch_binance_klines(symbol=self.symbol, interval="4h", start_str="60 days ago")

        if df_1h.empty:
            logger.error("Failed to fetch 1h data for paper trader tick.")
            return {"status": "error", "message": "No data returned"}

        result = self.pipeline.predict_latest_bar(df_1h, df_4h)
        logger.info(f"Paper Trader Result: {result}")
        return result
