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


class DynamicRiskSizer:
    """
    Refined Dynamic Risk Sizer Module for btc_ml_system.
    Dynamically adjusts position risk per trade between min_risk_pct (0.40%) and max_risk_pct (0.80%)
    based on:
    1. Performance signal: Combined Win Rate + Expectancy (last performance_lookback trades)
       - Reduces risk ONLY if win_rate < 42% OR expectancy < 0.
       - Increases risk ONLY if win_rate >= 55% AND expectancy > 0.
    2. Volatility signal: Mild ATR ratio adjustment
       - Reduces risk ONLY when current ATR > 1.3x average ATR.
       - Does NOT increase risk when ATR is low.
    3. Step-change smoothing (max_step_change limit per trade, default 0.15%).
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.drs_cfg = config.get("dynamic_risk_sizer", {})
        self.enabled = self.drs_cfg.get("enabled", False)
        self.base_risk_pct = self.drs_cfg.get("base_risk_pct", 0.0050)      # 0.50% base risk
        self.min_risk_pct = self.drs_cfg.get("min_risk_pct", 0.0040)       # 0.40% min risk (safer floor)
        self.max_risk_pct = self.drs_cfg.get("max_risk_pct", 0.0080)       # 0.80% max risk (selective ceiling)
        self.perf_lookback = self.drs_cfg.get("performance_lookback", 15)
        self.vol_lookback = self.drs_cfg.get("volatility_lookback", 50)
        self.max_step_change = self.drs_cfg.get("max_step_change", 0.0015)  # 0.15% max jump per trade

        # Configurable performance & volatility thresholds
        self.win_rate_upside = self.drs_cfg.get("win_rate_upside_threshold", 0.55)
        self.win_rate_downside = self.drs_cfg.get("win_rate_downside_threshold", 0.42)
        self.vol_spike_thresh = self.drs_cfg.get("volatility_spike_threshold", 1.30)

        self.prev_risk_pct = self.base_risk_pct

    def calculate_risk_pct(
        self,
        recent_trades: list = None,
        current_atr: float = 0.0,
        historical_avg_atr: float = 0.0
    ) -> float:
        """
        Calculates refined dynamic risk percentage for the next trade.
        """
        if not self.enabled:
            return self.base_risk_pct

        # 1. Performance Signal: Win Rate + Expectancy over last N closed trades
        perf_mult = 1.0
        if recent_trades and len(recent_trades) > 0:
            sample = recent_trades[-self.perf_lookback:]
            wins = [t for t in sample if getattr(t, "pnl", 0.0) > 0]
            win_rate = len(wins) / len(sample)
            total_pnl = sum(getattr(t, "pnl", 0.0) for t in sample)
            avg_expectancy = total_pnl / len(sample)

            if win_rate < self.win_rate_downside or avg_expectancy < 0:
                # Poor performance -> reduce risk moderately towards min_risk_pct floor
                p_factor = (self.win_rate_downside - win_rate) / self.win_rate_downside if self.win_rate_downside > 0 else 0.5
                perf_mult = max(0.80, 1.0 - (0.20 * max(0.0, p_factor)))
            elif win_rate >= self.win_rate_upside and avg_expectancy > 0:
                # Strong performance -> increase risk selectively towards max_risk_pct ceiling
                p_factor = (win_rate - self.win_rate_upside) / (1.0 - self.win_rate_upside) if self.win_rate_upside < 1.0 else 0.5
                perf_mult = min(1.60, 1.0 + (0.60 * min(1.0, p_factor)))
            else:
                # Neutral performance (42% <= win_rate < 55%) -> stay at base risk
                perf_mult = 1.0

        # 2. Volatility Signal: Milder ATR reduction only when ATR > 1.3x average ATR
        vol_mult = 1.0
        if current_atr > 0 and historical_avg_atr > 0:
            vol_ratio = current_atr / historical_avg_atr
            if vol_ratio > self.vol_spike_thresh:
                # Elevated volatility -> mild risk reduction
                excess_vol = vol_ratio - self.vol_spike_thresh
                vol_mult = max(0.80, 1.0 - (0.40 * min(1.0, excess_vol)))
            else:
                # Normal or low volatility -> do NOT increase risk
                vol_mult = 1.0

        # Target Risk before smoothing
        raw_target_risk = self.base_risk_pct * perf_mult * vol_mult
        raw_target_risk = max(self.min_risk_pct, min(self.max_risk_pct, raw_target_risk))

        # 3. Smoothing step-change limit
        risk_diff = raw_target_risk - self.prev_risk_pct
        if abs(risk_diff) > self.max_step_change:
            step = self.max_step_change if risk_diff > 0 else -self.max_step_change
            smoothed_risk = self.prev_risk_pct + step
        else:
            smoothed_risk = raw_target_risk

        final_risk = max(self.min_risk_pct, min(self.max_risk_pct, smoothed_risk))
        self.prev_risk_pct = final_risk

        logger.info(
            f"DynamicRiskSizer: Final Risk={final_risk*100:.3f}% "
            f"(Base={self.base_risk_pct*100:.2f}%, PerfMult={perf_mult:.2f}, VolMult={vol_mult:.2f})"
        )
        return final_risk


