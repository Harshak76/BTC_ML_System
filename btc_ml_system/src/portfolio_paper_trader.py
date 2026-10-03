"""
Portfolio Paper Trader Engine for V5.0 btc_ml_system.
Executes live polling, multi-asset strategy evaluation, portfolio risk checking,
correlation filtering, and paper order submission to Alpaca REST API v2.
"""

import os
import sys
import time
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
import pandas as pd
import numpy as np

from btc_ml_system.src.data_provider import DataProvider
from btc_ml_system.src.regimes import VolatilityRegimeClassifier
from btc_ml_system.src.direction import SessionFilter
from btc_ml_system.src.strategies import StrategyFactory
from btc_ml_system.src.signal_engine import SignalEngine
from btc_ml_system.src.position_sizing import PositionSizer
from btc_ml_system.src.risk import RiskEngine
from btc_ml_system.src.alpaca_executor import AlpacaExecutor

logger = logging.getLogger("btc_ml_system.portfolio_paper_trader")


class PortfolioPaperTrader:
    """
    Live Paper Trading Orchestrator for Simple Portfolio Mode V5.0.
    Monitors 7 assets (AAPL, MSFT, NVDA, TSLA, AMZN, BTCUSDT, ETHUSDT),
    enforces exact locked strategy settings, portfolio risk limits,
    correlation rules, and executes orders via Alpaca REST API.
    """

    def __init__(self, main_config: Dict[str, Any], dry_run_override: Optional[bool] = None):
        self.config = main_config
        self.alp_cfg = main_config.get("alpaca", {})
        
        if dry_run_override is not None:
            self.config.setdefault("alpaca", {})["dry_run"] = dry_run_override

        self.alpaca = AlpacaExecutor(self.config)
        self.port_cfg = main_config.get("portfolio", {})
        
        # Portfolio Allocations & Risk Limits
        self.weights = self.port_cfg.get("weights", {"equity_basket": 0.50, "BTCUSDT": 0.25, "ETHUSDT": 0.25})
        self.risk_cfg = self.port_cfg.get("risk_limits", {})
        self.max_portfolio_risk_pct = float(self.risk_cfg.get("max_portfolio_risk_pct", 0.03))
        self.max_daily_loss_pct = float(self.risk_cfg.get("max_daily_loss_pct", 0.020))
        self.max_drawdown_limit_pct = float(self.risk_cfg.get("max_drawdown_limit_pct", 0.10))
        
        self.corr_cfg = self.port_cfg.get("correlation_control", {})
        self.corr_enabled = bool(self.corr_cfg.get("enabled", True))
        self.corr_lookback = int(self.corr_cfg.get("lookback_window", 30))
        self.max_corr_threshold = float(self.corr_cfg.get("max_correlation_threshold", 0.70))

        self.symbols_equity = self.config.get("symbols", {}).get("equity_symbols", ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"])
        self.symbols_crypto = self.config.get("symbols", {}).get("crypto_symbols", ["BTCUSDT", "ETHUSDT"])
        self.all_symbols = self.symbols_equity + self.symbols_crypto

        # Load & Prepare Individual Component Configs with Locked Overrides
        self.asset_configs = self._load_and_lock_asset_configs()
        
        # Strategy Pipeline Engines per Asset
        self.pipeline = {}
        self._init_pipelines()

        # Tracking State
        self.daily_start_equity = self.alpaca.get_account_equity()
        self.peak_portfolio_equity = self.daily_start_equity
        self.trade_journal_path = Path(main_config.get("journal_path", "reports/paper_trade_journal_v5.csv"))
        self.trade_journal_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.open_positions = {}  # symbol -> position dict
        self.executed_trades_history = []

        logger.info("PortfolioPaperTrader successfully initialized with all locked strategies!")

    def _load_and_lock_asset_configs(self) -> Dict[str, Dict[str, Any]]:
        """Loads component strategy YAML files and applies strict baseline lock overrides."""
        comp_map = self.config.get("component_configs", {})
        asset_cfgs = {}
        base_dir = Path(__file__).resolve().parent.parent

        for sym in self.all_symbols:
            rel_path = comp_map.get(sym, f"configs/{sym.lower()}_v4.3.yaml")
            cfg_file = base_dir / rel_path
            
            if not cfg_file.exists():
                logger.warning(f"Config file {cfg_file} not found. Creating fallback config for {sym}.")
                cfg_data = {"system": {"name": sym}, "asset": {"symbol": sym, "asset_type": "equity" if sym in self.symbols_equity else "crypto"}}
            else:
                with open(cfg_file) as f:
                    cfg_data = yaml.safe_load(f)
            
            asset_cfgs[sym] = cfg_data

        # 1. LOCK EQUITY BASKET V4.3 (FROZEN)
        for sym in self.symbols_equity:
            asset_cfgs[sym]["dynamic_risk_sizer"] = {"enabled": False}
            asset_cfgs[sym]["exit_rules"] = {"enable_early_loss_cut": False, "enable_profit_runner": False}

        # 2. LOCK BTC 4H: MTF Medium + NORMAL Volatility Regime Only
        asset_cfgs["BTCUSDT"]["multi_timeframe_filter"] = {"enabled": True, "strength": "Medium", "ema_fast": 50, "ema_slow": 200}
        asset_cfgs["BTCUSDT"]["session_filter"] = {"enabled": False}
        asset_cfgs["BTCUSDT"]["dynamic_risk_sizer"] = {"enabled": False}
        asset_cfgs["BTCUSDT"]["volatility_regime"] = {"enabled": True, "window": 24, "calm_quantile": 0.33, "high_quantile": 0.67, "allowed_regimes": ["NORMAL"]}
        asset_cfgs["BTCUSDT"]["exit_rules"] = {"enable_early_loss_cut": False, "enable_profit_runner": False, "enable_trailing_stop": True, "trailing_trigger_pct": 0.025, "trailing_dist_pct": 0.020}

        # 3. LOCK ETH 1H: Clean Version (No MTF, No Session Filter)
        asset_cfgs["ETHUSDT"]["multi_timeframe_filter"] = {"enabled": False, "strength": "Medium"}
        asset_cfgs["ETHUSDT"]["session_filter"] = {"enabled": False}
        asset_cfgs["ETHUSDT"]["dynamic_risk_sizer"] = {"enabled": False}
        asset_cfgs["ETHUSDT"]["volatility_regime"] = {"enabled": True, "window": 24, "calm_quantile": 0.33, "high_quantile": 0.67, "allowed_regimes": ["CALM"]}
        asset_cfgs["ETHUSDT"]["exit_rules"] = {"enable_early_loss_cut": False, "enable_profit_runner": False, "enable_trailing_stop": False}

        return asset_cfgs

    def _init_pipelines(self):
        """Instantiates indicator and strategy evaluation engines for each asset."""
        for sym, cfg in self.asset_configs.items():
            self.pipeline[sym] = {
                "config": cfg,
                "data_provider": DataProvider(cfg),
                "vol_classifier": VolatilityRegimeClassifier(cfg),
                "session_filter": SessionFilter(cfg),
                "strategy": StrategyFactory.get_strategy(cfg),
                "signal_engine": SignalEngine(cfg),
                "position_sizer": PositionSizer(cfg),
                "risk_engine": RiskEngine(cfg)
            }

    def run_paper_tick(self) -> Dict[str, Any]:
        """
        Executes a single live market monitoring tick:
        1. Queries account state from Alpaca.
        2. Evaluates portfolio circuit breakers (Daily Loss, Max DD).
        3. Fetches latest candles per asset and evaluates strategy signals.
        4. Validates cross-asset risk and correlation before submitting paper orders.
        """
        account_info = self.alpaca.get_account_details()
        current_equity = account_info["equity"]
        
        # Update Peak Equity & Drawdown tracking
        if current_equity > self.peak_portfolio_equity:
            self.peak_portfolio_equity = current_equity

        current_dd_pct = (self.peak_portfolio_equity - current_equity) / self.peak_portfolio_equity if self.peak_portfolio_equity > 0 else 0.0
        daily_pnl_pct = (current_equity - self.daily_start_equity) / self.daily_start_equity if self.daily_start_equity > 0 else 0.0

        # Check Portfolio Circuit Breakers
        if current_dd_pct >= self.max_drawdown_limit_pct:
            logger.critical(f"MAX DRAWDOWN CIRCUIT BREAKER TRIGGERED: Current DD {current_dd_pct:.2%} >= Limit {self.max_drawdown_limit_pct:.2%}. Halting new entries.")
            return {"status": "circuit_breaker", "reason": "Max Drawdown Limit Exceeded", "equity": current_equity}

        if daily_pnl_pct <= -self.max_daily_loss_pct:
            logger.warning(f"DAILY LOSS LIMIT CIRCUIT BREAKER TRIGGERED: Daily PnL {daily_pnl_pct:.2%} <= Limit -{self.max_daily_loss_pct:.2%}. Blocking new orders today.")
            return {"status": "circuit_breaker", "reason": "Daily Loss Limit Exceeded", "equity": current_equity}

        # Calculate Capital Allocation per Asset
        equity_weight_total = float(self.weights.get("equity_basket", 0.50))
        per_stock_weight = equity_weight_total / len(self.symbols_equity)
        
        allocations = {}
        for sym in self.all_symbols:
            if sym in self.symbols_equity:
                allocations[sym] = per_stock_weight * current_equity
            else:
                allocations[sym] = float(self.weights.get(sym, 0.25)) * current_equity

        tick_signals = []
        tick_orders = []
        recent_returns = {}

        # Evaluate live bar data per symbol
        for sym in self.all_symbols:
            p = self.pipeline[sym]
            cfg = p["config"]
            
            try:
                tf_ltf = cfg["asset"]["base_timeframe"]
                tf_htf = cfg["asset"]["htf_timeframe"]
                
                # Fetch recent candles (50 bars sufficient for live indicator state)
                df_ltf = p["data_provider"].fetch_data(symbol=sym, interval=tf_ltf, days_back=15)
                df_htf = p["data_provider"].fetch_data(symbol=sym, interval=tf_htf, days_back=30)

                if df_ltf.empty or len(df_ltf) < 25:
                    logger.warning(f"Insufficient live bar data fetched for {sym}. Skipping tick evaluation.")
                    continue

                df_reg = p["vol_classifier"].predict_regimes(df_ltf)
                df_sess = p["session_filter"].apply_filter(df_reg)
                df_strat = p["strategy"].evaluate_signals(df_sess, df_htf)
                df_strat["atr"] = p["signal_engine"].compute_atr(df_strat)
                
                # Calculate return series for correlation matrix
                df_strat["returns"] = df_strat["close"].pct_change().fillna(0.0)
                recent_returns[sym] = df_strat["returns"].tail(self.corr_lookback).values

                latest_bar = df_strat.iloc[-1]
                latest_close = float(latest_bar["close"])
                latest_atr = float(latest_bar["atr"])
                latest_regime = str(latest_bar.get("volatility_regime", "NORMAL"))
                
                signal_raw = int(latest_bar.get("signal", 0))

                if signal_raw == 1:
                    # Strategic Buy Signal Generated
                    comp_capital = allocations[sym]
                    sl_dist = latest_atr * p["signal_engine"].sl_atr_mult
                    sl_price = latest_close - sl_dist
                    tp_price = latest_close + (latest_atr * p["signal_engine"].tp_atr_mult)

                    # Position Sizing based on allocated component capital (0.5% risk per trade)
                    risk_amount_usd = comp_capital * 0.005
                    risk_per_unit = latest_close - sl_price
                    qty = risk_amount_usd / risk_per_unit if risk_per_unit > 0 else 0.0

                    sig_id = f"{sym}_{latest_bar['open_time']}"

                    tick_signals.append({
                        "symbol": sym,
                        "signal_id": sig_id,
                        "action": "BUY",
                        "close_price": latest_close,
                        "stop_loss": sl_price,
                        "take_profit": tp_price,
                        "quantity": qty,
                        "risk_usd": risk_amount_usd,
                        "regime": latest_regime
                    })

            except Exception as e:
                logger.error(f"Error evaluating live signal for {sym}: {e}")

        # Correlation Matrix Check among Candidate & Open Positions
        approved_signals = []
        for sig in tick_signals:
            sym = sig["symbol"]
            
            # Check Correlation against active positions
            if self.corr_enabled and self.open_positions:
                too_correlated = False
                if sym in recent_returns:
                    r_sym = recent_returns[sym]
                    for open_sym in self.open_positions:
                        if open_sym in recent_returns and open_sym != sym:
                            r_open = recent_returns[open_sym]
                            min_len = min(len(r_sym), len(r_open))
                            if min_len > 10:
                                corr_val = np.corrcoef(r_sym[-min_len:], r_open[-min_len:])[0, 1]
                                if not np.isnan(corr_val) and corr_val > self.max_corr_threshold:
                                    logger.warning(f"PORTFOLIO CORRELATION BLOCK: {sym} correlation {corr_val:.2f} > threshold {self.max_corr_threshold:.2f} with active position {open_sym}.")
                                    too_correlated = True
                                    break
                if too_correlated:
                    continue

            # Combined Open Portfolio Dollar Risk Check
            current_open_risk = sum(p.get("risk_usd", 0.0) for p in self.open_positions.values())
            if (current_open_risk + sig["risk_usd"]) / current_equity > self.max_portfolio_risk_pct:
                logger.warning(f"PORTFOLIO MAX RISK BLOCK: Combined risk {(current_open_risk + sig['risk_usd'])/current_equity:.2%} exceeds max limit {self.max_portfolio_risk_pct:.2%}.")
                continue

            approved_signals.append(sig)

        # Order Execution via Alpaca Paper Endpoint
        for sig in approved_signals:
            order_res = self.alpaca.place_paper_order(
                signal_id=sig["signal_id"],
                symbol=sig["symbol"],
                qty=sig["quantity"],
                side="buy",
                estimated_price=sig["close_price"]
            )
            
            if order_res.get("status") in ["accepted", "submitted", "filled", "dry_run_success"]:
                self.open_positions[sig["symbol"]] = sig
                tick_orders.append(order_res)
                self._log_trade_journal(sig, order_res)

        return {
            "status": "success",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "equity": current_equity,
            "signals_evaluated": len(tick_signals),
            "orders_placed": len(tick_orders),
            "active_positions_count": len(self.open_positions)
        }

    def _log_trade_journal(self, sig: Dict[str, Any], order_res: Dict[str, Any]):
        """Appends trade records into persistent CSV Trade Journal."""
        row = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "symbol": sig["symbol"],
            "signal_id": sig["signal_id"],
            "action": sig["action"],
            "entry_price": sig["close_price"],
            "stop_loss": sig["stop_loss"],
            "take_profit": sig["take_profit"],
            "qty": sig["quantity"],
            "risk_usd": sig["risk_usd"],
            "regime": sig["regime"],
            "order_id": order_res.get("id", "MOCK"),
            "status": order_res.get("status", "UNKNOWN")
        }
        
        df_row = pd.DataFrame([row])
        if not self.trade_journal_path.exists():
            df_row.to_csv(self.trade_journal_path, index=False)
        else:
            df_row.to_csv(self.trade_journal_path, mode='a', header=False, index=False)
            
        logger.info(f"Logged paper trade to journal: {sig['symbol']} {sig['action']} Qty: {sig['quantity']:.4f}")

    def get_daily_summary(self) -> Dict[str, Any]:
        """Generates comprehensive daily paper trading summary report."""
        acc = self.alpaca.get_account_details()
        equity = acc["equity"]
        cash = acc["cash"]
        buying_power = acc["buying_power"]
        
        pnl_usd = equity - self.daily_start_equity
        pnl_pct = (pnl_usd / self.daily_start_equity) * 100.0 if self.daily_start_equity > 0 else 0.0
        dd_pct = ((self.peak_portfolio_equity - equity) / self.peak_portfolio_equity) * 100.0 if self.peak_portfolio_equity > 0 else 0.0

        positions = self.alpaca.get_open_positions()

        summary = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "account_equity": equity,
            "starting_daily_equity": self.daily_start_equity,
            "cash_balance": cash,
            "buying_power": buying_power,
            "daily_pnl_usd": pnl_usd,
            "daily_pnl_pct": pnl_pct,
            "peak_equity": self.peak_portfolio_equity,
            "current_drawdown_pct": dd_pct,
            "open_positions_count": len(positions),
            "open_positions": positions
        }

        print("\n" + "=" * 90)
        print("          ALPACA PAPER TRADING DAILY SUMMARY REPORT - PORTFOLIO V5.0          ")
        print("=" * 90)
        print(f"  Account Equity        : ${equity:,.2f}")
        print(f"  Starting Daily Equity : ${self.daily_start_equity:,.2f}")
        print(f"  Daily PnL ($ / %)     : ${pnl_usd:+,.2f} ({pnl_pct:+.2f}%)")
        print(f"  Current Drawdown      : {dd_pct:.2f}% (Peak: ${self.peak_portfolio_equity:,.2f})")
        print(f"  Cash / Buying Power   : ${cash:,.2f} / ${buying_power:,.2f}")
        print(f"  Active Positions      : {len(positions)}")
        for pos in positions:
            print(f"    -> {pos.get('symbol'):<8} | Qty: {pos.get('qty')} | Value: ${float(pos.get('market_value', 0)):,.2f} | PnL: ${float(pos.get('unrealized_pl', 0)):+,.2f}")
        print("=" * 90 + "\n")

        return summary

    def activate_kill_switch(self) -> Dict[str, Any]:
        """Emergency Flatten All Positions and Cancel Orders."""
        logger.warning("ACTIVATING SYSTEM KILL SWITCH VIA PORTFOLIO PAPER TRADER...")
        res = self.alpaca.flatten_all_positions()
        self.open_positions.clear()
        return res
