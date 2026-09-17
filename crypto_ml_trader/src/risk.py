"""
Risk Management & Decision Engine Module.
Enforces fixed-fractional position sizing, daily loss locks, maximum drawdown shutdown,
cooldown periods, and the 10 hard trade entry validation checks.
"""

import logging
from typing import Dict, Any, Tuple, Optional
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class RiskManager:
    """Manages risk limits, equity high-water marks, daily PnL, position sizing, and kill switches."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.initial_capital = self.config.get("initial_capital", 10000.0)
        self.risk_per_trade_pct = self.config.get("risk_per_trade_pct", 0.005) # 0.5%
        self.max_daily_loss_pct = self.config.get("max_daily_loss_pct", 0.010) # 1.0%
        self.max_drawdown_pct = self.config.get("max_drawdown_pct", 0.100)    # 10.0%
        self.min_reward_risk_ratio = self.config.get("min_reward_risk_ratio", 1.5)
        self.min_expected_edge_bps = self.config.get("min_expected_edge_bps", 20)
        self.cooldown_bars = self.config.get("cooldown_bars", 3)
        self.commission_bps = self.config.get("commission_bps", 10)
        self.slippage_bps = self.config.get("slippage_bps", 5)

        # Dynamic State Variables
        self.current_equity = self.initial_capital
        self.high_water_mark = self.initial_capital
        self.start_of_day_equity = self.initial_capital
        self.realized_pnl_today = 0.0
        self.unrealized_pnl = 0.0
        self.current_drawdown_pct = 0.0

        # Kill Switch States
        self.daily_loss_locked = False
        self.max_dd_shutdown = False
        self.cooldown_remaining = 0
        self.manual_reset_required = False

    def reset_daily_pnl(self, new_day_equity: Optional[float] = None):
        """Called at start of new 24h trading day."""
        if new_day_equity is not None:
            self.start_of_day_equity = new_day_equity
        else:
            self.start_of_day_equity = self.current_equity

        self.realized_pnl_today = 0.0
        self.daily_loss_locked = False
        logger.info(f"Daily PnL reset. Start of day equity: {self.start_of_day_equity:.2f} USDT")

    def update_equity(self, current_equity: float, open_pnl: float = 0.0):
        """Updates equity, high-water mark, drawdown, and evaluates kill switches."""
        self.current_equity = current_equity
        self.unrealized_pnl = open_pnl

        if current_equity > self.high_water_mark:
            self.high_water_mark = current_equity

        # Drawdown calculation
        self.current_drawdown_pct = (self.high_water_mark - current_equity) / self.high_water_mark

        # Max Drawdown Shutdown check (10%)
        if self.current_drawdown_pct >= self.max_drawdown_pct:
            self.max_dd_shutdown = True
            self.manual_reset_required = True
            logger.critical(
                f"MAX DRAWDOWN SHUTDOWN TRIGGERED! "
                f"Drawdown = {self.current_drawdown_pct*100:.2f}% >= {self.max_drawdown_pct*100:.2f}%. "
                f"Trading halted until manual reset."
            )

        # Daily Loss Lock check (1%)
        total_daily_pnl = self.realized_pnl_today + self.unrealized_pnl
        daily_loss_limit = self.start_of_day_equity * self.max_daily_loss_pct
        if -total_daily_pnl >= daily_loss_limit:
            self.daily_loss_locked = True
            logger.warning(
                f"DAILY LOSS LOCK TRIGGERED! "
                f"Daily PnL = {total_daily_pnl:.2f} USDT ({-total_daily_pnl/self.start_of_day_equity*100:.2f}%) "
                f"exceeds limit of {self.max_daily_loss_pct*100:.2f}%."
            )

    def trigger_cooldown(self):
        """Triggers cooldown counter after trade exit."""
        self.cooldown_remaining = self.cooldown_bars

    def decrement_cooldown(self):
        """Decrements cooldown counter at each new candle close."""
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float
    ) -> Dict[str, float]:
        """
        Calculates fixed-fractional position size based on 0.5% risk per trade.
        Position Size = (Equity * Risk_Pct) / Stop_Loss_Distance_In_Price.
        """
        if entry_price <= 0 or stop_loss_price <= 0 or stop_loss_price >= entry_price:
            return {"units": 0.0, "position_value_usdt": 0.0, "risk_usdt": 0.0}

        risk_usdt = self.current_equity * self.risk_per_trade_pct
        stop_dist = entry_price - stop_loss_price
        units = risk_usdt / stop_dist
        position_value = units * entry_price

        # Cap leverage at 1.0x (Binance Spot, no margin)
        max_units = self.current_equity / entry_price
        if units > max_units:
            units = max_units
            position_value = units * entry_price
            risk_usdt = units * stop_dist

        return {
            "units": units,
            "position_value_usdt": position_value,
            "risk_usdt": risk_usdt
        }

    def manual_reset_shutdown(self):
        """Explicit manual reset method for Max Drawdown Shutdown."""
        self.max_dd_shutdown = False
        self.manual_reset_required = False
        self.high_water_mark = self.current_equity
        logger.info("Manual reset executed. Max Drawdown Shutdown cleared.")


class DecisionEngine:
    """
    Evaluates 10 hard trade entry validation checks before granting execution permission.
    Returns decision dict with ACTION ('BUY' or 'HOLD') and exact rejection reason.
    """

    def __init__(self, risk_manager: RiskManager, config: Optional[Dict[str, Any]] = None):
        self.risk_manager = risk_manager
        self.config = config or {}
        self.prob_threshold = self.config.get("buy_probability_threshold", 0.55)
        self.disagreement_limit = self.config.get("disagreement_threshold", 0.20)
        self.min_expected_edge_bps = self.config.get("min_expected_edge_bps", 20)
        self.min_rr_ratio = self.config.get("min_reward_risk_ratio", 1.5)

    def evaluate(
        self,
        buy_probability: float,
        model_disagreement: float,
        htf_permits_long: bool,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        has_open_position: bool,
        is_market_tradable: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluates the 10 hard conditions:
        1. Market tradable & complete
        2. 4h HTF regime permits long
        3. Lower-timeframe structure valid
        4. Calibrated BUY prob >= threshold
        5. Expected edge >= minimum edge
        6. Reward-to-risk ratio acceptable
        7. Model disagreement within limit
        8. Risk limits (daily loss, max DD) inactive
        9. No active cooldown
        10. No existing open position
        """
        # Rule 1: Market tradable
        if not is_market_tradable:
            return {"action": "HOLD", "reason": "Market untradable or incomplete bar data."}

        # Rule 2: 4h HTF regime check
        if not htf_permits_long:
            return {"action": "HOLD", "reason": "4h Higher Timeframe regime does not permit long trades."}

        # Rule 3: Valid price structure
        if entry_price <= 0 or stop_loss_price >= entry_price or take_profit_price <= entry_price:
            return {"action": "HOLD", "reason": "Invalid price structure (SL >= Entry or TP <= Entry)."}

        # Rule 4: Calibrated BUY probability threshold
        if buy_probability < self.prob_threshold:
            return {"action": "HOLD", "reason": f"BUY probability ({buy_probability:.4f}) below threshold ({self.prob_threshold:.4f})."}

        # Rule 5: Reward-to-Risk ratio check
        stop_dist = entry_price - stop_loss_price
        tp_dist = take_profit_price - entry_price
        rr_ratio = tp_dist / (stop_dist + 1e-10)

        if rr_ratio < self.min_rr_ratio:
            return {"action": "HOLD", "reason": f"Reward-to-Risk ratio ({rr_ratio:.2f}) below minimum required ({self.min_rr_ratio:.2f})."}

        # Rule 6: Expected Edge calculation (prob * TP - (1-prob) * SL - total fees)
        total_fees_bps = (self.risk_manager.commission_bps + self.risk_manager.slippage_bps) * 2 # round trip
        fee_pct = total_fees_bps / 10000.0

        expected_return_pct = buy_probability * (tp_dist / entry_price) - (1.0 - buy_probability) * (stop_dist / entry_price) - fee_pct
        expected_edge_bps = expected_return_pct * 10000.0

        if expected_edge_bps < self.min_expected_edge_bps:
            return {"action": "HOLD", "reason": f"Expected edge ({expected_edge_bps:.1f} bps) below minimum ({self.min_expected_edge_bps} bps)."}

        # Rule 7: Model disagreement check
        if model_disagreement > self.disagreement_limit:
            return {"action": "HOLD", "reason": f"Model disagreement ({model_disagreement:.4f}) exceeds limit ({self.disagreement_limit:.4f})."}

        # Rule 8: Risk limits inactive (Daily loss lock & Max DD shutdown)
        if self.risk_manager.max_dd_shutdown:
            return {"action": "HOLD", "reason": "Maximum Drawdown Shutdown is active (requires manual reset)."}
        if self.risk_manager.daily_loss_locked:
            return {"action": "HOLD", "reason": "Daily Loss Lock is active."}

        # Rule 9: No active cooldown
        if self.risk_manager.cooldown_remaining > 0:
            return {"action": "HOLD", "reason": f"Cooldown active ({self.risk_manager.cooldown_remaining} bars remaining)."}

        # Rule 10: No existing position
        if has_open_position:
            return {"action": "HOLD", "reason": "Position already open (max 1 open position allowed, no pyramiding)."}

        # All 10 conditions passed -> BUY signal granted
        sizing = self.risk_manager.calculate_position_size(entry_price, stop_loss_price)

        return {
            "action": "BUY",
            "reason": "All 10 trade entry validation checks satisfied.",
            "buy_probability": buy_probability,
            "expected_edge_bps": expected_edge_bps,
            "rr_ratio": rr_ratio,
            "entry_price": entry_price,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            "position_units": sizing["units"],
            "position_value_usdt": sizing["position_value_usdt"],
            "risk_usdt": sizing["risk_usdt"]
        }
