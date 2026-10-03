"""
Full Pipeline Runner & Diagnostics Engine for V5.1 btc_ml_system.
Executes Part A (Regime-Specific Parameters) & Part B (Better Exit Upgrades):
1. BTCUSDT 4H Standalone Comparison (Baseline vs Upgrade)
2. ETHUSDT 1H Standalone Comparison (Baseline vs Upgrade)
3. Full Portfolio Comparison (Portfolio V5.0 Baseline vs Upgraded Portfolio V5.1)
"""

import os
import sys
import logging
from pathlib import Path
import yaml
import pandas as pd
import numpy as np
from typing import Dict, Any

# Add workspace root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from btc_ml_system.src.data_provider import DataProvider
from btc_ml_system.src.regimes import VolatilityRegimeClassifier
from btc_ml_system.src.direction import SessionFilter
from btc_ml_system.src.strategies import StrategyFactory
from btc_ml_system.src.signal_engine import SignalEngine, TradeSignal
from btc_ml_system.src.backtester import Backtester
from btc_ml_system.src.portfolio_manager import PortfolioManager

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("btc_ml_system.v5_1_runner")


def load_config(config_rel_path: str) -> dict:
    config_path = Path(__file__).resolve().parent / config_rel_path
    with open(config_path) as f:
        return yaml.safe_load(f)


def run_standalone_strategy(config: dict) -> Dict[str, Any]:
    sym = config['asset']['symbol']
    strat_name = config['strategy']['name']

    years = config.get("data", {}).get("history_years", 2)
    days_back = years * 365
    provider = DataProvider(config)
    df_ltf = provider.fetch_data(symbol=sym, interval=config['asset']['base_timeframe'], days_back=days_back)
    df_htf = provider.fetch_data(symbol=sym, interval=config['asset']['htf_timeframe'], days_back=days_back * 2)

    vol_classifier = VolatilityRegimeClassifier(config)
    df_reg = vol_classifier.predict_regimes(df_ltf)

    session_filter = SessionFilter(config)
    df_sess = session_filter.apply_filter(df_reg)

    strategy_engine = StrategyFactory.get_strategy(config)
    df_strat = strategy_engine.evaluate_signals(df_sess, df_htf)

    signal_engine = SignalEngine(config)
    signals = []

    current_equity = config.get("risk_engine", {}).get("initial_capital", 10000.0)
    atr_series = signal_engine.compute_atr(df_strat)
    df_strat["atr"] = atr_series

    risk_engine = signal_engine.risk_engine

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

        sl_m, tp_m, tr_trig, tr_dist = signal_engine.get_regime_exit_params(vol_regime)
        sl_price = entry_price - (sl_m * atr_val)
        tp_price = entry_price + (tp_m * atr_val)

        import uuid
        sig_id = str(uuid.uuid4())[:8]

        rejection_reason = None
        if not is_vol_favorable:
            rejection_reason = f"Blocked by Volatility Regime Filter: Current regime is '{vol_regime}'"
        elif not is_session_valid:
            rejection_reason = "Blocked by Session Filter"
        elif not htf_valid:
            rejection_reason = "Blocked by Multi-Timeframe Confirmation Filter"
        elif not dir_valid:
            rejection_reason = "Blocked by Strategy Direction Filter"

        if rejection_reason is None:
            risk_passed, _ = risk_engine.evaluate_risk(i, 0.0, 0.0)
            if risk_passed:
                qty, pos_val, _ = signal_engine.position_sizer.calculate_position(current_equity, entry_price, sl_price)
                if qty > 0:
                    risk_engine.last_trade_bar = i
                    sig = TradeSignal(sig_id, timestamp, sym, "BUY", entry_price, sl_price, tp_price, qty, pos_val, vol_regime, True, True, True, "Trade Approved", trailing_trigger_pct=tr_trig, trailing_dist_pct=tr_dist)
                    signals.append(sig)
                    continue

        sig = TradeSignal(sig_id, timestamp, sym, "HOLD", entry_price, sl_price, tp_price, 0.0, 0.0, vol_regime, dir_valid, htf_valid, False, rejection_reason or "Not Approved")
        signals.append(sig)

    backtester = Backtester(config)
    test_df = df_strat.iloc[50:].copy().reset_index(drop=True)
    equity_df, trades, metrics = backtester.run_backtest(test_df, signals)

    return metrics


