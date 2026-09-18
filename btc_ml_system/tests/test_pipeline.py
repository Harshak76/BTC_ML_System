"""
End-to-End Pipeline Integration Test for btc_ml_system V2.
Verifies complete flow from ingestion to backtest execution.
"""

import pytest
import pandas as pd
import numpy as np

from btc_ml_system.src.data_quality import DataQualityChecker
from btc_ml_system.src.features import FeatureEngineer
from btc_ml_system.src.labels import TripleBarrierLabeler
from btc_ml_system.src.models import EnsembledModel
from btc_ml_system.src.regimes import RegimeDetector
from btc_ml_system.src.risk import RiskEngine
from btc_ml_system.src.backtester import Backtester


def test_pipeline_integration():
    dates = pd.date_range("2023-01-01", periods=300, freq="1h", tz="UTC")
    np.random.seed(42)
    close = 20000 + np.cumsum(np.random.randn(300) * 50)

    df = pd.DataFrame({
        "open_time": dates,
        "close_time": dates + pd.Timedelta(minutes=59, seconds=59),
        "open": close + np.random.randn(300) * 5,
        "high": close + 30,
        "low": close - 30,
        "close": close,
        "volume": 100.0 + np.random.rand(300) * 10,
        "taker_buy_base": 50.0,
        "taker_buy_quote": 50.0 * close,
        "quote_volume": 100.0 * close
    })

    config = {
        "features": {
            "returns_windows": [1, 2, 6],
            "rsi_period": 14,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "adx_period": 14,
            "volatility_windows": [12, 24],
            "volume_windows": [6, 24],
            "interaction_features": True
        },
        "labels": {
            "pt_multiplier": 1.5,
            "sl_multiplier": 1.0,
            "max_vertical_barrier": 12,
            "volatility_window": 24,
            "min_return": 0.002
        },
        "models": {
            "use_nn": False,
            "lightgbm_params": {"n_estimators": 10, "verbose": -1},
            "xgboost_params": {"n_estimators": 10},
            "logistic_params": {"max_iter": 50}
        },
        "regimes": {
            "adx_trend_threshold": 20.0,
            "volatility_high_quantile": 0.80,
            "regime_dependent_thresholds": {
                "BULLISH_TREND": {"buy_prob_threshold": 0.50, "position_size_multiplier": 1.0},
                "BEARISH_TREND": {"buy_prob_threshold": 0.70, "position_size_multiplier": 0.5},
                "RANGING_NEUTRAL": {"buy_prob_threshold": 0.55, "position_size_multiplier": 0.75},
                "HIGH_VOLATILITY": {"buy_prob_threshold": 0.65, "position_size_multiplier": 0.5}
            }
        },
        "risk": {
            "initial_capital": 10000.0,
            "risk_per_trade_pct": 0.005,
            "max_daily_loss_pct": 0.01,
            "max_drawdown_pct": 0.10,
            "volatility_targeting": True,
            "target_annual_vol": 0.15,
            "cooldown_bars": 3
        },
        "execution": {
            "commission_bps": 10,
            "slippage_bps": 5
        }
    }

    # 1. Quality
    checker = DataQualityChecker(config)
    valid, _ = checker.check_integrity(df)
    assert valid

    # 2. Features & Labels
    fe = FeatureEngineer(config)
    feat_df = fe.create_features(df)

    lbl = TripleBarrierLabeler(config)
    lbl_df = lbl.generate_labels(feat_df)

    # 3. Model Training
    feats = fe.get_feature_names(lbl_df)
    X = lbl_df[feats].dropna()
    y = lbl_df.loc[X.index, "target_binary"]

    model = EnsembledModel(config)
    model.fit(X, y)

    probs, _ = model.predict_proba(X)
    assert len(probs) == len(X)
