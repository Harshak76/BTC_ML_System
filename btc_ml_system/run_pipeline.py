"""
Full System Pipeline Runner for V2 btc_ml_system.
Runs end-to-end data ingestion, features, triple-barrier labeling,
purged walk-forward splits, ensemble training, isotonic calibration,
meta-labeling, risk engine filtering, backtesting, Monte Carlo, and live tick simulation.
"""

import logging
import yaml
import pandas as pd
import numpy as np

from btc_ml_system.src.data_ingestion import DataIngestion
from btc_ml_system.src.data_quality import DataQualityChecker
from btc_ml_system.src.features import FeatureEngineer
from btc_ml_system.src.labels import TripleBarrierLabeler
from btc_ml_system.src.meta_labeling import MetaLabeler
from btc_ml_system.src.splits import DataSplitter
from btc_ml_system.src.regimes import RegimeDetector
from btc_ml_system.src.models import EnsembledModel
from btc_ml_system.src.calibration import ProbabilityCalibrator
from btc_ml_system.src.risk import RiskEngine
from btc_ml_system.src.backtester import Backtester
from btc_ml_system.src.monitoring import ModelMonitor
from btc_ml_system.src.paper_trader import PaperTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("btc_ml_system.runner")


def main():
    print("=" * 60)
    print("      BTC-ML-SYSTEM V2.0 END-TO-END PIPELINE RUNNER      ")
    print("=" * 60)

    # STEP 1: LOAD CONFIG
    print("\n[STEP 1] Loading system configuration...")
    with open("btc_ml_system/configs/btcusdt_1h_v2.yaml") as f:
        config = yaml.safe_load(f)
    print("-> Config loaded successfully.")

    # STEP 2: DATA INGESTION
    print("\n[STEP 2] Fetching market data...")
    ingestion = DataIngestion(config)
    df_1h = ingestion.load_cached_or_fetch(symbol="BTCUSDT", interval="1h", days_back=30)
    df_4h = ingestion.load_cached_or_fetch(symbol="BTCUSDT", interval="4h", days_back=60)
    print(f"-> Ingested 1h rows: {len(df_1h)}, 4h rows: {len(df_4h)}")

    # STEP 3: DATA QUALITY AUDIT
    print("\n[STEP 3] Running Data Quality Audit...")
    checker = DataQualityChecker(config)
    is_valid, report = checker.check_integrity(df_1h, timeframe="1h")
    print(f"-> Quality Check: Passed={is_valid}, Missing={report['missing_values']}, Gaps={report['gap_count']}")

    # STEP 4: FEATURE ENGINEERING
    print("\n[STEP 4] Engineering technical & microstructural features...")
    fe = FeatureEngineer(config)
    feat_df = fe.create_features(df_1h, df_4h)
    feat_cols = fe.get_feature_names(feat_df)
    print(f"-> Engineered {len(feat_cols)} features for {len(feat_df)} rows.")

    # STEP 5: TRIPLE-BARRIER LABELING & SAMPLE WEIGHTING
    print("\n[STEP 5] Generating Triple-Barrier Labels & Sample Weights...")
    labeler = TripleBarrierLabeler(config)
    lbl_df = labeler.generate_labels(feat_df)
    counts = lbl_df["target"].value_counts().to_dict()
    print(f"-> Target distribution (+1 PT, -1 SL, 0 Exit): {counts}")

    # STEP 6: TRAIN/VAL/TEST PURGED SPLITS
    print("\n[STEP 6] Generating Purged Walk-Forward & CPCV Splits...")
    splitter = DataSplitter(config)
    splits = list(splitter.purged_walk_forward_splits(lbl_df))
    print(f"-> Generated {len(splits)} purged walk-forward cross-validation splits.")

    # STEP 7: REGIME DETECTION
    print("\n[STEP 7] Detecting Market Regimes...")
    regime_det = RegimeDetector(config)
    reg_df = regime_det.detect_regimes(lbl_df)
    reg_counts = reg_df["regime"].value_counts().to_dict()
    print(f"-> Market Regimes Detected: {reg_counts}")

    # STEP 8: MODEL TRAINING & PROBABILITY CALIBRATION
    print("\n[STEP 8] Training Ensemble Models & Fitting Isotonic Calibrator...")
    X = reg_df[feat_cols].dropna()
    y = reg_df.loc[X.index, "target_binary"]
    sample_weights = reg_df.loc[X.index, "sample_weight"]

    train_size = int(len(X) * 0.7)
    X_train, X_test = X.iloc[:train_size], X.iloc[train_size:]
    y_train, y_test = y.iloc[:train_size], y.iloc[train_size:]
    w_train = sample_weights.iloc[:train_size]

    model = EnsembledModel(config)
    model.fit(X_train, y_train, sample_weight=w_train)
    raw_probs, model_dict = model.predict_proba(X_test)
    disagreements = model.calculate_disagreement(model_dict)

    calibrator = ProbabilityCalibrator(config)
    calibrator.fit(raw_probs, y_test.values)
    calibrated_probs = calibrator.calibrate(raw_probs)
    print(f"-> Trained ensemble on {len(X_train)} samples. Evaluated on {len(X_test)} OOS test samples.")

    # STEP 9: META-LABELING & BET SIZING
    print("\n[STEP 9] Training Secondary Meta-Labeler & Calculating Dynamic Bet Sizes...")
    meta_labeler = MetaLabeler(config)
    meta_y_train = labeler.generate_meta_labels(reg_df.iloc[:train_size], model.predict_proba(X_train)[0])
    meta_labeler.fit(X_train, meta_y_train)
    meta_probs = meta_labeler.predict_meta_prob(X_test)
    bet_sizes = meta_labeler.compute_bet_size(calibrated_probs, meta_probs)
    print(f"-> Meta-labeler trained. Average OOS bet size: {bet_sizes.mean():.4f}")

    # STEP 10: RISK ENGINE EVALUATION & EVENT-DRIVEN BACKTEST
    print("\n[STEP 10] Running 10-Rule Risk Engine & Event-Driven Backtest...")
    risk_engine = RiskEngine(config)
    decisions = []

    test_df = reg_df.loc[X_test.index].copy()
    for i in range(len(test_df)):
        row = test_df.iloc[i]
        reg_params = regime_det.get_regime_parameters(row["regime"])
        dec = risk_engine.evaluate_trade(
            current_bar_idx=i,
            buy_prob=calibrated_probs[i],
            disagreement=disagreements[i],
            regime_params=reg_params,
            current_volatility=row.get("vol_24h", 0.01),
            current_drawdown=0.0,
            daily_pnl_pct=0.0,
            meta_bet_size=bet_sizes[i]
        )
        decisions.append(dec)

    approved_trades = [d for d in decisions if d.allow_trade]
    print(f"-> Risk Engine Approved Trades: {len(approved_trades)} / {len(decisions)} bars")

    backtester = Backtester(config)
    equity_df, trades, metrics = backtester.run_backtest(test_df, decisions)

    print("\n" + "=" * 45)
    print("       BACKTEST PERFORMANCE SUMMARY       ")
    print("=" * 45)
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:<25}: {v:.2f}")
        else:
            print(f"  {k:<25}: {v}")

    # STEP 11: MONTE CARLO ROBUSTNESS
    print("\n[STEP 11] Running Monte Carlo Simulation (500 paths)...")
    mc_metrics = backtester.run_monte_carlo(trades, n_paths=500)
    for k, v in mc_metrics.items():
        print(f"  {k:<25}: {v:.2f}")

    # STEP 12: DRIFT MONITORING
    print("\n[STEP 12] Performing Data & Feature Drift Audit...")
    monitor = ModelMonitor(config)
    drift_report = monitor.check_feature_drift(X_train, X_test, feat_cols)
    print(f"-> Feature Drift Ratio: {drift_report['drift_ratio']:.1%} | Retrain Recommended: {drift_report['retrain_recommended']}")

    # STEP 13: LIVE PAPER TRADER TICK DEMO
    print("\n[STEP 13] Simulating Live Paper Trading Tick...")
    paper_trader = PaperTrader(config)
    tick_result = paper_trader.run_tick()
    print("-> Live Paper Trader Output:")
    for k, v in tick_result.items():
        print(f"     {k:<25}: {v}")

    print("\n" + "=" * 60)
    print("         END-TO-END PIPELINE EXECUTION COMPLETED          ")
    print("=" * 60)


if __name__ == "__main__":
    main()