def main():
    print("=" * 115)
    print("   BTC-ML-SYSTEM V5.1 QUANTITATIVE AUDIT: REGIME PARAMETERS & EXIT UPGRADES   ")
    print("=" * 115)

    # 1. BTCUSDT 4H STANDALONE COMPARISON
    # Baseline BTC 4H: MTF Medium + NORMAL volatility regime only
    btc_baseline_cfg = load_config("configs/btc_4h_v4.5.yaml")
    btc_baseline_cfg["volatility_regime"] = {"enabled": True, "window": 24, "calm_quantile": 0.33, "high_quantile": 0.67, "allowed_regimes": ["NORMAL"]}
    btc_baseline_cfg["exit_rules"] = {"enable_trailing_stop": True, "trailing_trigger_pct": 0.025, "trailing_dist_pct": 0.020, "enable_early_loss_cut": False, "enable_profit_runner": False}
    btc_prev_metrics = run_standalone_strategy(btc_baseline_cfg)

    # Upgraded BTC 4H: Regime-Specific Parameters + Part B Exits (Early Loss Cut & Profit Runner)
    btc_upgraded_cfg = load_config("configs/btc_4h_v4.5.yaml")
    btc_upgraded_cfg["volatility_regime"] = {
        "enabled": True, "window": 24, "calm_quantile": 0.33, "high_quantile": 0.67, "allowed_regimes": ["NORMAL"],
        "regime_params": {
            "NORMAL": {
                "sl_atr_multiplier": 1.5,
                "tp_atr_multiplier": 4.0,       # Extended target for NORMAL regime momentum
                "trailing_trigger_pct": 0.025,
                "trailing_dist_pct": 0.020
            }
        }
    }
    btc_upgraded_cfg["exit_rules"] = {
        "enable_trailing_stop": True,
        "trailing_trigger_pct": 0.025,
        "trailing_dist_pct": 0.020,
        "enable_early_loss_cut": True,
        "early_loss_cut_bars": 5,
        "early_loss_cut_max_pnl_r": 0.0,        # Cut losing trades early at bar 5 if <= 0 R
        "enable_profit_runner": True,
        "profit_runner_trigger_r": 2.5,
        "profit_runner_trail_dist_pct": 0.015
    }
    btc_new_metrics = run_standalone_strategy(btc_upgraded_cfg)

    # 2. ETHUSDT 1H STANDALONE COMPARISON
    # Baseline ETH 1H: Clean version (No MTF, No Session Filter, CALM regime)
    eth_baseline_cfg = load_config("configs/eth_1h_v4.5.yaml")
    eth_baseline_cfg["multi_timeframe_filter"] = {"enabled": False}
    eth_baseline_cfg["session_filter"] = {"enabled": False}
    eth_baseline_cfg["volatility_regime"] = {"enabled": True, "window": 24, "calm_quantile": 0.33, "high_quantile": 0.67, "allowed_regimes": ["CALM"]}
    eth_baseline_cfg["exit_rules"] = {"enable_trailing_stop": False, "enable_early_loss_cut": False, "enable_profit_runner": False}
    eth_prev_metrics = run_standalone_strategy(eth_baseline_cfg)

    # Upgraded ETH 1H: Better Exits (Early Loss Cut + Profit Runner)
    eth_upgraded_cfg = load_config("configs/eth_1h_v4.5.yaml")
    eth_upgraded_cfg["multi_timeframe_filter"] = {"enabled": False}
    eth_upgraded_cfg["session_filter"] = {"enabled": False}
    eth_upgraded_cfg["volatility_regime"] = {"enabled": True, "window": 24, "calm_quantile": 0.33, "high_quantile": 0.67, "allowed_regimes": ["CALM"]}
    eth_upgraded_cfg["exit_rules"] = {
        "enable_trailing_stop": False,
        "enable_early_loss_cut": True,
        "early_loss_cut_bars": 6,               # Cut non-performing ETH trades early at bar 6
        "early_loss_cut_max_pnl_r": 0.0,
        "enable_profit_runner": True,
        "profit_runner_trigger_r": 2.0,
        "profit_runner_trail_dist_pct": 0.012
    }
    eth_new_metrics = run_standalone_strategy(eth_upgraded_cfg)

    # 3. FULL PORTFOLIO COMPARISON (Equity 50% + BTC 25% + ETH 25%)
    port_config = load_config("configs/portfolio_v5.yaml")

    # Portfolio V5.0 Baseline configs
    portfolio_baseline_assets = {
        "AAPL": load_config("configs/aapl_v4.3.yaml"),
        "MSFT": load_config("configs/msft_v4.3.yaml"),
        "NVDA": load_config("configs/nvda_v4.3.yaml"),
        "TSLA": load_config("configs/tsla_v4.3.yaml"),
        "AMZN": load_config("configs/amzn_v4.3.yaml"),
        "BTCUSDT": btc_baseline_cfg,
        "ETHUSDT": eth_baseline_cfg
    }
    pm_prev = PortfolioManager(port_config)
    port_prev_metrics = pm_prev.run_portfolio_backtest(portfolio_baseline_assets)

    # Portfolio V5.1 Upgraded configs
    portfolio_upgraded_assets = {
        "AAPL": load_config("configs/aapl_v4.3.yaml"),
        "MSFT": load_config("configs/msft_v4.3.yaml"),
        "NVDA": load_config("configs/nvda_v4.3.yaml"),
        "TSLA": load_config("configs/tsla_v4.3.yaml"),
        "AMZN": load_config("configs/amzn_v4.3.yaml"),
        "BTCUSDT": btc_upgraded_cfg,
        "ETHUSDT": eth_upgraded_cfg
    }
    pm_new = PortfolioManager(port_config)
    port_new_metrics = pm_new.run_portfolio_backtest(portfolio_upgraded_assets)

    # PRINT COMPARISON TABLES
    print("\n" + "=" * 105)
    print("      1. BTCUSDT 4H STANDALONE: REGIME PARAMETERS & EXIT UPGRADES      ")
    print("=" * 105)
    print(f"  {'Configuration':<45} | {'Total Trades':<12} | {'Win Rate':<10} | {'Return %':<10} | {'Max DD %':<10} | {'Profit Factor':<13}")
    print("-" * 105)
    b_p = btc_prev_metrics
    b_n = btc_new_metrics
    print(f"  {'Previous Best (MTF + NORMAL filter only)':<45} | {b_p['total_trades']:<12} | {b_p['win_rate']:<10.2%} | {b_p['total_return_pct']:<10.2f}% | {b_p['max_drawdown_pct']:<10.2f}% | {b_p['profit_factor']:<13.2f}")
    print(f"  {'New (Regime Params + Early Cut & Profit Runner)':<45} | {b_n['total_trades']:<12} | {b_n['win_rate']:<10.2%} | {b_n['total_return_pct']:<10.2f}% | {b_n['max_drawdown_pct']:<10.2f}% | {b_n['profit_factor']:<13.2f}")
    print("=" * 105)

    print("\n" + "=" * 105)
    print("      2. ETHUSDT 1H STANDALONE: BETTER EXIT UPGRADES      ")
    print("=" * 105)
    print(f"  {'Configuration':<45} | {'Total Trades':<12} | {'Win Rate':<10} | {'Return %':<10} | {'Max DD %':<10} | {'Profit Factor':<13}")
    print("-" * 105)
    e_p = eth_prev_metrics
    e_n = eth_new_metrics
    print(f"  {'Previous Clean Version':<45} | {e_p['total_trades']:<12} | {e_p['win_rate']:<10.2%} | {e_p['total_return_pct']:<10.2f}% | {e_p['max_drawdown_pct']:<10.2f}% | {e_p['profit_factor']:<13.2f}")
    print(f"  {'New (Early Loss Cut & Profit Runner Exits)':<45} | {e_n['total_trades']:<12} | {e_n['win_rate']:<10.2%} | {e_n['total_return_pct']:<10.2f}% | {e_n['max_drawdown_pct']:<10.2f}% | {e_n['profit_factor']:<13.2f}")
    print("=" * 105)

    print("\n" + "=" * 105)
    print("      3. FULL PORTFOLIO (EQUITY 50% + BTC 25% + ETH 25%)      ")
    print("=" * 105)
    print(f"  {'Configuration':<45} | {'Total Trades':<12} | {'Win Rate':<10} | {'Return %':<10} | {'Max DD %':<10} | {'Profit Factor':<13}")
    print("-" * 105)
    p_p = port_prev_metrics
    p_n = port_new_metrics
    print(f"  {'Previous Portfolio V5.0 Results':<45} | {p_p['total_trades']:<12} | {p_p['win_rate']:<10.2%} | {p_p['total_return_pct']:<10.2f}% | {p_p['max_drawdown_pct']:<10.2f}% | {p_p['profit_factor']:<13.2f}")
    print(f"  {'New Upgraded Portfolio V5.1 Results':<45} | {p_n['total_trades']:<12} | {p_n['win_rate']:<10.2%} | {p_n['total_return_pct']:<10.2f}% | {p_n['max_drawdown_pct']:<10.2f}% | {p_n['profit_factor']:<13.2f}")
    print("=" * 105 + "\n")


if __name__ == "__main__":
    main()
