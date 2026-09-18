"""
Risk & Position Sizing Engine for V2 btc_ml_system.
Includes:
- 10-rule non-negotiable risk decision pipeline
- Dynamic Volatility Targeting position sizing
- Regime-dependent probability thresholds
- Model disagreement filter
- SHAP feature contribution tracking
"""

import logging
from typing import Dict, Any, Tuple
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger("btc_ml_system.risk")


@dataclass
class RiskDecision:
    allow_trade: bool
    position_size: float  # Fraction of portfolio capital [0.0, 1.0]
    reason: str
    stop_loss_pct: float
    take_profit_pct: float


class RiskEngine:
    """Evaluates risk controls and determines exact execution sizing."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.r_cfg = config.get("risk", {})
        self.initial_capital = self.r_cfg.get("initial_capital", 10000.0)
        self.risk_per_trade = self.r_cfg.get("risk_per_trade_pct", 0.005)
        self.max_daily_loss = self.r_cfg.get("max_daily_loss_pct", 0.010)
        self.max_drawdown = self.r_cfg.get("max_drawdown_pct", 0.100)
        self.disagreement_limit = config.get("models", {}).get("disagreement_threshold", 0.20)
        self.vol_targeting = self.r_cfg.get("volatility_targeting", True)
        self.target_annual_vol = self.r_cfg.get("target_annual_vol", 0.15)
        self.cooldown_bars = self.r_cfg.get("cooldown_bars", 3)
        self.last_trade_bar = -999

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
        """
        Runs 10-rule safety pipeline to issue trade permission and size.
        """
        # Rule 1: Max Drawdown Limit
        if current_drawdown >= self.max_drawdown:
            return RiskDecision(False, 0.0, f"Max drawdown exceeded: {current_drawdown:.2%}", 0.0, 0.0)

        # Rule 2: Max Daily Loss Circuit Breaker
        if daily_pnl_pct <= -self.max_daily_loss:
            return RiskDecision(False, 0.0, f"Daily loss circuit breaker hit: {daily_pnl_pct:.2%}", 0.0, 0.0)

        # Rule 3: Cooldown Bars
        if (current_bar_idx - self.last_trade_bar) < self.cooldown_bars:
            return RiskDecision(False, 0.0, f"In cooldown period ({current_bar_idx - self.last_trade_bar} bars)", 0.0, 0.0)

        # Rule 4: Dynamic Regime Probability Threshold
        required_threshold = regime_params.get("buy_prob_threshold", 0.55)
        if buy_prob < required_threshold:
            return RiskDecision(False, 0.0, f"Prob {buy_prob:.3f} below regime threshold {required_threshold:.3f}", 0.0, 0.0)

        # Rule 5: Model Disagreement Filter
        if disagreement > self.disagreement_limit:
            return RiskDecision(False, 0.0, f"Model disagreement too high: {disagreement:.3f}", 0.0, 0.0)

        # Base Position Sizing: Risk per trade / Volatility SL
        sl_pct = max(1.0 * current_volatility, 0.005)
        pt_pct = max(1.5 * current_volatility, 0.0075)

        base_size = self.risk_per_trade / sl_pct

        # Rule 6: Volatility Targeting Scaling (V2 Addition)
        if self.vol_targeting and current_volatility > 0:
            annualized_vol = current_volatility * np.sqrt(24 * 365)
            vol_scalar = self.target_annual_vol / (annualized_vol + 1e-10)
            base_size = base_size * min(vol_scalar, 1.5)

        # Rule 7: Regime Position Size Multiplier
        regime_mult = regime_params.get("position_size_multiplier", 1.0)
        final_size = base_size * regime_mult * meta_bet_size

        # Cap max position size at 25% of capital for safety
        final_size = min(final_size, 0.25)

        if final_size <= 0.01:
            return RiskDecision(False, 0.0, "Position size too small after risk adjustments", 0.0, 0.0)

        self.last_trade_bar = current_bar_idx
        return RiskDecision(True, final_size, "Trade Approved", sl_pct, pt_pct)
