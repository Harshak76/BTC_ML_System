"""
Full System Pipeline Runner & Diagnostics Engine for V3 btc_ml_system.
Features:
- Step 1: Volatility Regime Classification (CALM, NORMAL, HIGH)
- Step 2: Directional Filter (Price > EMA50 and EMA50 sloping up)
- Step 3: Risk Engine (Kill Switch, 1% Daily Loss, 10% Drawdown, Cooldown)
- Step 4: Position Sizing (Risk 0.5% equity per trade)
- Event-Driven Backtest & Monte Carlo Robustness (1,000 paths)
- Alpaca Paper Trading Execution Safety
"""

import logging
import yaml
import pandas as pd
import numpy as np

from btc_ml_system.src.data_ingestion import DataIngestion
from btc_ml_system.src.data_quality import DataQualityChecker
from btc_ml_system.src.regimes import VolatilityRegimeClassifier
from btc_ml_system.src.direction import DirectionalFilter
from btc_ml_system.src.signal_engine import SignalEngine
from btc_ml_system.src.position_sizing import PositionSizer
from btc_ml_system.src.risk import RiskEngine
from btc_ml_system.src.backtester import Backtester
from btc_ml_system.src.alpaca_executor import AlpacaExecutor
from btc_ml_system.src.paper_trader import PaperTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("btc_ml_system.v3_runner")


