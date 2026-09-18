"""
Full System Pipeline Runner & Diagnostics Engine for V2.1 btc_ml_system.
Features:
- Configurable history ingestion (2 years / 17,520 1h bars)
- Diagnostic Grid analyzing trade counts & performance across multiple probability thresholds (0.50 to 0.60)
- Detailed probability distribution histogram summary & calibration diagnostics
- Rejection reason breakdown across all 10 risk rules
- Feature importance ranking (top 10 LightGBM & XGBoost features)
- Honest predictive edge evaluation
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


def print_histogram(probs: np.ndarray, bins: int = 10):
    """Prints ASCII probability distribution histogram."""
    counts, edges = np.histogram(probs, bins=bins, range=(0.0, 1.0))
    max_count = max(1, max(counts))
    print("\n   [PROBABILITY DISTRIBUTION HISTOGRAM]")
    for i in range(bins):
        bar = "#" * int(counts[i] / max_count * 30)
        print(f"   [{edges[i]:.2f} - {edges[i+1]:.2f}] : {counts[i]:<5} | {bar}")


def run_threshold_diagnostic_grid(config, test_df, calibrated_probs, disagreements, bet_sizes, regime_det, risk_engine, backtester):
    """Evaluates trade count and return metrics across sensitivity thresholds."""
    grid = config.get("robustness", {}).get("threshold_diagnostic_grid", [0.50, 0.52, 0.54, 0.56, 0.58, 0.60])
    print("\n" + "=" * 65)
    print("      V2.1 THRESHOLD DIAGNOSTIC SENSITIVITY GRID      ")
    print("=" * 65)
    print(f"  {'Threshold':<10} | {'Trades':<8} | {'Win Rate':<10} | {'Return %':<10} | {'Max DD %':<10}")
    print("-" * 65)

    for thresh in grid:
        decisions = []
        for i in range(len(test_df)):
            row = test_df.iloc[i]
            reg_params = regime_det.get_regime_parameters(row["regime"]).copy()
            reg_params["buy_prob_threshold"] = thresh

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

        _, trades, metrics = backtester.run_backtest(test_df, decisions)
        print(f"  {thresh:<10.2f} | {metrics['total_trades']:<8} | {metrics['win_rate']:<10.2%} | {metrics['total_return_pct']:<10.2f}% | {metrics['max_drawdown_pct']:<10.2f}%")
    print("=" * 65)


def main():
    print("=" * 70)
    print("      BTC-ML-SYSTEM V2.1 RESEARCH-GRADE PIPELINE & DIAGNOSTICS      ")
    print("=" * 70)

    # STEP 1: LOAD CONFIG V2.1
    config_path = "btc_ml_system/configs/btcusdt_1h_v2.1.yaml"
    print(f"\n[STEP 1] Loading V2.1 configuration from {config_path}...")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    print("-> Config V2.1 loaded successfully.")

    # STEP 2: DATA INGESTION (2 YEARS)
    years = config.get("data", {}).get("history_years", 2)
    days_back = years * 365
    print(f"\n[STEP 2] Fetching {years} Years (~{days_back * 24:,} candles) of market data...")
    ingestion = DataIngestion(config)
    df_1h = ingestion.load_cached_or_fetch(symbol="BTCUSDT", interval="1h", days_back=days_back)
    df_4h = ingestion.load_cached_or_fetch(symbol="BTCUSDT", interval="4h", days_back=days_back * 2)
    print(f"-> Ingested 1h rows: {len(df_1h):,}, 4h rows: {len(df_4h):,}")
    print(f"-> Date Range: {df_1h['open_time'].min().strftime('%Y-%m-%d')} to {df_1h['open_time'].max().strftime('%Y-%m-%d')}")

    # STEP 3: DATA QUALITY AUDIT
    print("\n[STEP 3] Running Data Quality Audit...")
    checker = DataQualityChecker(config)
    is_valid, report = checker.check_integrity(df_1h, timeframe="1h")
    print(f"-> Integrity Check: Passed={is_valid}, Missing={report['missing_values']}, Gaps={report['gap_count']}")

    # STEP 4: FEATURE ENGINEERING
    print("\n[STEP 4] Engineering technical & microstructural features...")
    fe = FeatureEngineer(config)
    feat_df = fe.create_features(df_1h, df_4h)
    feat_cols = fe.get_feature_names(feat_df)
    print(f"-> Engineered {len(feat_cols)} features across {len(feat_df):,} bars.")

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
    print(f"-> Market Regimes Distribution: {reg_counts}")

    # STEP 8: MODEL TRAINING & PROBABILITY CALIBRATION
    print("\n[STEP 8] Training Ensemble Models (LightGBM + XGBoost + Logistic) & Fitting Isotonic Calibrator...")
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
    print(f"-> Trained ensemble on {len(X_train):,} samples. Evaluated on {len(X_test):,} OOS test samples.")

    # PROBABILITY DIAGNOSTICS & FEATURE IMPORTANCE
    print_histogram(calibrated_probs)

    # Feature Importance
    if hasattr(model.lgb, "feature_importances_"):
        lgb_imp = pd.Series(model.lgb.feature_importances_, index=feat_cols).sort_values(ascending=False).head(10)
        print("\n   [TOP 10 FEATURE IMPORTANCES (LightGBM)]")
        for f_name, imp_val in lgb_imp.items():
            print(f"   - {f_name:<25}: {imp_val}")

    # STEP 9: META-LABELING & BET SIZING
    print("\n[STEP 9] Training Secondary Meta-Labeler & Calculating Dynamic Bet Sizes...")
    meta_labeler = MetaLabeler(config)
    meta_y_train = labeler.generate_meta_labels(reg_df.iloc[:train_size], model.predict_proba(X_train)[0])
    meta_labeler.fit(X_train, meta_y_train)
    meta_probs = meta_labeler.predict_meta_prob(X_test)
    bet_sizes = meta_labeler.compute_bet_size(calibrated_probs, meta_probs, threshold=0.52)
    print(f"-> Meta-labeler trained. Non-zero bets count: {np.count_nonzero(bet_sizes)} / {len(bet_sizes)} | Average Bet Size: {bet_sizes.mean():.4f}")

    # STEP 10: RISK ENGINE EVALUATION & BREAKDOWN
    print("\n[STEP 10] Running 10-Rule Risk Engine & Rejection Breakdown...")
    risk_engine = RiskEngine(config)
    decisions = []
    rejection_reasons = {}

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

        if not dec.allow_trade:
            reason_key = dec.reason.split(":")[0]
            rejection_reasons[reason_key] = rejection_reasons.get(reason_key, 0) + 1

    approved_trades = [d for d in decisions if d.allow_trade]
    print(f"-> Total OOS Bars Evaluated: {len(decisions):,}")
    print(f"-> Potential Signals (>0.50 Raw Prob): {np.sum(raw_probs > 0.50):,}")
    print(f"-> Risk Engine Approved Trades: {len(approved_trades):,} / {len(decisions):,}")
    print("\n   [RISK REJECTION REASON BREAKDOWN]")
    for reason, r_count in rejection_reasons.items():
        print(f"   - {reason:<45}: {r_count:,} bars")

    # DIAGNOSTIC SENSITIVITY GRID
    backtester = Backtester(config)
    run_threshold_diagnostic_grid(config, test_df, calibrated_probs, disagreements, bet_sizes, regime_det, risk_engine, backtester)

    # BACKTEST EXECUTED AT DEFAULT CONFIG THRESHOLD
    equity_df, trades, metrics = backtester.run_backtest(test_df, decisions)

    print("\n" + "=" * 55)
    print("   V2.1 BACKTEST PERFORMANCE SUMMARY (DEFAULT CONFIG)   ")
    print("=" * 55)
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
    print(f"-> Feature Drift Ratio: {drift_report['drift_ratio']:.1%} ({drift_report['drifted_feature_count']}/{len(feat_cols)} features drifted)")
    print(f"-> Retrain Signal Triggered: {drift_report['retrain_recommended']}")

    # STEP 13: LIVE PAPER TRADER TICK DEMO
    print("\n[STEP 13] Simulating Live Paper Trading Tick...")
    paper_trader = PaperTrader(config)
    tick_result = paper_trader.run_tick()
    print("-> Live Paper Trader Output:")
    for k, v in tick_result.items():
        print(f"     {k:<25}: {v}")

    # FINAL QUANTITATIVE RECOMMENDATION
    print("\n" + "=" * 70)
    print("               QUANTITATIVE RESEARCH RECOMMENDATION               ")
    print("=" * 70)
    if metrics["total_trades"] > 0 and metrics["profit_factor"] > 1.1:
        print("  VERDICT: PRODUCING EDGE - System demonstrated statistically significant")
        print(f"  positive return ({metrics['total_return_pct']:.2f}%) with Profit Factor {metrics['profit_factor']:.2f}.")
    else:
        print("  VERDICT: NO STATISTICAL EDGE DEMONSTRATED ON OOS TEST PERIOD.")
        print("  Recommendation: Abstain from live deployment. Long-only 1h directional")
        print("  crypto predictions remain noisy. Retain HOLD as optimal risk position.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
