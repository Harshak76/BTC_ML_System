"""
Alpaca Paper Trading Executor Module for V5 btc_ml_system.
Provides multi-asset (Equities + Crypto) order execution, position tracking,
duplicate order protection, account equity queries, hard risk limits,
and emergency kill-switch flattening via Alpaca REST API v2.
"""

import os
import logging
import requests
from typing import Dict, Any, Optional, List

logger = logging.getLogger("btc_ml_system.alpaca_executor")


class AlpacaExecutor:
    """Interfaces with Alpaca Paper Trading REST API (https://paper-api.alpaca.markets/v2)."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.alp_cfg = config.get("alpaca", {})
        self.endpoint = self.alp_cfg.get("endpoint", "https://paper-api.alpaca.markets/v2").rstrip('/')
        
        # API Keys Resolution (Env Vars primary, Config secondary)
        self.api_key_env = self.alp_cfg.get("api_key_env", "ALPACA_API_KEY")
        self.secret_key_env = self.alp_cfg.get("secret_key_env", "ALPACA_SECRET_KEY")
        
        self.api_key = os.environ.get(self.api_key_env, self.alp_cfg.get("api_key", ""))
        self.secret_key = os.environ.get(self.secret_key_env, self.alp_cfg.get("secret_key", ""))

        self.dry_run = bool(self.alp_cfg.get("dry_run", False))
        self.symbol_map = config.get("alpaca_symbol_map", {
            "AAPL": "AAPL",
            "MSFT": "MSFT",
            "NVDA": "NVDA",
            "TSLA": "TSLA",
            "AMZN": "AMZN",
            "BTCUSDT": "BTC/USD",
            "ETHUSDT": "ETH/USD"
        })
        
        # Hard Safety Position Limits
        self.port_risk_cfg = config.get("portfolio", {}).get("risk_limits", {})
        self.max_position_value_usd = float(self.port_risk_cfg.get("max_position_value_usd", 2500.0))
        self.max_position_equity_pct = float(self.port_risk_cfg.get("max_position_equity_pct", 0.30))

        self.executed_signal_ids = set()

        if not self.api_key or not self.secret_key:
            logger.warning(
                f"Alpaca API keys ({self.api_key_env}/{self.secret_key_env}) not fully set in environment. "
                f"Defaulting to DRY-RUN Mode."
            )
            self.dry_run = True
        else:
            logger.info(f"AlpacaExecutor connected to Paper Trading Endpoint: {self.endpoint} (Dry-Run: {self.dry_run})")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }

    def get_account_details(self) -> Dict[str, Any]:
        """Fetches full account state from Alpaca REST endpoint."""
        if self.dry_run or not self.api_key or not self.secret_key:
            return {
                "equity": 10000.0,
                "cash": 10000.0,
                "buying_power": 40000.0,
                "portfolio_value": 10000.0,
                "status": "DRY_RUN_MOCK"
            }

        url = f"{self.endpoint}/account"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return {
                "equity": float(data.get("equity", 10000.0)),
                "cash": float(data.get("cash", 10000.0)),
                "buying_power": float(data.get("buying_power", 40000.0)),
                "portfolio_value": float(data.get("portfolio_value", 10000.0)),
                "status": data.get("status", "ACTIVE")
            }
        except Exception as e:
            logger.error(f"Failed to query Alpaca account: {e}. Defaulting to mock equity $10,000.")
            return {
                "equity": 10000.0,
                "cash": 10000.0,
                "buying_power": 40000.0,
                "portfolio_value": 10000.0,
                "status": "ERROR_FALLBACK"
            }

    def get_account_equity(self) -> float:
        """Helper to get current portfolio account equity."""
        return self.get_account_details()["equity"]

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Queries all active open positions on Alpaca."""
        if self.dry_run or not self.api_key or not self.secret_key:
            return []

        url = f"{self.endpoint}/positions"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to query Alpaca open positions: {e}")
            return []

    def get_position_for_symbol(self, internal_symbol: str) -> Optional[Dict[str, Any]]:
        """Returns open position for a specific asset symbol if it exists."""
        alpaca_sym = self.symbol_map.get(internal_symbol, internal_symbol)
        positions = self.get_open_positions()
        for pos in positions:
            if pos.get("symbol") == alpaca_sym or pos.get("symbol") == internal_symbol:
                return pos
        return None

    def flatten_all_positions(self) -> Dict[str, Any]:
        """
        EMERGENCY KILL SWITCH:
        Cancels all pending open orders and flattens all open positions immediately.
        """
        logger.warning("!!! EMERGENCY KILL SWITCH ACTIVATED: FLATTENING ALL POSITIONS & CANCELING ORDERS !!!")
        if self.dry_run or not self.api_key or not self.secret_key:
            logger.info("[DRY-RUN KILL SWITCH] Mock flattened all positions and canceled orders.")
            return {"status": "success", "message": "Dry-run kill switch executed"}

        results = {"orders_canceled": False, "positions_flattened": False}
        
        # 1. Cancel all open orders
        orders_url = f"{self.endpoint}/orders"
        try:
            resp = requests.delete(orders_url, headers=self._get_headers(), timeout=10)
            resp.raise_for_status()
            results["orders_canceled"] = True
            logger.info("Successfully canceled all open Alpaca orders.")
        except Exception as e:
            logger.error(f"Failed to cancel open orders: {e}")

        # 2. Close all positions
        pos_url = f"{self.endpoint}/positions"
        try:
            resp = requests.delete(pos_url, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            results["positions_flattened"] = True
            logger.info("Successfully requested close/flatten on all active Alpaca positions.")
        except Exception as e:
            logger.error(f"Failed to flatten open positions: {e}")

        return results

    def map_symbol(self, internal_symbol: str) -> str:
        """Maps internal system symbol (e.g. BTCUSDT) to Alpaca symbol (e.g. BTC/USD)."""
        return self.symbol_map.get(internal_symbol, internal_symbol)

    def place_paper_order(
        self,
        signal_id: str,
        symbol: str,
        qty: float,
        side: str = "buy",
        order_type: str = "market",
        time_in_force: str = "gtc",
        estimated_price: float = 0.0
    ) -> Dict[str, Any]:
        """
        Executes paper market order on Alpaca REST endpoint with safety limit checks.
        Enforces duplicate signal_id protection and hard position size caps.
        """
        alpaca_symbol = self.map_symbol(symbol)

        # 1. Duplicate Signal Check
        if signal_id in self.executed_signal_ids:
            logger.warning(f"DUPLICATE ORDER BLOCKED: Signal ID {signal_id} has already been executed.")
            return {"status": "rejected", "reason": "Duplicate signal_id"}

        # 2. Hard Safety Limit Checks
        equity = self.get_account_equity()
        est_val = qty * estimated_price if estimated_price > 0 else 0.0

        if est_val > self.max_position_value_usd:
            logger.error(f"HARD RISK CAP BLOCKED ORDER: Estimated position value ${est_val:,.2f} exceeds limit ${self.max_position_value_usd:,.2f}")
            return {"status": "rejected", "reason": f"Exceeds max_position_value_usd (${self.max_position_value_usd})"}

        if equity > 0 and (est_val / equity) > self.max_position_equity_pct:
            logger.error(f"HARD RISK CAP BLOCKED ORDER: Position value represents {(est_val/equity):.1%} of equity, exceeding max {self.max_position_equity_pct:.1%}")
            return {"status": "rejected", "reason": f"Exceeds max_position_equity_pct ({self.max_position_equity_pct:.1%})"}

        self.executed_signal_ids.add(signal_id)

        # 3. Dry-Run Execution Branch
        if self.dry_run or not self.api_key or not self.secret_key:
            logger.info(f"[DRY-RUN PAPER ORDER] {side.upper()} {qty:.4f} {alpaca_symbol} @ ~${estimated_price:,.2f} (Signal: {signal_id})")
            return {
                "status": "dry_run_success",
                "id": f"mock_order_{signal_id}",
                "symbol": alpaca_symbol,
                "qty": qty,
                "side": side,
                "order_type": order_type
            }

        # 4. Format Quantity cleanly for Alpaca
        # Alpaca stocks require integer or float depending on fractional support.
        # Crypto permits fractional decimal quantities (e.g. 0.0154 BTC).
        if "/" in alpaca_symbol or "USD" in alpaca_symbol:
            qty_str = str(round(qty, 4))
        else:
            qty_str = str(int(qty)) if qty >= 1 else str(round(qty, 4))

        url = f"{self.endpoint}/orders"
        payload = {
            "symbol": alpaca_symbol,
            "qty": qty_str,
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
            "client_order_id": f"v5_{signal_id[:20]}"
        }

        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"[ALPACA PAPER ORDER EXECUTED] ID: {data.get('id')} | Symbol: {alpaca_symbol} | Side: {side} | Qty: {qty_str}")
            return data
        except Exception as e:
            logger.error(f"Alpaca Order Execution Failed for {alpaca_symbol}: {e}")
            return {"status": "failed", "reason": str(e)}
