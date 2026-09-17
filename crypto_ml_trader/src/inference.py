"""
Continuous Inference Engine Module.
Runs on every new 1h candle close or on-demand.
Outputs structured JSON decision report for paper/live execution.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from crypto_ml_trader.src.features import FeatureEngineer
from crypto_ml_trader.src.regimes import RegimeDetector
from crypto_ml_trader.src.models import ModelFactory
from crypto_ml_trader.src.calibration import ModelCalibrator, EnsembleMetaModel
from crypto_ml_trader.src.risk import RiskManager, DecisionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class InferencePipeline:
    """Inference Engine that processes latest candle data and returns trade decision."""

    def __init__(
        self,
        config: Dict[str, Any],
        model_path: str = "models/lightgbm_model.joblib",
        scaler_path: str = "models/scaler.joblib",
        calibrator_path: Optional[str] = "models/calibrator.joblib"
    ):
        self.config = config
        self.fe = FeatureEngineer(config.get("features", {}))
        self.regime_detector = RegimeDetector(config.get("regimes", {}))
        self.risk_manager = RiskManager(config.get("risk", {}))
        self.decision_engine = DecisionEngine(self.risk_manager, config.get("models", {}))

        # Load persisted model and scaler artifacts
        self.model = ModelFactory.load_artifact(model_path) if os.path.exists(model_path) else None
        self.scaler = ModelFactory.load_artifact(scaler_path) if os.path.exists(scaler_path) else None
        self.calibrator = ModelFactory.load_artifact(calibrator_path) if (calibrator_path and os.path.exists(calibrator_path)) else None

    def process_new_candle(
        self,
        df_1h: pd.DataFrame,
        df_4h: pd.DataFrame,
        has_open_position: bool = False
    ) -> Dict[str, Any]:
        """Processes latest candle data and generates point-in-time trade decision."""
        if df_1h.empty or df_4h.empty:
            return {"action": "HOLD", "reason": "Empty input data provided."}

        # 1. Feature Engineering
        df_1h_feat = self.fe.create_1h_features(df_1h)
        df_merged = self.fe.merge_confirmed_4h_features(df_1h_feat, df_4h)
        df_annotated = self.regime_detector.annotate_dataframe(df_merged)

        latest_row = df_annotated.iloc[-1]
        timestamp = latest_row["open_time"].isoformat()
        close_p = float(latest_row["close"])

        # 2. Extract feature vector X
        ignore_cols = [
            "open_time", "close_time", "open", "high", "low", "close", "volume",
            "quote_asset_volume", "number_of_trades", "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume", "market_regime", "htf_permits_long",
            "label_tb", "target_buy", "fwd_return_12h", "mfe_12h", "mae_12h",
            "barrier_touch_type", "barrier_touch_bars"
        ]
        feat_cols = [c for c in df_annotated.columns if c not in ignore_cols]

        X_latest = latest_row[feat_cols].values.reshape(1, -1)

        # Scale features
        if self.scaler is not None:
            X_latest_scaled = self.scaler.transform(X_latest)
        else:
            X_latest_scaled = X_latest

        # 3. Model Inference & Calibration
        if self.model is not None:
            if hasattr(self.model, "predict_proba"):
                raw_prob = float(self.model.predict_proba(X_latest_scaled)[0, 1])
            else:
                raw_prob = float(self.model.predict(X_latest_scaled)[0])

            if self.calibrator is not None:
                calibrated_prob = float(self.calibrator.calibrate(np.array([raw_prob]))[0])
            else:
                calibrated_prob = raw_prob
        else:
            logger.warning("No model loaded! Defaulting to 0.50 probability.")
            calibrated_prob = 0.50

        # 4. Price structure targets
        norm_atr = float(latest_row.get("norm_atr_14", 0.02))
        vol = max(norm_atr * close_p, close_p * 0.005)
        stop_loss_price = close_p - 1.0 * vol
        take_profit_price = close_p + 1.5 * vol
        htf_permits = bool(latest_row.get("htf_permits_long", True))

        # 5. Evaluate Decision Engine
        decision = self.decision_engine.evaluate(
            buy_probability=calibrated_prob,
            model_disagreement=0.0,
            htf_permits_long=htf_permits,
            entry_price=close_p,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            has_open_position=has_open_position,
            is_market_tradable=True
        )

        decision["timestamp_utc"] = timestamp
        decision["symbol"] = self.config.get("asset", {}).get("primary_symbol", "BTCUSDT")
        decision["market_regime"] = str(latest_row.get("market_regime", "UNKNOWN"))

        logger.info(f"Inference Cycle [{timestamp}]: Decision = {decision['action']} | Reason = {decision['reason']}")

        return decision
