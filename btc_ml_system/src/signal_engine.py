"""
Signal Engine Module for V3 btc_ml_system.
Orchestrates the 3-Step entry pipeline:
Step 1: Volatility Regime must be CALM or NORMAL (High Vol blocked)
Step 2: Directional filter must pass (Price > EMA50 and EMA50 sloping up)
Step 3: All risk checks pass (Kill switch, 1% daily loss limit, 10% max drawdown, cooldown)
"""

import uuid
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
import pandas as pd

from btc_ml_system.src.regimes import VolatilityRegimeClassifier
from btc_ml_system.src.direction import DirectionalFilter
from btc_ml_system.src.position_sizing import PositionSizer
from btc_ml_system.src.risk import RiskEngine

logger = logging.getLogger("btc_ml_system.signal_engine")


@dataclass
class TradeSignal:
    signal_id: str
    timestamp: pd.Timestamp
    symbol: str
    action: str  # BUY / HOLD
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    quantity: float
    position_value_usd: float
    volatility_regime: str
    direction_valid: bool
    allowed_trade: bool
    rejection_reason: str


class SignalEngine:
    """3-Step sequential entry signal generator."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.vol_classifier = VolatilityRegimeClassifier(config)
        self.directional_filter = DirectionalFilter(config)
        self.position_sizer = PositionSizer(config)
        self.risk_engine = RiskEngine(config)

        self.exit_cfg = config.get("exit_rules", {})
        self.atr_period = self.exit_cfg.get("atr_period", 14)
        self.sl_atr_mult = self.exit_cfg.get("stop_loss_atr_mult", 1.5)
        self.tp_atr_mult = self.exit_cfg.get("take_profit_atr_mult", 2.5)

    def compute_atr(self, df: pd.DataFrame) -> pd.Series:
        """Calculates Average True Range (ATR)."""
        high, low, close = df["high"], df["low"], df["close"]
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(alpha=1/self.atr_period, adjust=False).mean()

    def generate_signal(
        self,
        df_1h: pd.DataFrame,
        current_equity: float = 10000.0,
        current_drawdown: float = 0.0,
        daily_pnl_pct: float = 0.0
    ) -> TradeSignal:
        """
        Runs 3-Step sequential entry verification on latest bar.
        Returns TradeSignal with unique ID and rejection logging.
        """
        signal_id = str(uuid.uuid4())[:8]

        # 1. Prepare indicators
        df_vol = self.vol_classifier.predict_regimes(df_1h)
        df_dir = self.directional_filter.evaluate_direction(df_vol)
        df_dir["atr"] = self.compute_atr(df_dir)

        latest = df_dir.iloc[-1]
        timestamp = latest["open_time"]
        entry_price = float(latest["close"])
        vol_regime = str(latest["volatility_regime"])
        is_vol_favorable = bool(latest["vol_regime_favorable"])
        dir_valid = bool(latest["direction_valid"])
        atr_val = float(latest["atr"]) if not pd.isna(latest["atr"]) else entry_price * 0.01

        sl_price = entry_price - (self.sl_atr_mult * atr_val)
        tp_price = entry_price + (self.tp_atr_mult * atr_val)

        bar_idx = len(df_1h) - 1

        # STEP 1: Volatility Regime Filter
        if not is_vol_favorable:
            reason = f"Blocked by Step 1: Volatility regime is {vol_regime} (only CALM/NORMAL allowed)"
            logger.debug(f"Signal [{signal_id}] REJECTED -> {reason}")
            return TradeSignal(
                signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="HOLD",
                entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
                quantity=0.0, position_value_usd=0.0, volatility_regime=vol_regime,
                direction_valid=dir_valid, allowed_trade=False, rejection_reason=reason
            )

        # STEP 2: Directional Condition Filter (Price > EMA50 and EMA50 sloping up)
        if not dir_valid:
            reason = "Blocked by Step 2: Directional filter failed (Requires Price > EMA50 & EMA50 sloping up)"
            logger.debug(f"Signal [{signal_id}] REJECTED -> {reason}")
            return TradeSignal(
                signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="HOLD",
                entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
                quantity=0.0, position_value_usd=0.0, volatility_regime=vol_regime,
                direction_valid=False, allowed_trade=False, rejection_reason=reason
            )

        # STEP 3: Risk Engine Checks
        risk_passed, risk_reason = self.risk_engine.evaluate_risk(bar_idx, current_drawdown, daily_pnl_pct)
        if not risk_passed:
            reason = f"Blocked by Step 3: {risk_reason}"
            logger.debug(f"Signal [{signal_id}] REJECTED -> {reason}")
            return TradeSignal(
                signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="HOLD",
                entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
                quantity=0.0, position_value_usd=0.0, volatility_regime=vol_regime,
                direction_valid=True, allowed_trade=False, rejection_reason=reason
            )

        # STEP 4: Position Sizing (Risk 0.5% equity)
        qty, pos_val, size_reason = self.position_sizer.calculate_position(current_equity, entry_price, sl_price)
        if qty <= 0:
            reason = f"Blocked by Position Sizing: {size_reason}"
            logger.debug(f"Signal [{signal_id}] REJECTED -> {reason}")
            return TradeSignal(
                signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="HOLD",
                entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
                quantity=0.0, position_value_usd=0.0, volatility_regime=vol_regime,
                direction_valid=True, allowed_trade=False, rejection_reason=reason
            )

        logger.debug(f"Signal [{signal_id}] APPROVED -> BUY {qty:.4f} BTC (${pos_val:.2f}) | Regime={vol_regime}")
        return TradeSignal(
            signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="BUY",
            entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
            quantity=qty, position_value_usd=pos_val, volatility_regime=vol_regime,
            direction_valid=True, allowed_trade=True, rejection_reason="Trade Approved"
        )
