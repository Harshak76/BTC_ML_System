"""
Full System Pipeline Runner & Diagnostics Engine for V4.2 btc_ml_system.
Executes Part 1 (Equities V4.2 Optimization) and Part 2 (Crypto V4.2 Optimization).
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
from btc_ml_system.src.paper_trader import PaperTrader

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("btc_ml_system.v4_2_runner")


def run_single_pipeline(config_rel_path: str):
    config_path = Path(__file__).resolve().parent / config_rel_path
    with open(config_path) as f:
        config = yaml.safe_load(f)

    sym = config['asset']['symbol']
    asset_type = config['asset']['asset_type']
    strat_name = config['strategy']['name']

    # Data Ingestion
    years = config.get("data", {}).get("history_years", 2)
    days_back = years * 365
    provider = DataProvider(config)
    df_ltf = provider.fetch_data(symbol=sym, interval=config['asset']['base_timeframe'], days_back=days_back)
    df_htf = provider.fetch_data(symbol=sym, interval=config['asset']['htf_timeframe'], days_back=days_back * 2)

    # Volatility Regime
    vol_classifier = VolatilityRegimeClassifier(config)
    df_reg = vol_classifier.predict_regimes(df_ltf)

    # Strategy Evaluation
    strategy_engine = StrategyFactory.get_strategy(config)
    df_strat = strategy_engine.evaluate_signals(df_reg, df_htf)

    # Signal & Risk Check
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

    # Backtest
    backtester = Backtester(config)
    test_df = df_strat.iloc[50:].copy().reset_index(drop=True)
    equity_df, trades, metrics = backtester.run_backtest(test_df, signals)

    return sym, strat_name, metrics


def main():
    print("=" * 85)
    print("   BTC-ML-SYSTEM V4.2 OPTIMIZED MULTI-ASSET QUANTITATIVE PERFORMANCE AUDIT   ")
    print("=" * 85)

    # PART 1: US EQUITIES V4.2 OPTIMIZATION
    stocks = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]
    stock_configs = {
        "AAPL": "configs/aapl_v4.2.yaml",
        "MSFT": "configs/msft_v4.2.yaml",
        "NVDA": "configs/nvda_v4.2.yaml",
        "TSLA": "configs/tsla_v4.2.yaml",
        "AMZN": "configs/amzn_v4.2.yaml"
    }

    stock_results = {}
    print("\n[PART 1] Running V4.2 Optimized Trend Pullback Strategy across US Equities...")
    for sym in stocks:
        _, strat, m = run_single_pipeline(stock_configs[sym])
        stock_results[sym] = m
        print(f"  -> {sym:<6}: Return={m['total_return_pct']:>6.2f}%, WinRate={m['win_rate']:>6.2%}, MaxDD={m['max_drawdown_pct']:>5.2f}%, PF={m['profit_factor']:>4.2f}, Trades={m['total_trades']}")

    # PART 2: CRYPTO V4.2 OPTIMIZATION
    cryptos = ["ETHUSDT", "BTCUSDT"]
    crypto_configs = {
        "ETHUSDT": "configs/eth_v4.2.yaml",
        "BTCUSDT": "configs/btc_v4.2.yaml"
    }

    crypto_results = {}
    print("\n[PART 2] Running V4.2 Optimized Crypto Regime Momentum Strategy on Crypto...")
    for sym in cryptos:
        _, strat, m = run_single_pipeline(crypto_configs[sym])
        crypto_results[sym] = m
        print(f"  -> {sym:<8}: Return={m['total_return_pct']:>6.2f}%, WinRate={m['win_rate']:>6.2%}, MaxDD={m['max_drawdown_pct']:>5.2f}%, PF={m['profit_factor']:>4.2f}, Trades={m['total_trades']}")

    # PRINT COMPARISON TABLES
    print("\n" + "=" * 90)
    print("      PART 1: EQUITIES OPTIMIZED PERFORMANCE COMPARISON (V4.2)      ")
    print("=" * 90)
    print(f"  {'Stock Symbol':<14} | {'Total Trades':<13} | {'Win Rate':<12} | {'Total Return %':<16} | {'Max DD %':<10} | {'Profit Factor':<13}")
    print("-" * 90)
    for sym in stocks:
        m = stock_results[sym]
        print(f"  {sym:<14} | {m['total_trades']:<13} | {m['win_rate']:<12.2%} | {m['total_return_pct']:<16.2f}% | {m['max_drawdown_pct']:<10.2f}% | {m['profit_factor']:<13.2f}")
    print("=" * 90)

    print("\n" + "=" * 90)
    print("      PART 2: CRYPTO OPTIMIZED PERFORMANCE COMPARISON (V4.2)      ")
    print("=" * 90)
    print(f"  {'Crypto Symbol':<14} | {'Total Trades':<13} | {'Win Rate':<12} | {'Total Return %':<16} | {'Max DD %':<10} | {'Profit Factor':<13}")
    print("-" * 90)
    for sym in cryptos:
        m = crypto_results[sym]
        print(f"  {sym:<14} | {m['total_trades']:<13} | {m['win_rate']:<12.2%} | {m['total_return_pct']:<16.2f}% | {m['max_drawdown_pct']:<10.2f}% | {m['profit_factor']:<13.2f}")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    main()
