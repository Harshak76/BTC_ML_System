"""
Alpaca Paper Trading Executor Module for V5 btc_ml_system.
Provides multi-asset (Equities + Crypto) order execution, position tracking,
order lifecycle polling, fractional order rules, account equity queries, hard risk limits,
and emergency kill-switch flattening via Alpaca REST API v2.
"""

import os
import re
import time
import logging
from typing import Dict, Any, Optional, List
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("btc_ml_system.alpaca_executor")


class AlpacaExecutor:
    """Interfaces with Alpaca Paper Trading REST API (https://paper-api.alpaca.markets/v2)."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.alp_cfg = config.get("alpaca", {})
        self.endpoint = (
            self.alp_cfg.get("endpoint") or
            os.environ.get("ALPACA_ENDPOINT") or
            "https://paper-api.alpaca.markets/v2"
        ).rstrip('/')

        # ---------------------------------------------------------------------
        # Non-Negotiable Safety Guard (SEC-003): Enforce Paper-Only Isolation
        # ---------------------------------------------------------------------
        allow_live_trading = (
            os.environ.get("ALLOW_LIVE_MONEY_TRADING", "false").lower() == "true" or
            bool(config.get("allow_live_money_trading", False))
        )
        if "paper" not in self.endpoint.lower() and not allow_live_trading:
            raise RuntimeError(
                f"CRITICAL SAFETY VIOLATION: Endpoint '{self.endpoint}' does not contain 'paper' "
                "and live-money trading is strictly disabled. Aborting immediately to prevent accidental real-money execution."
            )

        # ---------------------------------------------------------------------
        # API Keys Resolution (SEC-001): Environment primary, no hardcoded fallbacks
        # ---------------------------------------------------------------------
        self.api_key_env = self.alp_cfg.get("api_key_env", "ALPACA_API_KEY")
        self.secret_key_env = self.alp_cfg.get("secret_key_env", "ALPACA_SECRET_KEY")

        self.api_key = os.environ.get(self.api_key_env) or os.environ.get("ALPACA_API_KEY") or self.alp_cfg.get("api_key") or ""
        self.secret_key = os.environ.get(self.secret_key_env) or os.environ.get("ALPACA_SECRET_KEY") or self.alp_cfg.get("secret_key") or ""

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

        # Idempotency and executed signal tracking
        self.executed_signal_ids = set()

        if not self.api_key or not self.secret_key:
            logger.warning(
                f"Alpaca API keys ({self.api_key_env}/{self.secret_key_env}) not set. Defaulting to DRY-RUN Mode."
            )
            self.dry_run = True
        else:
            masked_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if len(self.api_key) >= 8 else "***"
            logger.info(f"AlpacaExecutor connected to Paper Trading Endpoint: {self.endpoint} (Dry-Run: {self.dry_run}, Key: {masked_key})")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json"
        }

    @staticmethod
    def sanitize_client_order_id(signal_id: str) -> str:
        """
        Generates deterministic, valid client_order_id complying with Alpaca API:
        Regex: ^[a-zA-Z0-9_-]+$, maximum length 128 chars.
        Replaces spaces, colons, plus signs, and periods with underscores.
        """
        clean_sig = re.sub(r"[^a-zA-Z0-9_-]", "_", str(signal_id))
        clean_sig = re.sub(r"_+", "_", clean_sig).strip("_")
        return f"v5_{clean_sig[:60]}"

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
        alpaca_sym = self.map_symbol(internal_symbol)
        clean_sym = alpaca_sym.replace("/", "")
        positions = self.get_open_positions()
        for pos in positions:
            p_sym = pos.get("symbol", "")
            if p_sym in [alpaca_sym, internal_symbol, clean_sym]:
                return pos
        return None

    def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Queries order details by Alpaca order ID."""
        if self.dry_run or not self.api_key or not self.secret_key:
            return None

        url = f"{self.endpoint}/orders/{order_id}"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            logger.error(f"Error querying order {order_id}: {e}")
            return None

    def poll_order_fill(
        self,
        order_id: str,
        max_wait_seconds: float = 4.0,
        poll_interval: float = 0.5
    ) -> Dict[str, Any]:
        """
        EXE-002: Bounded polling policy for order state verification.
        Distinguishes: filled, partially_filled, accepted/new, rejected, canceled, expired.
        Never treats an accepted order as filled without broker confirmation.
        """
        start_time = time.time()
        latest_data = {}

        while (time.time() - start_time) < max_wait_seconds:
            order_data = self.get_order_by_id(order_id)
            if not order_data:
                time.sleep(poll_interval)
                continue

            latest_data = order_data
            status = order_data.get("status", "").lower()

            if status == "filled":
                logger.info(
                    f"[ORDER FILLED] ID: {order_id} | Symbol: {order_data.get('symbol')} | "
                    f"Qty: {order_data.get('filled_qty')} | Avg Price: ${float(order_data.get('filled_avg_price', 0)):,.2f}"
                )
                return {
                    "status": "filled",
                    "order_id": order_id,
                    "symbol": order_data.get("symbol"),
                    "side": order_data.get("side"),
                    "filled_qty": float(order_data.get("filled_qty", 0.0)),
                    "filled_avg_price": float(order_data.get("filled_avg_price", 0.0)),
                    "raw_order": order_data
                }

            if status == "partially_filled":
                logger.warning(
                    f"[ORDER PARTIALLY FILLED] ID: {order_id} | Symbol: {order_data.get('symbol')} | "
                    f"Filled: {order_data.get('filled_qty')} / {order_data.get('qty')} @ ${float(order_data.get('filled_avg_price', 0)):,.2f}"
                )
                return {
                    "status": "partially_filled",
                    "order_id": order_id,
                    "symbol": order_data.get("symbol"),
                    "side": order_data.get("side"),
                    "filled_qty": float(order_data.get("filled_qty", 0.0)),
                    "filled_avg_price": float(order_data.get("filled_avg_price", 0.0)),
                    "raw_order": order_data
                }

            if status in ["rejected", "canceled", "expired", "suspended"]:
                reject_reason = order_data.get("reject_reason") or f"Broker status: {status}"
                logger.error(f"[ORDER {status.upper()}] ID: {order_id} | Reason: {reject_reason}")
                return {
                    "status": status,
                    "order_id": order_id,
                    "symbol": order_data.get("symbol"),
                    "reason": reject_reason,
                    "raw_order": order_data
                }

            time.sleep(poll_interval)

        # Timed out while still in transit (accepted / new / pending_new)
        unresolved_status = latest_data.get("status", "pending_unconfirmed")
        logger.warning(
            f"[ORDER UNRESOLVED] ID: {order_id} reached polling timeout ({max_wait_seconds}s). "
            f"Broker status remains '{unresolved_status}'. Recording as pending to prevent duplicates."
        )
        return {
            "status": "pending_unconfirmed",
            "order_id": order_id,
            "symbol": latest_data.get("symbol"),
            "side": latest_data.get("side"),
            "broker_status": unresolved_status,
            "raw_order": latest_data
        }

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

    def close_position(self, internal_symbol: str, qty: Optional[float] = None) -> Dict[str, Any]:
        """
        Closes an open position on Alpaca (e.g. Stop-Loss or Take-Profit hit).
        """
        alpaca_sym = self.map_symbol(internal_symbol)
        clean_sym = alpaca_sym.replace("/", "")
        logger.info(f"Closing position for {internal_symbol} ({clean_sym}) on Alpaca...")

        if self.dry_run or not self.api_key or not self.secret_key:
            logger.info(f"[DRY-RUN CLOSE POSITION] Mock closed position for {internal_symbol}.")
            return {"status": "dry_run_success", "symbol": internal_symbol}

        url = f"{self.endpoint}/positions/{clean_sym}"
        params = {}
        if qty is not None and qty > 0:
            params["qty"] = str(qty)

        try:
            resp = requests.delete(url, headers=self._get_headers(), params=params, timeout=10)
            if resp.status_code in [200, 204]:
                data = resp.json() if resp.text else {"status": "closed"}
                logger.info(f"[ALPACA POSITION CLOSED] Successfully closed position for {internal_symbol} on Alpaca: {data}")
                return data
            else:
                logger.warning(f"Close position returned {resp.status_code}: {resp.text}")
                return {"status": "failed", "code": resp.status_code, "error": resp.text}
        except Exception as e:
            logger.error(f"Failed to close Alpaca position for {internal_symbol}: {e}")
            return {"status": "failed", "error": str(e)}

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
        estimated_price: float = 0.0,
        verify_fill: bool = True
    ) -> Dict[str, Any]:
        """
        Executes paper market order on Alpaca REST endpoint with safety limit checks,
        sanitized client_order_id, fractional equity order rules, and order lifecycle verification.
        """
        alpaca_symbol = self.map_symbol(symbol)
        is_crypto = ("/" in alpaca_symbol or "USD" in alpaca_symbol)

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
                "filled_qty": qty,
                "filled_avg_price": estimated_price,
                "side": side,
                "order_type": order_type
            }

        # 4. Format Quantity & Enforce Fractional Rules (EXE-003)
        if is_crypto:
            # Alpaca crypto enforces minimum notional of $10
            if estimated_price > 0 and (qty * estimated_price) < 10.0:
                qty = 10.5 / estimated_price
            qty_str = str(round(qty, 4))
            selected_tif = time_in_force
        else:
            # US Equities: Fractional shares must use time_in_force="day"
            is_fractional = (qty < 1.0 or (qty % 1 != 0.0))
            if is_fractional:
                selected_tif = "day"
                qty_str = str(round(qty, 4))
                if time_in_force.lower() != "day":
                    logger.info(f"Auto-selected time_in_force='day' for fractional equity order ({alpaca_symbol} Qty: {qty_str})")
            else:
                selected_tif = time_in_force
                qty_str = str(int(qty))

        # 5. Deterministic, Valid Client Order ID (EXE-001)
        client_order_id = self.sanitize_client_order_id(signal_id)

        url = f"{self.endpoint}/orders"
        payload = {
            "symbol": alpaca_symbol,
            "qty": qty_str,
            "side": side,
            "type": order_type,
            "time_in_force": selected_tif,
            "client_order_id": client_order_id
        }

        try:
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            order_id = data.get("id")
            logger.info(f"[ALPACA ORDER SUBMITTED] ID: {order_id} | ClientOrderID: {client_order_id} | Symbol: {alpaca_symbol} | Side: {side} | Qty: {qty_str}")

            # 6. Order Fill Verification (EXE-002)
            if verify_fill and order_id:
                verified_res = self.poll_order_fill(order_id, max_wait_seconds=4.0, poll_interval=0.5)
                return verified_res

            return data
        except requests.exceptions.HTTPError as e:
            err_msg = resp.text if 'resp' in locals() and resp is not None else str(e)
            logger.error(f"Alpaca Order HTTP Error ({resp.status_code if 'resp' in locals() else 'unknown'}): {err_msg}")
            return {"status": "rejected", "reason": f"HTTP Error: {err_msg}"}
        except Exception as e:
            logger.error(f"Alpaca Order Execution Failed for {alpaca_symbol}: {e}")
            return {"status": "failed", "reason": str(e)}
