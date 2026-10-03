"""
Full System Pipeline Runner & Diagnostics Engine for V3.4 btc_ml_system.
Ultra-Strict Market Structure Breakout + Light Machine Learning Meta-Labeler Strategy.
"""

import os
import sys
import logging
from pathlib import Path
import yaml
import pandas as pd
import numpy as np

# Add workspace root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from btc_ml_system.src.data_ingestion import DataIngestion
from btc_ml_system.src.data_quality import DataQualityChecker
from btc_ml_system.src.regimes import VolatilityRegimeClassifier
from btc_ml_system.src.direction import DirectionalFilter
from btc_ml_system.src.signal_engine import SignalEngine, TradeSignal
from btc_ml_system.src.position_sizing import PositionSizer
from btc_ml_system.src.risk import RiskEngine
from btc_ml_system.src.backtester import Backtester
from btc_ml_system.src.meta_labeler import MetaLabeler
from btc_ml_system.src.alpaca_executor import AlpacaExecutor
from btc_ml_system.src.paper_trader import PaperTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("btc_ml_system.v3_4_runner")


def main():
    print("=" * 75)
    print("   BTC-ML-SYSTEM V3.4 ULTRA-STRICT BREAKOUT + ML META-LABELER SYSTEM   ")
    print("=" * 75)

    # STEP 1: LOAD CONFIG V3.4
    config_path = Path(__file__).resolve().parent / "configs" / "btcusdt_v3.4.yaml"
    print(f"\n[STEP 1] Loading V3.4 configuration from {config_path}...")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    print(f"-> Config V3.4 loaded: {config['system']['name']} v{config['system']['version']}")

    # STEP 2: DATA INGESTION (2 YEARS 1H + 4H)
    years = config.get("data", {}).get("history_years", 2)
    days_back = years * 365
    print(f"\n[STEP 2] Ingesting {years} Years (~{days_back * 24:,} 1h candles) from Binance Spot...")
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

    # STEP 4: VOLATILITY REGIME CLASSIFICATION
    print("\n[STEP 4] Classifying Volatility Regimes (CALM / NORMAL / HIGH)...")
    vol_classifier = VolatilityRegimeClassifier(config)
    df_reg = vol_classifier.predict_regimes(df_1h)

    # STEP 5: DIRECTIONAL FILTER & 4H HTF CONFIRMATION
    print("\n[STEP 5] Evaluating Ultra-Strict Breakout (20-bar High + 0.4% Buffer + Bullish Body + 1.35x Vol + 1h EMA20>EMA50) & 4h HTF Confirmation...")
    dir_filter = DirectionalFilter(config)
    df_dir = dir_filter.evaluate_direction(df_reg, df_4h)

    # STEP 6: BASELINE V3.3 SIGNAL ENGINE EVALUATION
    print("\n[STEP 6] Extracting Baseline V3.3 Candidate Entry Signals...")
    signal_engine = SignalEngine(config)
    signals = []

    current_equity = 10000.0
    atr_series = signal_engine.compute_atr(df_dir)
    df_dir["atr"] = atr_series

    risk_engine = RiskEngine(config)

    for i in range(50, len(df_dir)):
        row = df_dir.iloc[i]
        timestamp = row["open_time"]
        entry_price = float(row["close"])
        vol_regime = str(row["volatility_regime"])
        is_vol_favorable = bool(row["vol_regime_favorable"])
        dir_valid = bool(row["direction_valid"])
        htf_valid = bool(row.get("htf_trend_valid", True))
        atr_val = float(row["atr"]) if not pd.isna(row["atr"]) else entry_price * 0.01

        sl_price = entry_price - (signal_engine.sl_atr_mult * atr_val)
        tp_price = entry_price + (signal_engine.tp_atr_mult * atr_val)

        import uuid
        sig_id = str(uuid.uuid4())[:8]

        if is_vol_favorable and htf_valid and dir_valid:
            risk_passed, _ = risk_engine.evaluate_risk(i, 0.0, 0.0)
            if risk_passed:
                qty, pos_val, _ = signal_engine.position_sizer.calculate_position(current_equity, entry_price, sl_price)
                if qty > 0:
                    risk_engine.last_trade_bar = i
                    sig = TradeSignal(sig_id, timestamp, "BTCUSDT", "BUY", entry_price, sl_price, tp_price, qty, pos_val, vol_regime, True, True, True, "Trade Approved")
                    signals.append(sig)
                    continue

        sig = TradeSignal(sig_id, timestamp, "BTCUSDT", "HOLD", entry_price, sl_price, tp_price, 0.0, 0.0, vol_regime, dir_valid, htf_valid, False, "Not Approved")
        signals.append(sig)

    approved_v33 = [s for s in signals if s.allowed_trade]
    print(f"-> Baseline V3.3 Candidate Trades: {len(approved_v33)}")

    # STEP 7: FIRST PASS BACKTEST TO GENERATE TRADE OUTCOMES FOR ML
    backtester = Backtester(config)
    test_df = df_dir.iloc[50:].copy().reset_index(drop=True)
    _, initial_trades, v33_metrics = backtester.run_backtest(test_df, signals)

    print(f"-> V3.3 Baseline Return: {v33_metrics['total_return_pct']:.2f}% | Trades: {v33_metrics['total_trades']} | PF: {v33_metrics['profit_factor']:.2f}")

    # STEP 8: APPLY LIGHT MACHINE LEARNING META-LABELER
    print("\n[STEP 8] Fitting Light ML Meta-Labeler (Logistic Regression / LightGBM) on Signal Features...")
    meta_labeler = MetaLabeler(config)
    v34_signals, meta_stats = meta_labeler.fit_predict_signals(df_dir, signals, initial_trades)
    
    approved_v34 = [s for s in v34_signals if s.allowed_trade]
    print(f"-> Meta-Labeler Stats: {meta_stats}")
    print(f"-> Retained V3.4 Approved Signals: {len(approved_v34)}")

    # STEP 9: FINAL V3.4 BACKTEST WITH META-LABELING FILTER
    print("\n[STEP 9] Running Final Event-Driven Backtest for V3.4 Meta-Labeled Strategy...")
    equity_df, final_trades, v34_metrics = backtester.run_backtest(test_df, v34_signals)

    print("\n" + "=" * 60)
    print("      V3.4 BACKTEST PERFORMANCE SUMMARY      ")
    print("=" * 60)
    for k, v in v34_metrics.items():
        if isinstance(v, float):
            print(f"  {k:<25}: {v:.2f}")
        else:
            print(f"  {k:<25}: {v}")

    # COMPARISON WITH V3.3
    v33_comparison = {
        "total_trades": v33_metrics.get("total_trades", 79),
        "win_rate": v33_metrics.get("win_rate", 0.4051),
        "total_return_pct": v33_metrics.get("total_return_pct", -4.14),
        "max_drawdown_pct": v33_metrics.get("max_drawdown_pct", 5.43),
        "profit_factor": v33_metrics.get("profit_factor", 0.82)
    }

    print("\n" + "=" * 65)
    print("         V3.3 vs V3.4 STRATEGY COMPARISON         ")
    print("=" * 65)
    print(f"  {'Metric':<25} | {'V3.3 (Ultra-Strict)':<15} | {'V3.4 (Meta-Labeled)':<15}")
    print("-" * 65)
    print(f"  {'Total Trades':<25} | {v33_comparison['total_trades']:<15} | {v34_metrics['total_trades']:<15}")
    print(f"  {'Win Rate':<25} | {v33_comparison['win_rate']:.2%}           | {v34_metrics['win_rate']:.2%}")
    print(f"  {'Total Return %':<25} | {v33_comparison['total_return_pct']:.2f}%          | {v34_metrics['total_return_pct']:.2f}%")
    print(f"  {'Max Drawdown %':<25} | {v33_comparison['max_drawdown_pct']:.2f}%          | {v34_metrics['max_drawdown_pct']:.2f}%")
    print(f"  {'Profit Factor':<25} | {v33_comparison['profit_factor']:.2f}           | {v34_metrics['profit_factor']:.2f}")
    print("=" * 65)

    # STEP 10: ALPACA PAPER TRADING EXECUTION DEMO
    print("\n[STEP 10] Running Alpaca Paper Trading Execution Demo...")
    paper_trader = PaperTrader(config)
    tick_res = paper_trader.run_tick()
    print("\n   [LIVE TICK RESULT]")
    for k, v in tick_res.items():
        print(f"   - {k:<22}: {v}")

    print("\n" + "=" * 75)
    print("                V3.4 QUANTITATIVE VERDICT & FINAL AUDIT                ")
    print("=" * 75)
    if v34_metrics["total_return_pct"] > 0 and v34_metrics["profit_factor"] > 1.0:
        print(f"  PROFITABLE EDGE DEMONSTRATED! Total Return: {v34_metrics['total_return_pct']:.2f}%, Profit Factor: {v34_metrics['profit_factor']:.2f} across {v34_metrics['total_trades']} trades.")
    else:
        print(f"  HONEST QUANTITATIVE AUDIT: Total Return {v34_metrics['total_return_pct']:.2f}%, Max DD {v34_metrics['max_drawdown_pct']:.2f}%, Profit Factor {v34_metrics['profit_factor']:.2f}.")
        print(f"  FINAL VERDICT: Meta-labeling on 1h BTC price breakouts alone failed to produce a positive statistical edge (PF < 1.0).")
        print(f"  RECOMMENDATION: Pivot to Version 4 (Multi-Factor Machine Learning / Cross-Asset Regime Architecture).")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    main()
