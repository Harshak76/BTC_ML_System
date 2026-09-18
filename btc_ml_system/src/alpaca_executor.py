"""
Alpaca Paper Trading Executor Module for V3 btc_ml_system.
Provides order execution, position tracking, duplicate order protection,
and account equity queries using Alpaca REST API v2.
"""

import os
import logging
from typing import Dict, Any, Optional, List
import requests

logger = logging.getLogger("btc_ml_system.alpaca_executor")


class AlpacaExecutor:
    """Interfaces with Alpaca Paper Trading REST API (https://paper-api.alpaca.markets/v2)."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.alp_cfg = config.get("alpaca", {})
        self.endpoint = self.alp_cfg.get("endpoint", "https://paper-api.alpaca.markets/v2")
        self.api_key_env = self.alp_cfg.get("api_key_env", "ALPACA_API_KEY")
        self.secret_key_env = self.alp_cfg.get("secret_key_env", "ALPACA_SECRET_KEY")

        self.api_key = os.environ.get(self.api_key_env, "")
        self.secret_key = os.environ.get(self.secret_key_env, "")

        self.symbol = config.get("asset", {}).get("alpaca_symbol", "BTC/USD")
        self.executed_signal_ids = set()

        if not self.api_key or not self.secret_key:
            logger.warning(f"Alpaca API keys ({self.api_key_env}/{self.secret_key_env}) not set in environment. Running in Dry-Run / Paper mode.")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }

    def get_account_equity(self) -> float:
        """Fetches current portfolio account equity from Alpaca."""
        if not self.api_key or not self.secret_key:
            return 10000.0  # Default mock equity in dry-run mode

        url = f"{self.endpoint}/account"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            equity = float(data.get("equity", 10000.0))
            logger.info(f"Alpaca Account Equity: ${equity:,.2f}")
            return equity
        except Exception as e:
            logger.error(f"Failed to query Alpaca account equity: {e}. Defaulting to $10,000.")
            return 10000.0

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Queries active crypto positions on Alpaca."""
        if not self.api_key or not self.secret_key:
            return []

        url = f"{self.endpoint}/positions"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to query Alpaca positions: {e}")
            return []

    def place_paper_order(
        self,
        signal_id: str,
        symbol: str = "BTC/USD",
        qty: float = 0.001,
        side: str = "buy",
        order_type: str = "market",
        time_in_force: str = "gtc"
    ) -> Dict[str, Any]:
        """
        Executes paper market order on Alpaca.
        Enforces unique signal_id protection against duplicate order execution.
        """
        if signal_id in self.executed_signal_ids:
            logger.warning(f"DUPLICATE ORDER BLOCKED: Signal ID {signal_id} has already been executed.")
            return {"status": "rejected", "reason": "Duplicate signal_id"}

        self.executed_signal_ids.add(signal_id)

        if not self.api_key or not self.secret_key:
            logger.info(f"[DRY-RUN PAPER ORDER] Placed {side.upper()} order for {qty:.4f} {symbol} (Signal: {signal_id})")
            return {
                "status": "dry_run_success",
                "id": f"mock_order_{signal_id}",
                "symbol": symbol,
                "qty": qty,
                "side": side
            }

        url = f"{self.endpoint}/orders"
        payload = {
            "symbol": symbol,
            "qty": str(round(qty, 4)),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
            "client_order_id": f"btc_v3_{signal_id}"
        }

        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"[ALPACA PAPER ORDER EXECUTED] Order ID: {data.get('id')} | Side: {side} | Qty: {qty}")
            return data
        except Exception as e:
            logger.error(f"Alpaca Order Execution Failed: {e}")
            return {"status": "failed", "reason": str(e)}
