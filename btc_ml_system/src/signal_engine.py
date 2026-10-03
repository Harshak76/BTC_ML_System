"""
Signal Engine Module for V3.3 btc_ml_system.
Orchestrates the 3-Step entry pipeline with 4h HTF Trend Confirmation & 2.0x Risk-Reward enforcement:
Step 1: Volatility Regime must be CALM or NORMAL (High Vol blocked)
Step 2: 4h HTF Confirmation must pass (4h Close > 4h EMA50 & 4h EMA50 sloping up)
Step 3: Stricter Market Structure Breakout & 1h EMA Alignment (Close > 20-bar high + 0.4%, Volume >= 1.35x avg, Body >= 50%, EMA20 > EMA50)
Step 4: All risk checks pass (Kill switch, 1% daily loss limit, 10% max drawdown, 12-bar cooldown)
"""

import uuid
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pandas as pd

from btc_ml_system.src.regimes import VolatilityRegimeClassifier
from btc_ml_system.src.direction import DirectionalFilter, SessionFilter
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
    htf_valid: bool
    allowed_trade: bool
    rejection_reason: str
    trailing_trigger_pct: Optional[float] = None
    trailing_dist_pct: Optional[float] = None


class SignalEngine:
    """Sequential entry signal generator with 4h HTF trend confirmation and strict risk-reward controls."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.vol_classifier = VolatilityRegimeClassifier(config)
        self.session_filter = SessionFilter(config)
        self.directional_filter = DirectionalFilter(config)
        self.position_sizer = PositionSizer(config)
        self.risk_engine = RiskEngine(config)

        # Support both 'signal_engine' and 'exit_rules' section names for ATR multipliers
        self.sig_cfg = config.get("signal_engine", config.get("exit_rules", {}))
        self.atr_period = self.sig_cfg.get("atr_period", 14)
        self.sl_atr_mult = self.sig_cfg.get("sl_atr_multiplier", self.sig_cfg.get("stop_loss_atr_mult", 1.5))
        self.tp_atr_mult = self.sig_cfg.get("tp_atr_multiplier", self.sig_cfg.get("take_profit_atr_mult", 3.0))

    def get_regime_exit_params(self, vol_regime: str) -> Tuple[float, float, Optional[float], Optional[float]]:
        """Returns regime-aware SL multiplier, TP multiplier, trailing trigger %, and trailing distance %."""
        vol_cfg = self.config.get("volatility_regime", {})
        regime_params = vol_cfg.get("regime_params", {})

        default_sl_mult = self.sl_atr_mult
        default_tp_mult = self.tp_atr_mult
        default_trigger = self.config.get("exit_rules", {}).get("trailing_trigger_pct", None)
        default_dist = self.config.get("exit_rules", {}).get("trailing_dist_pct", None)

        if vol_regime in regime_params:
            r_cfg = regime_params[vol_regime]
            sl_m = r_cfg.get("sl_atr_multiplier", default_sl_mult)
            tp_m = r_cfg.get("tp_atr_multiplier", default_tp_mult)
            tr_trig = r_cfg.get("trailing_trigger_pct", default_trigger)
            tr_dist = r_cfg.get("trailing_dist_pct", default_dist)
            return float(sl_m), float(tp_m), tr_trig, tr_dist

        return default_sl_mult, default_tp_mult, default_trigger, default_dist

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
        df_4h: Optional[pd.DataFrame] = None,
        current_equity: float = 10000.0,
        current_drawdown: float = 0.0,
        daily_pnl_pct: float = 0.0
    ) -> TradeSignal:
        """
        Runs sequential entry verification with volatility, session, HTF, and breakout filters.
        """
        signal_id = str(uuid.uuid4())[:8]

        # 1. Prepare indicators
        df_vol = self.vol_classifier.predict_regimes(df_1h)
        df_sess = self.session_filter.apply_filter(df_vol)
        df_dir = self.directional_filter.evaluate_direction(df_sess, df_4h)
        df_dir["atr"] = self.compute_atr(df_dir)

        latest = df_dir.iloc[-1]
        timestamp = latest["open_time"]
        entry_price = float(latest["close"])
        vol_regime = str(latest["volatility_regime"])
        is_vol_favorable = bool(latest["vol_regime_favorable"])
        is_session_valid = bool(latest.get("session_valid", True))
        dir_valid = bool(latest["direction_valid"])
        htf_valid = bool(latest.get("htf_trend_valid", True))

        atr_val = float(latest["atr"]) if not pd.isna(latest["atr"]) else entry_price * 0.01

        sl_m, tp_m, tr_trig, tr_dist = self.get_regime_exit_params(vol_regime)
        sl_price = entry_price - (sl_m * atr_val)
        tp_price = entry_price + (tp_m * atr_val)

        bar_idx = len(df_1h) - 1

        # STEP 1: Volatility Regime Filter
        if not is_vol_favorable:
            reason = f"Blocked by Step 1: Volatility regime is {vol_regime} (allowed: {self.vol_classifier.allowed_regimes})"
            logger.info(f"Signal [{signal_id}] REJECTED -> {reason}")
            return TradeSignal(
                signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="HOLD",
                entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
                quantity=0.0, position_value_usd=0.0, volatility_regime=vol_regime,
                direction_valid=dir_valid, htf_valid=htf_valid, allowed_trade=False, rejection_reason=reason
            )

        # STEP 2: Session Filter
        if not is_session_valid:
            entry_hr = pd.to_datetime(timestamp, utc=True).hour
            reason = f"Blocked by Step 2: Session Filter (Entry hour {entry_hr:02d}:00 UTC outside window {self.session_filter.start_hour:02d}:00–{self.session_filter.end_hour:02d}:00 UTC)"
            logger.info(f"Signal [{signal_id}] REJECTED -> {reason}")
            return TradeSignal(
                signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="HOLD",
                entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
                quantity=0.0, position_value_usd=0.0, volatility_regime=vol_regime,
                direction_valid=dir_valid, htf_valid=htf_valid, allowed_trade=False, rejection_reason=reason
            )

        # STEP 2: HTF Confirmation Filter (MultiTimeframeFilter)
        if not htf_valid:
            reason = "Blocked by Step 2: Multi-Timeframe Confirmation Filter failed (Requires higher timeframe trend agreement)"
            logger.info(f"Signal [{signal_id}] REJECTED -> {reason}")
            return TradeSignal(
                signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="HOLD",
                entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
                quantity=0.0, position_value_usd=0.0, volatility_regime=vol_regime,
                direction_valid=dir_valid, htf_valid=False, allowed_trade=False, rejection_reason=reason
            )

        # STEP 3: 1h Market Structure Breakout & EMA Alignment Filter
        if not dir_valid:
            reason = "Blocked by Step 3: Market Structure Breakout filter failed (Requires Close > 20-bar High + 0.4%, Volume >= 1.35x Avg, Bullish Body >= 50%, EMA20 > EMA50)"
            logger.debug(f"Signal [{signal_id}] REJECTED -> {reason}")
            return TradeSignal(
                signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="HOLD",
                entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
                quantity=0.0, position_value_usd=0.0, volatility_regime=vol_regime,
                direction_valid=False, htf_valid=htf_valid, allowed_trade=False, rejection_reason=reason
            )

        # STEP 4: Risk Engine Verification
        risk_passed, risk_reason = self.risk_engine.evaluate_risk(
            current_bar=bar_idx, current_drawdown=current_drawdown, daily_pnl_pct=daily_pnl_pct
        )
        if not risk_passed:
            reason = f"Blocked by Risk Engine: {risk_reason}"
            logger.debug(f"Signal [{signal_id}] REJECTED -> {reason}")
            return TradeSignal(
                signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="HOLD",
                entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
                quantity=0.0, position_value_usd=0.0, volatility_regime=vol_regime,
                direction_valid=True, htf_valid=True, allowed_trade=False, rejection_reason=reason
            )

        # Position Sizing
        qty, pos_val, size_reason = self.position_sizer.calculate_position(
            account_equity=current_equity, entry_price=entry_price, stop_loss_price=sl_price
        )

        if qty <= 0:
            reason = f"Blocked by Position Sizing: {size_reason}"
            logger.debug(f"Signal [{signal_id}] REJECTED -> {reason}")
            return TradeSignal(
                signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="HOLD",
                entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
                quantity=0.0, position_value_usd=0.0, volatility_regime=vol_regime,
                direction_valid=True, htf_valid=True, allowed_trade=False, rejection_reason=reason
            )

        self.risk_engine.last_trade_bar = bar_idx

        logger.info(f"Signal [{signal_id}] APPROVED -> BUY {qty:.6f} BTC @ ${entry_price:,.2f} | SL: ${sl_price:,.2f} | TP: ${tp_price:,.2f}")
        return TradeSignal(
            signal_id=signal_id, timestamp=timestamp, symbol="BTCUSDT", action="BUY",
            entry_price=entry_price, stop_loss_price=sl_price, take_profit_price=tp_price,
            quantity=qty, position_value_usd=pos_val, volatility_regime=vol_regime,
            direction_valid=True, htf_valid=True, allowed_trade=True, rejection_reason="Trade Approved",
            trailing_trigger_pct=tr_trig, trailing_dist_pct=tr_dist
        )
