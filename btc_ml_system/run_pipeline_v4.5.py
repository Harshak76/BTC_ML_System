"""
Full System Pipeline Runner & Diagnostics Engine for V4.5 btc_ml_system.
Executes Task 1 (Frozen Equity V4.3 Baseline), Task 2 (Final BTC 4h Push), and Task 3 (Final ETH 1h Push).
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
from btc_ml_system.src.direction import SessionFilter
from btc_ml_system.src.strategies import StrategyFactory
from btc_ml_system.src.signal_engine import SignalEngine, TradeSignal
from btc_ml_system.src.position_sizing import PositionSizer
from btc_ml_system.src.risk import RiskEngine
from btc_ml_system.src.backtester import Backtester

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("btc_ml_system.v4_5_runner")


def run_single_pipeline(config_rel_path: str, override_config: dict = None):
    config_path = Path(__file__).resolve().parent / config_rel_path
    with open(config_path) as f:
        config = yaml.safe_load(f)

    if override_config:
        def deep_update(d, u):
            for k, v in u.items():
                if isinstance(v, dict):
                    d[k] = deep_update(d.get(k, {}), v)
                else:
                    d[k] = v
            return d
        deep_update(config, override_config)

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

    # Session Filter
    session_filter = SessionFilter(config)
    df_sess = session_filter.apply_filter(df_reg)

    # Strategy Evaluation
    strategy_engine = StrategyFactory.get_strategy(config)
    df_strat = strategy_engine.evaluate_signals(df_sess, df_htf)

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
        is_session_valid = bool(row.get("session_valid", True))
        dir_valid = bool(row["direction_valid"])
        htf_valid = bool(row.get("htf_trend_valid", True))
        atr_val = float(row["atr"]) if not pd.isna(row["atr"]) else entry_price * 0.01

        sl_price = entry_price - (signal_engine.sl_atr_mult * atr_val)
        tp_price = entry_price + (signal_engine.tp_atr_mult * atr_val)

        import uuid
        sig_id = str(uuid.uuid4())[:8]

        rejection_reason = None
        if not is_vol_favorable:
            rejection_reason = f"Blocked by Volatility Regime Filter: Current regime is '{vol_regime}' (allowed: {vol_classifier.allowed_regimes})"
            logger.info(f"Signal [{sig_id}] REJECTED @ {timestamp} -> {rejection_reason}")
        elif not is_session_valid:
            entry_hr = pd.to_datetime(timestamp, utc=True).hour
            rejection_reason = f"Blocked by Session Filter: Entry hour {entry_hr:02d}:00 UTC outside US session window ({session_filter.start_hour:02d}:00–{session_filter.end_hour:02d}:00 UTC)"
            logger.info(f"Signal [{sig_id}] REJECTED @ {timestamp} -> {rejection_reason}")
        elif not htf_valid:
            rejection_reason = "Blocked by Multi-Timeframe Confirmation Filter"
            logger.debug(f"Signal [{sig_id}] REJECTED @ {timestamp} -> {rejection_reason}")
        elif not dir_valid:
            rejection_reason = "Blocked by Strategy Direction Filter"
            logger.debug(f"Signal [{sig_id}] REJECTED @ {timestamp} -> {rejection_reason}")

        if rejection_reason is None:
            risk_passed, _ = risk_engine.evaluate_risk(i, 0.0, 0.0)
            if risk_passed:
                qty, pos_val, _ = signal_engine.position_sizer.calculate_position(current_equity, entry_price, sl_price)
                if qty > 0:
                    risk_engine.last_trade_bar = i
                    sig = TradeSignal(sig_id, timestamp, sym, "BUY", entry_price, sl_price, tp_price, qty, pos_val, vol_regime, True, True, True, "Trade Approved")
                    signals.append(sig)
                    continue

        sig = TradeSignal(sig_id, timestamp, sym, "HOLD", entry_price, sl_price, tp_price, 0.0, 0.0, vol_regime, dir_valid, htf_valid, False, rejection_reason or "Not Approved")
        signals.append(sig)

    # Backtest
    backtester = Backtester(config)
    test_df = df_strat.iloc[50:].copy().reset_index(drop=True)
    equity_df, trades, metrics = backtester.run_backtest(test_df, signals)

    return sym, strat_name, metrics


def main():
    print("=" * 95)
    print("   BTC-ML-SYSTEM QUANTITATIVE AUDIT: TRADE JOURNAL HIGH-VALUE FILTERS EVALUATION   ")
    print("=" * 95)

    # A. BTCUSDT 4H COMPARISON
    # Baseline: MTF Medium only (allowed regimes: CALM, NORMAL)
    btc_baseline_override = {"volatility_regime": {"enabled": True, "allowed_regimes": ["CALM", "NORMAL"]}}
    _, _, btc_prev = run_single_pipeline("configs/btc_4h_v4.5.yaml", override_config=btc_baseline_override)

    # New: MTF Medium + NORMAL volatility regime only
    btc_new_override = {"volatility_regime": {"enabled": True, "allowed_regimes": ["NORMAL"]}}
    _, _, btc_new = run_single_pipeline("configs/btc_4h_v4.5.yaml", override_config=btc_new_override)

    # B. ETHUSDT 1H COMPARISON
    # Baseline: No MTF, Session Filter disabled
    eth_baseline_override = {"session_filter": {"enabled": False}, "multi_timeframe_filter": {"enabled": False}}
    _, _, eth_prev = run_single_pipeline("configs/eth_1h_v4.5.yaml", override_config=eth_baseline_override)

    # New: US Session 14:00–22:00 UTC only
    eth_new_override = {"session_filter": {"enabled": True, "start_hour": 14, "end_hour": 22}, "multi_timeframe_filter": {"enabled": False}}
    _, _, eth_new = run_single_pipeline("configs/eth_1h_v4.5.yaml", override_config=eth_new_override)

    # PRINT COMPARISON TABLES
    print("\n" + "=" * 105)
    print("      A. BTCUSDT 4H: VOLATILITY REGIME FILTER PERFORMANCE COMPARISON      ")
    print("=" * 105)
    print(f"  {'Configuration':<42} | {'Total Trades':<12} | {'Win Rate':<10} | {'Return %':<10} | {'Max DD %':<10} | {'Profit Factor':<13}")
    print("-" * 105)
    print(f"  {'Previous Best (MTF Medium only)':<42} | {btc_prev['total_trades']:<12} | {btc_prev['win_rate']:<10.2%} | {btc_prev['total_return_pct']:<10.2f}% | {btc_prev['max_drawdown_pct']:<10.2f}% | {btc_prev['profit_factor']:<13.2f}")
    print(f"  {'New (MTF Medium + NORMAL Vol Regime only)':<42} | {btc_new['total_trades']:<12} | {btc_new['win_rate']:<10.2%} | {btc_new['total_return_pct']:<10.2f}% | {btc_new['max_drawdown_pct']:<10.2f}% | {btc_new['profit_factor']:<13.2f}")
    print("=" * 105)

    print("\n" + "=" * 105)
    print("      B. ETHUSDT 1H: US SESSION FILTER PERFORMANCE COMPARISON      ")
    print("=" * 105)
    print(f"  {'Configuration':<42} | {'Total Trades':<12} | {'Win Rate':<10} | {'Return %':<10} | {'Max DD %':<10} | {'Profit Factor':<13}")
    print("-" * 105)
    print(f"  {'Previous Best (No MTF, All Sessions)':<42} | {eth_prev['total_trades']:<12} | {eth_prev['win_rate']:<10.2%} | {eth_prev['total_return_pct']:<10.2f}% | {eth_prev['max_drawdown_pct']:<10.2f}% | {eth_prev['profit_factor']:<13.2f}")
    print(f"  {'New (US Session 14:00-22:00 UTC only)':<42} | {eth_new['total_trades']:<12} | {eth_new['win_rate']:<10.2%} | {eth_new['total_return_pct']:<10.2f}% | {eth_new['max_drawdown_pct']:<10.2f}% | {eth_new['profit_factor']:<13.2f}")
    print("=" * 105 + "\n")


if __name__ == "__main__":
    main()
