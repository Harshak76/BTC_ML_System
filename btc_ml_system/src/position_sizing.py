"""
Position Sizing Module for V3 btc_ml_system.
Calculates exact position size and quantity risking 0.5% of current equity per trade.
"""

import logging
from typing import Dict, Any, Tuple
import numpy as np

logger = logging.getLogger("btc_ml_system.position_sizing")


class PositionSizer:
    """Calculates quantity and position size based on fixed 0.5% equity risk per trade."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ps_cfg = config.get("position_sizing", {})
        self.risk_pct = self.ps_cfg.get("risk_per_trade_pct", 0.005)  # 0.5%
        self.max_cap_fraction = self.ps_cfg.get("max_capital_fraction", 0.25)
        self.min_notional = self.ps_cfg.get("min_order_notional", 10.0)

    def calculate_position(
        self,
        current_equity: float,
        entry_price: float,
        stop_loss_price: float
    ) -> Tuple[float, float, str]:
        """
        Calculates quantity and position value in USD.
        Formula:
        Dollar Risk = Equity * 0.005
        Risk Per Unit = entry_price - stop_loss_price
        Quantity = Dollar Risk / Risk Per Unit
        Returns (qty, position_value_usd, size_reason).
        """
        if current_equity <= 0 or entry_price <= 0:
            return 0.0, 0.0, "Invalid equity or price"

        stop_distance = abs(entry_price - stop_loss_price)
        if stop_distance <= 0:
            return 0.0, 0.0, "Stop loss distance is zero"

        dollar_risk = current_equity * self.risk_pct
        qty = dollar_risk / stop_distance
        pos_value = qty * entry_price

        # Cap max position value at 25% of current equity
        max_allowed_val = current_equity * self.max_cap_fraction
        if pos_value > max_allowed_val:
            pos_value = max_allowed_val
            qty = pos_value / entry_price
            reason = "Quantity capped by max capital fraction limit (25%)"
        else:
            reason = "Quantity calculated strictly from 0.5% risk rule"

        if pos_value < self.min_notional:
            return 0.0, 0.0, f"Position value ${pos_value:.2f} below minimum notional ${self.min_notional}"

        return qty, pos_value, reason
