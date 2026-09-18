"""
Inference & Real-Time Pipeline Module for V2 btc_ml_system.
Provides single-bar feature pipeline, model inference, and risk evaluation.
"""

import logging
from typing import Dict, Any, Tuple
import pandas as pd
import numpy as np

from btc_ml_system.src.features import FeatureEngineer
from btc_ml_system.src.regimes import RegimeDetector
from btc_ml_system.src.models import EnsembledModel
from btc_ml_system.src.calibration import ProbabilityCalibrator
from btc_ml_system.src.meta_labeling import MetaLabeler
from btc_ml_system.src.risk import RiskEngine

logger = logging.getLogger("btc_ml_system.inference")


class LiveInferencePipeline:
    """Production inference pipeline for real-time trade generation."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.feature_eng = FeatureEngineer(config)
        self.regime_det = RegimeDetector(config)
        self.model = EnsembledModel(config)
        self.calibrator = ProbabilityCalibrator(config)
        self.meta_labeler = MetaLabeler(config)
        self.risk_engine = RiskEngine(config)

    def predict_latest_bar(
        self,
        df_1h: pd.DataFrame,
        df_4h: pd.DataFrame,
        current_drawdown: float = 0.0,
        daily_pnl_pct: float = 0.0
    ) -> Dict[str, Any]:
        """
        Runs live end-to-end inference on the latest bar of data.
        Returns complete trade signal and risk decision object.
        """
        # 1. Feature Engineering
        feat_df = self.feature_eng.create_features(df_1h, df_4h)
        feat_cols = self.feature_eng.get_feature_names(feat_df)
        latest_row = feat_df.iloc[[-1]]
        X_latest = latest_row[feat_cols]

        # 2. Regime Detection
        reg_df = self.regime_det.detect_regimes(feat_df)
        current_regime = reg_df["regime"].iloc[-1]
        regime_params = self.regime_det.get_regime_parameters(current_regime)

        # 3. Model Inference & Calibration
        raw_prob, model_dict = self.model.predict_proba(X_latest)
        calibrated_prob = self.calibrator.calibrate(raw_prob)[0]
        disagreement = self.model.calculate_disagreement(model_dict)[0]

        # 4. Meta-Labeling Sizing
        meta_prob = self.meta_labeler.predict_meta_prob(X_latest)[0]
        meta_bet_size = self.meta_labeler.compute_bet_size(
            np.array([calibrated_prob]),
            np.array([meta_prob]),
            threshold=regime_params.get("buy_prob_threshold", 0.55)
        )[0]

        # 5. Risk Engine Decision
        vol = latest_row["vol_24h"].iloc[0] if "vol_24h" in latest_row.columns else 0.01
        bar_idx = len(df_1h) - 1

        decision = self.risk_engine.evaluate_trade(
            current_bar_idx=bar_idx,
            buy_prob=calibrated_prob,
            disagreement=disagreement,
            regime_params=regime_params,
            current_volatility=vol,
            current_drawdown=current_drawdown,
            daily_pnl_pct=daily_pnl_pct,
            meta_bet_size=meta_bet_size
        )

        return {
            "timestamp": latest_row["open_time"].iloc[0],
            "current_regime": current_regime,
            "raw_probability": float(raw_prob[0]),
            "calibrated_probability": float(calibrated_prob),
            "disagreement": float(disagreement),
            "meta_bet_size": float(meta_bet_size),
            "allow_trade": decision.allow_trade,
            "position_size": decision.position_size,
            "stop_loss_pct": decision.stop_loss_pct,
            "take_profit_pct": decision.take_profit_pct,
            "reason": decision.reason
        }
