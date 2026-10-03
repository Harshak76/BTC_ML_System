"""
Full Portfolio Pipeline Runner & Diagnostics Engine for V5.0 btc_ml_system.
Executes Simple Portfolio Mode combining:
1. Frozen V4.3 US Equities Basket (AAPL, MSFT, NVDA, TSLA, AMZN)
2. BTC 4H (with NORMAL Volatility Regime Filter)
3. ETH 1H (Clean Version: Session Filter Disabled, MTF Disabled)
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

from btc_ml_system.src.portfolio_manager import PortfolioManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("btc_ml_system.v5_0_portfolio_runner")


def load_config(config_rel_path: str) -> dict:
    config_path = Path(__file__).resolve().parent / config_rel_path
    with open(config_path) as f:
        return yaml.safe_load(f)


def main():
    print("=" * 115)
    print("   BTC-ML-SYSTEM V5.0 SIMPLE PORTFOLIO MODE QUANTITATIVE AUDIT   ")
    print("=" * 115)

    # Load Portfolio Config
    port_config = load_config("configs/portfolio_v5.yaml")

    # Load Individual Locked Component Configs
    asset_configs = {
        # Frozen Equity Basket (V4.3)
        "AAPL": load_config("configs/aapl_v4.3.yaml"),
        "MSFT": load_config("configs/msft_v4.3.yaml"),
        "NVDA": load_config("configs/nvda_v4.3.yaml"),
        "TSLA": load_config("configs/tsla_v4.3.yaml"),
        "AMZN": load_config("configs/amzn_v4.3.yaml"),

        # BTC 4H with NORMAL Volatility Filter
        "BTCUSDT": load_config("configs/btc_4h_v4.5.yaml"),

        # ETH 1H Clean Version (No MTF, No Session Filter)
        "ETHUSDT": load_config("configs/eth_1h_v4.5.yaml")
    }

    # Ensure ETH 1H Clean Version override parameters are locked
    asset_configs["ETHUSDT"]["multi_timeframe_filter"] = {"enabled": False, "strength": "Medium"}
    asset_configs["ETHUSDT"]["session_filter"] = {"enabled": False}
    asset_configs["ETHUSDT"]["dynamic_risk_sizer"] = {"enabled": False}
    asset_configs["ETHUSDT"]["volatility_regime"] = {"enabled": True, "window": 24, "calm_quantile": 0.33, "high_quantile": 0.67, "allowed_regimes": ["CALM"]}

    # Ensure BTC 4H NORMAL Volatility Filter override parameters are locked
    asset_configs["BTCUSDT"]["multi_timeframe_filter"] = {"enabled": True, "strength": "Medium", "ema_fast": 50, "ema_slow": 200}
    asset_configs["BTCUSDT"]["session_filter"] = {"enabled": False}
    asset_configs["BTCUSDT"]["dynamic_risk_sizer"] = {"enabled": False}
    asset_configs["BTCUSDT"]["volatility_regime"] = {"enabled": True, "window": 24, "calm_quantile": 0.33, "high_quantile": 0.67, "allowed_regimes": ["NORMAL"]}

    # Instantiate PortfolioManager and execute portfolio backtest
    pm = PortfolioManager(port_config)
    results = pm.run_portfolio_backtest(asset_configs)

    # 1. DISPLAY COMPONENT & ASSET INDIVIDUAL PERFORMANCE IN PORTFOLIO
    print("\n" + "=" * 115)
    print("      A. INDIVIDUAL COMPONENT PERFORMANCE INSIDE PORTFOLIO      ")
    print("=" * 115)
    print(f"  {'Component / Asset':<35} | {'Weight %':<10} | {'Trades':<8} | {'Win Rate':<10} | {'Return %':<10} | {'Profit Factor':<13} | {'Net PnL ($)':<12}")
    print("-" * 115)

    comp = results["component_breakdown"]
    for comp_name, m in comp.items():
        print(f"  {comp_name:<35} | {m['weight_pct']:<10.1f}% | {m['total_trades']:<8} | {m['win_rate']:<10.2%} | {m['return_pct']:<10.2f}% | {m['profit_factor']:<13.2f} | ${m['total_pnl_usd']:<11,.2f}")

    print("-" * 115)
    print("  Detailed Asset Breakdown inside Portfolio:")
    for sym, m in results["asset_breakdown"].items():
        print(f"    -> {sym:<8}: Trades={m['total_trades']:<4} | WinRate={m['win_rate']:<6.2%} | Return={m['return_pct']:>6.2f}% | PF={m['profit_factor']:>4.2f} | NetPnL=${m['total_pnl_usd']:>8,.2f}")
    print("=" * 115)

    # 2. DISPLAY FULL PORTFOLIO METRICS
    print("\n" + "=" * 115)
    print("      B. FULL PORTFOLIO EQUITY CURVE METRICS      ")
    print("=" * 115)
    print(f"  Initial Portfolio Capital     : ${results['initial_capital']:,.2f}")
    print(f"  Final Portfolio Capital       : ${results['final_capital']:,.2f}")
    print(f"  Total Portfolio Return        : {results['total_return_pct']:+.2f}%")
    print(f"  Total Portfolio Trades        : {results['total_trades']}")
    print(f"  Overall Portfolio Win Rate    : {results['win_rate']:.2%}")
    print(f"  Max Portfolio Drawdown        : {results['max_drawdown_pct']:.2f}%")
    print(f"  Portfolio Profit Factor       : {results['profit_factor']:.2f}")
    print("=" * 115)

    # 3. DISPLAY CORRELATION & RISK FILTER STATS
    print("\n" + "=" * 115)
    print("      C. PORTFOLIO RISK & CORRELATION CONTROL DIAGNOSTICS      ")
    print("=" * 115)
    print(f"  Trades Blocked by Pairwise Correlation Filter (> {port_config['portfolio']['correlation_control']['max_correlation_threshold']:.2f}) : {results['blocked_by_correlation_count']}")
    print(f"  Trades Blocked by Portfolio Max Total Open Risk Limit        : {results['blocked_by_portfolio_risk_count']}")
    print(f"  Trades Blocked by Portfolio Drawdown / Daily Circuit Breaker   : {results['blocked_by_circuit_breaker_count']}")
    print("=" * 115 + "\n")


if __name__ == "__main__":
    main()
