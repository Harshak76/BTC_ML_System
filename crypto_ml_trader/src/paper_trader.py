"""
Paper Trading Module.
Simulates continuous execution loop with state persistence and complete signal logging.
"""

import os
import time
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from crypto_ml_trader.src.data_ingestion import BinanceDataIngestor
from crypto_ml_trader.src.data_quality import DataQualityChecker
from crypto_ml_trader.src.inference import InferencePipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class PaperTrader:
    """Runs continuous paper trading simulation with persistent state logging."""

    def __init__(
        self,
        config: Dict[str, Any],
        state_path: str = "reports/paper_trading_state.json"
    ):
        self.config = config
        self.state_path = state_path
        self.ingestor = BinanceDataIngestor()
        self.pipeline = InferencePipeline(config)
        self.symbol = config.get("asset", {}).get("primary_symbol", "BTCUSDT")

        self.state = self.load_state()

    def load_state(self) -> Dict[str, Any]:
        """Loads paper trading state from disk or initializes default state."""
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r") as f:
                    state = json.load(f)
                logger.info(f"Loaded existing paper trading state from {self.state_path}")
                return state
            except Exception as e:
                logger.warning(f"Error loading state file: {e}. Reinitializing default state.")

        initial_equity = float(self.config.get("risk", {}).get("initial_capital", 10000.0))
        return {
            "initial_equity": initial_equity,
            "current_equity": initial_equity,
            "high_water_mark": initial_equity,
            "open_position": None,
            "trade_history": [],
            "signal_logs": [],
            "last_processed_timestamp": None
        }

    def save_state(self):
        """Persists current state to JSON."""
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(self.state, f, indent=2)
        logger.info(f"Saved paper trading state to {self.state_path}")

    def run_cycle(self) -> Dict[str, Any]:
        """Executes a single paper trading evaluation cycle."""
        logger.info("Executing paper trading cycle...")

        # 1. Fetch latest 1h and 4h candles
        end_time = datetime.now(timezone.utc)
        start_time = end_time - pd.Timedelta(days=30)

        df_1h_raw = self.ingestor.fetch_historical_klines(self.symbol, "1h", start_time, end_time)
        df_4h_raw = self.ingestor.fetch_historical_klines(self.symbol, "4h", start_time, end_time)

        if df_1h_raw.empty or df_4h_raw.empty:
            logger.warning("Failed to retrieve latest candle data.")
            return {"status": "ERROR", "reason": "No data received."}

        df_1h, _ = DataQualityChecker.inspect_and_clean(df_1h_raw, timeframe="1h")
        df_4h, _ = DataQualityChecker.inspect_and_clean(df_4h_raw, timeframe="4h")

        has_position = self.state["open_position"] is not None

        # 2. Run inference pipeline
        decision = self.pipeline.process_new_candle(df_1h, df_4h, has_open_position=has_position)

        # 3. Log decision signal
        self.state["signal_logs"].append(decision)
        self.state["last_processed_timestamp"] = decision.get("timestamp_utc")

        # Save updated state
        self.save_state()

        return decision


if __name__ == "__main__":
    import yaml
    config_file = "crypto_ml_trader/configs/btcusdt_1h.yaml"
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            cfg = yaml.safe_load(f)
    else:
        cfg = {}

    trader = PaperTrader(cfg)
    trader.run_cycle()
