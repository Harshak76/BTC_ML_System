"""
Full System Pipeline Runner & Diagnostics Engine for V4.0 btc_ml_system.
Multi-Asset (Crypto & Stocks) Quantitative Trading System supporting modular plug-and-play strategies.
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

from btc_ml_system.src.data_provider import DataProvider
from btc_ml_system.src.data_quality import DataQualityChecker
from btc_ml_system.src.regimes import VolatilityRegimeClassifier
from btc_ml_system.src.strategies import StrategyFactory
from btc_ml_system.src.signal_engine import SignalEngine, TradeSignal
from btc_ml_system.src.position_sizing import PositionSizer
from btc_ml_system.src.risk import RiskEngine
from btc_ml_system.src.backtester import Backtester
from btc_ml_system.src.alpaca_executor import AlpacaExecutor
from btc_ml_system.src.paper_trader import PaperTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("btc_ml_system.v4_0_runner")


def run_pipeline(config_rel_path: str):
    config_path = Path(__file__).resolve().parent / config_rel_path
    print("\n" + "=" * 75)
    print(f"   BTC-ML-SYSTEM V4.0 MULTI-ASSET TRADING SYSTEM ({config_path.name})   ")
    print("=" * 75)

    # STEP 1: LOAD CONFIG
    print(f"\n[STEP 1] Loading V4.0 Configuration from {config_path.name}...")
    with open(config_path) as f:
        config = yaml.safe_load(f)

    sys_name = config['system']['name']
    sym = config['asset']['symbol']
    asset_type = config['asset']['asset_type']
    strat_name = config['strategy']['name']
    print(f"-> Active Asset: {sym} ({asset_type.upper()}) | Provider: {config['asset']['data_provider']}")
    print(f"-> Active Strategy: '{strat_name}'")

    # STEP 2: MULTI-ASSET DATA INGESTION
    years = config.get("data", {}).get("history_years", 2)
    days_back = years * 365
    print(f"\n[STEP 2] Fetching Multi-Asset Historical Data via DataProvider...")
    provider = DataProvider(config)
    df_ltf = provider.fetch_data(symbol=sym, interval=config['asset']['base_timeframe'], days_back=days_back)
    df_htf = provider.fetch_data(symbol=sym, interval=config['asset']['htf_timeframe'], days_back=days_back * 2)

    print(f"-> Ingested LTF ({config['asset']['base_timeframe']}) rows: {len(df_ltf):,}, HTF ({config['asset']['htf_timeframe']}) rows: {len(df_htf):,}")
    print(f"-> Date Range: {df_ltf['open_time'].min().strftime('%Y-%m-%d')} to {df_ltf['open_time'].max().strftime('%Y-%m-%d')}")

    # STEP 3: DATA QUALITY AUDIT
    print("\n[STEP 3] Running Data Quality Audit...")
    checker = DataQualityChecker(config)
    is_valid, report = checker.check_integrity(df_ltf, timeframe=config['asset']['base_timeframe'])
    print(f"-> Integrity Check: Passed={is_valid}, Missing={report['missing_values']}, Gaps={report['gap_count']}")

    # STEP 4: VOLATILITY REGIME CLASSIFICATION
    print("\n[STEP 4] Classifying Volatility Regimes (CALM / NORMAL / HIGH)...")
    vol_classifier = VolatilityRegimeClassifier(config)
    df_reg = vol_classifier.predict_regimes(df_ltf)
    reg_counts = df_reg["volatility_regime"].value_counts().to_dict()
    print(f"-> Volatility Regime Breakdown: {reg_counts}")

    # STEP 5: EVALUATE MODULAR STRATEGY MODULE
    print(f"\n[STEP 5] Evaluating Modular Strategy Engine ('{strat_name}')...")
    strategy_engine = StrategyFactory.get_strategy(config)
    df_strat = strategy_engine.evaluate_signals(df_reg, df_htf)
    valid_signals_count = df_strat["direction_valid"].sum()
    htf_valid_count = df_strat["htf_trend_valid"].sum()
    print(f"-> HTF Trend Bullish Bars: {htf_valid_count:,} / {len(df_strat):,} ({htf_valid_count/len(df_strat):.1%})")
    print(f"-> Valid '{strat_name}' Entry Signals: {valid_signals_count:,} / {len(df_strat):,} ({valid_signals_count/len(df_strat):.1%})")

    # STEP 6: SIGNAL ENGINE & RISK ENGINE VERIFICATION
    print("\n[STEP 6] Running Entry Signal Engine & Risk Engine Checks...")
    signal_engine = SignalEngine(config)
    signals = []

    current_equity = config.get("risk_engine", {}).get("initial_capital", 10000.0)
    atr_series = signal_engine.compute_atr(df_strat)
    df_strat["atr"] = atr_series

    risk_engine = RiskEngine(config)

    for i in range(50, len(df_strat)):
        row = df_strat.iloc[i]
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
                    sig = TradeSignal(sig_id, timestamp, sym, "BUY", entry_price, sl_price, tp_price, qty, pos_val, vol_regime, True, True, True, "Trade Approved")
                    signals.append(sig)
                    continue

        sig = TradeSignal(sig_id, timestamp, sym, "HOLD", entry_price, sl_price, tp_price, 0.0, 0.0, vol_regime, dir_valid, htf_valid, False, "Not Approved")
        signals.append(sig)

    approved_signals = [s for s in signals if s.allowed_trade]
    print(f"-> Approved BUY Signals: {len(approved_signals):,}")

    # STEP 7: EVENT-DRIVEN BACKTEST
    print("\n[STEP 7] Running Event-Driven Backtest...")
    backtester = Backtester(config)
    test_df = df_strat.iloc[50:].copy().reset_index(drop=True)
    equity_df, trades, metrics = backtester.run_backtest(test_df, signals)

    print("\n" + "=" * 60)
    print(f"      V4.0 BACKTEST SUMMARY ({sym} - {strat_name.upper()})      ")
    print("=" * 60)
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:<25}: {v:.2f}")
        else:
            print(f"  {k:<25}: {v}")

    # STEP 8: ALPACA EXECUTION VERIFICATION
    print("\n[STEP 8] Running Alpaca Paper Trading Execution Demo...")
    paper_trader = PaperTrader(config)
    tick_res = paper_trader.run_tick()
    print("\n   [LIVE TICK RESULT]")
    for k, v in tick_res.items():
        print(f"   - {k:<22}: {v}")

    return sym, metrics


def main():
    # Run pipeline for Crypto (BTCUSDT)
    btc_sym, btc_metrics = run_pipeline("configs/default_v4.yaml")

    # Run pipeline for Equities (AAPL)
    aapl_sym, aapl_metrics = run_pipeline("configs/aapl_v4.yaml")

    # Run pipeline for Equities (TSLA)
    tsla_sym, tsla_metrics = run_pipeline("configs/tsla_v4.yaml")

    print("\n" + "=" * 85)
    print("         V4.0 MULTI-ASSET QUANTITATIVE PERFORMANCE SUMMARY         ")
    print("=" * 85)
    print(f"  {'Metric':<25} | {'BTCUSDT (Crypto)':<16} | {'AAPL (Equity)':<16} | {'TSLA (Equity)':<16}")
    print("-" * 85)
    print(f"  {'Total Trades':<25} | {btc_metrics['total_trades']:<16} | {aapl_metrics['total_trades']:<16} | {tsla_metrics['total_trades']:<16}")
    print(f"  {'Win Rate':<25} | {btc_metrics['win_rate']:.2%}           | {aapl_metrics['win_rate']:.2%}           | {tsla_metrics['win_rate']:.2%}")
    print(f"  {'Total Return %':<25} | {btc_metrics['total_return_pct']:.2f}%          | {aapl_metrics['total_return_pct']:.2f}%          | {tsla_metrics['total_return_pct']:.2f}%")
    print(f"  {'Max Drawdown %':<25} | {btc_metrics['max_drawdown_pct']:.2f}%          | {aapl_metrics['max_drawdown_pct']:.2f}%          | {tsla_metrics['max_drawdown_pct']:.2f}%")
    print(f"  {'Profit Factor':<25} | {btc_metrics['profit_factor']:.2f}           | {aapl_metrics['profit_factor']:.2f}           | {tsla_metrics['profit_factor']:.2f}")
    print("=" * 85 + "\n")


if __name__ == "__main__":
    main()
