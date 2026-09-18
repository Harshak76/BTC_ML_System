"""
Inference & Real-Time Pipeline Module for V3 btc_ml_system.
Provides single-bar real-time trade signal generation using Volatility Regime + Directional Filter.
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd

from btc_ml_system.src.signal_engine import SignalEngine, TradeSignal
from btc_ml_system.src.alpaca_executor import AlpacaExecutor

logger = logging.getLogger("btc_ml_system.inference")


class LiveInferencePipeline:
    """Production inference pipeline for V3 Volatility + Directional trade generation."""

    def __init__(self, config: Dict[str, Any], model: Optional[Any] = None):
        self.config = config
        self.signal_engine = SignalEngine(config)
        self.alpaca_executor = AlpacaExecutor(config)

    def fit_pipeline(self, df_1h: pd.DataFrame, df_4h: Optional[pd.DataFrame] = None):
        """No ML model fitting required for V3 fixed regime + directional rules."""
        pass

    def predict_latest_bar(
        self,
        df_1h: pd.DataFrame,
        df_4h: Optional[pd.DataFrame] = None,
        current_drawdown: float = 0.0,
        daily_pnl_pct: float = 0.0
    ) -> Dict[str, Any]:
        """
        Runs live V3 signal generation on the latest bar.
        If BUY signal generated, triggers paper execution on Alpaca.
        """
        equity = self.alpaca_executor.get_account_equity()
        sig: TradeSignal = self.signal_engine.generate_signal(
            df_1h=df_1h,
            current_equity=equity,
            current_drawdown=current_drawdown,
            daily_pnl_pct=daily_pnl_pct
        )

        exec_res = {}
        if sig.action == "BUY" and sig.allowed_trade:
            exec_res = self.alpaca_executor.place_paper_order(
                signal_id=sig.signal_id,
                symbol=self.config.get("asset", {}).get("alpaca_symbol", "BTC/USD"),
                qty=sig.quantity,
                side="buy"
            )

        return {
            "signal_id": sig.signal_id,
            "timestamp": sig.timestamp,
            "volatility_regime": sig.volatility_regime,
            "direction_valid": sig.direction_valid,
            "action": sig.action,
            "allowed_trade": sig.allowed_trade,
            "entry_price": sig.entry_price,
            "stop_loss_price": sig.stop_loss_price,
            "take_profit_price": sig.take_profit_price,
            "quantity": sig.quantity,
            "position_value_usd": sig.position_value_usd,
            "rejection_reason": sig.rejection_reason,
            "alpaca_execution": exec_res
        }