def main():
    print("=" * 70)
    print("      BTC-ML-SYSTEM V3.0 VOLATILITY REGIME + DIRECTIONAL SYSTEM      ")
    print("=" * 70)

    # STEP 1: LOAD CONFIG V3
    config_path = "btc_ml_system/configs/btcusdt_v3.yaml"
    print(f"\n[STEP 1] Loading V3 configuration from {config_path}...")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    print("-> Config V3 loaded successfully.")

    # STEP 2: DATA INGESTION (2 YEARS)
    years = config.get("data", {}).get("history_years", 2)
    days_back = years * 365
    print(f"\n[STEP 2] Ingesting {years} Years (~{days_back * 24:,} candles) of market data from Binance Spot...")
    ingestion = DataIngestion(config)
    df_1h = ingestion.load_cached_or_fetch(symbol="BTCUSDT", interval="1h", days_back=days_back)
    print(f"-> Ingested 1h rows: {len(df_1h):,}")
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
    reg_counts = df_reg["volatility_regime"].value_counts().to_dict()
    fav_count = df_reg["vol_regime_favorable"].sum()
    print(f"-> Volatility Regime Distribution: {reg_counts}")
    print(f"-> Favorable Volatility Bars (CALM + NORMAL): {fav_count:,} / {len(df_reg):,} ({fav_count/len(df_reg):.1%})")

    # STEP 5: DIRECTIONAL FILTER EVALUATION
    print("\n[STEP 5] Evaluating Directional Filter (Price > EMA50 & EMA50 sloping up)...")
    dir_filter = DirectionalFilter(config)
    df_dir = dir_filter.evaluate_direction(df_reg)
    dir_valid_count = df_dir["direction_valid"].sum()
    print(f"-> Directionally Valid Bars: {dir_valid_count:,} / {len(df_dir):,} ({dir_valid_count/len(df_dir):.1%})")

    # STEP 6: SIGNAL ENGINE & POSITION SIZING EVALUATION
    print("\n[STEP 6] Running Sequential 3-Step Signal Engine & Position Sizing...")
    signal_engine = SignalEngine(config)
    signals = []
    rejection_reasons = {}

    current_equity = 10000.0
    atr_series = signal_engine.compute_atr(df_dir)
    df_dir["atr"] = atr_series

    for i in range(50, len(df_dir)):
        row = df_dir.iloc[i]
        timestamp = row["open_time"]
        entry_price = float(row["close"])
        vol_regime = str(row["volatility_regime"])
        is_vol_favorable = bool(row["vol_regime_favorable"])
        dir_valid = bool(row["direction_valid"])
        atr_val = float(row["atr"]) if not pd.isna(row["atr"]) else entry_price * 0.01

        sl_price = entry_price - (signal_engine.sl_atr_mult * atr_val)
        tp_price = entry_price + (signal_engine.tp_atr_mult * atr_val)

        from btc_ml_system.src.signal_engine import TradeSignal
        import uuid
        sig_id = str(uuid.uuid4())[:8]

        if not is_vol_favorable:
            reason = f"Blocked by Step 1: Volatility regime is {vol_regime} (only CALM/NORMAL allowed)"
            sig = TradeSignal(sig_id, timestamp, "BTCUSDT", "HOLD", entry_price, sl_price, tp_price, 0.0, 0.0, vol_regime, dir_valid, False, reason)
        elif not dir_valid:
            reason = "Blocked by Step 2: Directional filter failed (Requires Price > EMA50 & EMA50 sloping up)"
            sig = TradeSignal(sig_id, timestamp, "BTCUSDT", "HOLD", entry_price, sl_price, tp_price, 0.0, 0.0, vol_regime, False, False, reason)
        else:
            qty, pos_val, size_reason = signal_engine.position_sizer.calculate_position(current_equity, entry_price, sl_price)
            if qty <= 0:
                reason = f"Blocked by Position Sizing: {size_reason}"
                sig = TradeSignal(sig_id, timestamp, "BTCUSDT", "HOLD", entry_price, sl_price, tp_price, 0.0, 0.0, vol_regime, True, False, reason)
            else:
                sig = TradeSignal(sig_id, timestamp, "BTCUSDT", "BUY", entry_price, sl_price, tp_price, qty, pos_val, vol_regime, True, True, "Trade Approved")

        signals.append(sig)

        if not sig.allowed_trade:
            reason_key = sig.rejection_reason.split(":")[0]
            rejection_reasons[reason_key] = rejection_reasons.get(reason_key, 0) + 1

    approved_signals = [s for s in signals if s.allowed_trade]
    print(f"-> Evaluated Bars: {len(signals):,}")
    print(f"-> Approved BUY Signals: {len(approved_signals):,}")
    print("\n   [SIGNAL REJECTION REASON BREAKDOWN]")
    for reason, r_count in rejection_reasons.items():
        print(f"   - {reason:<60}: {r_count:,} bars")

    # STEP 7: EVENT-DRIVEN BACKTEST
    print("\n[STEP 7] Running Event-Driven Backtest (0.5% Equity Risk Per Trade, ATR SL/TP)...")
    backtester = Backtester(config)
    test_df = df_dir.iloc[50:].copy().reset_index(drop=True)
    equity_df, trades, metrics = backtester.run_backtest(test_df, signals)

    print("\n" + "=" * 55)
    print("      V3.0 BACKTEST PERFORMANCE SUMMARY      ")
    print("=" * 55)
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:<25}: {v:.2f}")
        else:
            print(f"  {k:<25}: {v}")

    # STEP 8: MONTE CARLO ROBUSTNESS SIMULATION
    print("\n[STEP 8] Running Monte Carlo Simulation (1,000 paths)...")
    mc_metrics = backtester.run_monte_carlo(trades, n_paths=1000)
    for k, v in mc_metrics.items():
        print(f"  {k:<25}: {v:.2f}")

    # STEP 9: ALPACA PAPER TRADING EXECUTION DEMO
    print("\n[STEP 9] Running Alpaca Paper Trading Execution Demo...")
    alpaca = AlpacaExecutor(config)
    equity = alpaca.get_account_equity()
    print(f"-> Connected to Alpaca Paper Trading API | Equity: ${equity:,.2f}")

    paper_trader = PaperTrader(config)
    tick_res = paper_trader.run_tick()
    print("\n   [LIVE TICK RESULT]")
    for k, v in tick_res.items():
        print(f"   - {k:<22}: {v}")

    print("\n" + "=" * 70)
    print("                V3.0 QUANTITATIVE VERDICT & STATUS                ")
    print("=" * 70)
    if metrics["total_trades"] > 0:
        print(f"  SUCCESS: Generated {metrics['total_trades']} disciplined trades risking 0.5% equity.")
        print(f"  Total Return: {metrics['total_return_pct']:.2f}% | Max Drawdown: {metrics['max_drawdown_pct']:.2f}% | Win Rate: {metrics['win_rate']:.2%}")
    else:
        print("  NOTICE: Risk & Volatility filters safely protected capital (0 trades).")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
