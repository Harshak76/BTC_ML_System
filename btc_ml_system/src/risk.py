"""
Risk Engine Module for V3 btc_ml_system.
Includes:
- Kill switch check
- Daily loss circuit breaker (1%)
- Max drawdown limit (10%)
- Trade cooldown tracking
"""

import logging
from typing import Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger("btc_ml_system.risk")


@dataclass
class RiskDecision:
    allow_trade: bool
    position_size: float
    reason: str
    stop_loss_pct: float
    take_profit_pct: float


class RiskEngine:
    """Evaluates non-negotiable risk limits before trade execution."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.r_cfg = config.get("risk", {})
        self.initial_capital = self.r_cfg.get("initial_capital", 10000.0)
        self.risk_per_trade = self.r_cfg.get("risk_per_trade_pct", 0.005)
        self.max_daily_loss = self.r_cfg.get("max_daily_loss_pct", 0.010)
        self.max_drawdown = self.r_cfg.get("max_drawdown_pct", 0.100)
        self.cooldown_bars = self.r_cfg.get("cooldown_bars", 2)
        self.kill_switch = self.r_cfg.get("kill_switch_enabled", True)
        self.is_kill_switch_active = False
        self.last_trade_bar = -999

    def trigger_kill_switch(self, reason: str = "Manual trigger"):
        """Activates emergency kill switch blocking all new trades."""
        self.is_kill_switch_active = True
        logger.critical(f"RISK KILL SWITCH ACTIVATED: {reason}")

    def evaluate_risk(
        self,
        current_bar_idx: int,
        current_drawdown: float,
        daily_pnl_pct: float
    ) -> Tuple[bool, str]:
        """
        Evaluates risk constraints:
        1. Kill Switch
        2. Max Drawdown (10%)
        3. Daily Loss Circuit Breaker (1%)
        4. Cooldown Period
        """
        if self.is_kill_switch_active:
            return False, "Kill switch is ACTIVE - all trading blocked"

        if current_drawdown >= self.max_drawdown:
            self.trigger_kill_switch(f"Max drawdown reached ({current_drawdown:.2%})")
            return False, f"Max drawdown limit hit ({current_drawdown:.2%} >= {self.max_drawdown:.2%})"

        if daily_pnl_pct <= -self.max_daily_loss:
            return False, f"Daily loss circuit breaker hit ({daily_pnl_pct:.2%} <= -{self.max_daily_loss:.2%})"

        if (current_bar_idx - self.last_trade_bar) < self.cooldown_bars:
            return False, f"In cooldown period ({current_bar_idx - self.last_trade_bar} < {self.cooldown_bars} bars)"

        return True, "Risk checks PASSED"

    def evaluate_trade(
        self,
        current_bar_idx: int,
        buy_prob: float,
        disagreement: float,
        regime_params: Dict[str, float],
        current_volatility: float,
        current_drawdown: float,
        daily_pnl_pct: float,
        meta_bet_size: float = 1.0
    ) -> RiskDecision:
        """Backward compatibility interface for V2/V2.1 backtester calls."""
        passed, reason = self.evaluate_risk(current_bar_idx, current_drawdown, daily_pnl_pct)
        if not passed:
            return RiskDecision(False, 0.0, reason, 0.0, 0.0)

        sl_pct = max(1.5 * current_volatility, 0.01)
        pt_pct = max(2.5 * current_volatility, 0.02)
        
        self.last_trade_bar = current_bar_idx
        return RiskDecision(True, 0.25, "Trade Approved", sl_pct, pt_pct)
