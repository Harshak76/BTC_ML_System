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
from btc_ml_system.src.database import DatabaseManager

logger = logging.getLogger("btc_ml_system.portfolio_paper_trader")


class PortfolioPaperTrader:
    """
    Live Paper Trading Orchestrator for Simple Portfolio Mode V5.0.
    Monitors 7 assets (AAPL, MSFT, NVDA, TSLA, AMZN, BTCUSDT, ETHUSDT),
    enforces exact locked strategy settings, portfolio risk limits,
    correlation rules, and executes orders via Alpaca REST API.
    """

    def __init__(
        self,
        main_config: Dict[str, Any],
        dry_run_override: Optional[bool] = None,
        mode_override: Optional[str] = None
    ):
        self.config = main_config
        self.alp_cfg = main_config.get("alpaca", {})
        
        if dry_run_override is not None:
            self.config.setdefault("alpaca", {})["dry_run"] = dry_run_override

        # Mode Resolution: CLI Override -> Config Profile -> Default 'strict'
        raw_mode = (
            mode_override or
            main_config.get("system", {}).get("trading_mode") or
            main_config.get("trading_mode", "strict")
        )
        self.trading_mode = raw_mode.lower().strip()
        if self.trading_mode not in ["strict", "loose_stage1"]:
            logger.warning(f"Unknown trading_mode '{self.trading_mode}', defaulting to 'strict'")
            self.trading_mode = "strict"

        self.alpaca = AlpacaExecutor(self.config)
        self.port_cfg = main_config.get("portfolio", {})
        
        # Portfolio Allocations & Risk Limits (Strict & Unchanged across all modes)
        self.weights = self.port_cfg.get("weights", {"equity_basket": 0.50, "BTCUSDT": 0.25, "ETHUSDT": 0.25})
        self.risk_cfg = self.port_cfg.get("risk_limits", {})
        self.max_portfolio_risk_pct = float(self.risk_cfg.get("max_portfolio_risk_pct", 0.03))
        self.max_daily_loss_pct = float(self.risk_cfg.get("max_daily_loss_pct", 0.020))
        self.max_drawdown_limit_pct = float(self.risk_cfg.get("max_drawdown_limit_pct", 0.10))
        
        # Correlation Control Settings (Mode-dependent: 0.70 strict vs 0.80 loose_stage1)
        self.corr_cfg = self.port_cfg.get("correlation_control", {})
        self.corr_enabled = bool(self.corr_cfg.get("enabled", True))
        self.corr_lookback = int(self.corr_cfg.get("lookback_window", 30))
        
        if self.trading_mode == "loose_stage1":
            self.max_corr_threshold = float(self.corr_cfg.get("loose_correlation_threshold", 0.80))
            self.btc_allowed_regimes = ["NORMAL", "CALM"]
        else:
            self.max_corr_threshold = float(self.corr_cfg.get("max_correlation_threshold", 0.70))
            self.btc_allowed_regimes = ["NORMAL"]

        self.symbols_equity = self.config.get("symbols", {}).get("equity_symbols", ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"])
        self.symbols_crypto = self.config.get("symbols", {}).get("crypto_symbols", ["BTCUSDT", "ETHUSDT"])
        self.all_symbols = self.symbols_equity + self.symbols_crypto

        # Load & Prepare Individual Component Configs with Locked Overrides
        self.asset_configs = self._load_and_lock_asset_configs()
        
        # Strategy Pipeline Engines per Asset
        self.pipeline = {}
        self._init_pipelines()

        # Tracking State & Database Persistence
        self.daily_start_equity = self.alpaca.get_account_equity()
        self.peak_portfolio_equity = self.daily_start_equity
        self.db = DatabaseManager(main_config.get("database", {}).get("path"))
        
        self.open_positions = {}  # symbol -> position dict
        self.executed_trades_history = []
        self._sync_positions_on_startup()

        logger.info(
            f"PortfolioPaperTrader initialized in [{self.trading_mode.upper()}] mode! "
            f"BTC Regimes: {self.btc_allowed_regimes} | Correlation Limit: {self.max_corr_threshold:.2f}"
        )

    def _sync_positions_on_startup(self):
        """Synchronizes internal open positions with Alpaca live positions and DuckDB."""
        try:
            alpaca_positions = self.alpaca.get_open_positions()
            db_positions = {p["symbol"]: p for p in self.db.get_open_positions()}
            
            # Map alpaca symbols (e.g. BTC/USD, ETH/USD, AAPL) back to internal keys
            rev_sym_map = {v.replace("/", ""): k for k, v in self.alpaca.symbol_map.items()}
            rev_sym_map.update({k: k for k in self.all_symbols})
            
            active_symbols = set()
            for pos in alpaca_positions:
                raw_sym = pos.get("symbol", "")
                clean_sym = raw_sym.replace("/", "")
                int_sym = rev_sym_map.get(clean_sym, rev_sym_map.get(raw_sym, raw_sym))
                active_symbols.add(int_sym)
                
                qty = float(pos.get("qty", 0.0))
                entry_px = float(pos.get("avg_entry_price", pos.get("current_price", 0.0)))
                curr_px = float(pos.get("current_price", entry_px))
                
                db_pos = db_positions.get(int_sym, {})
                sl = float(db_pos.get("stop_loss", entry_px * 0.98))
                tp = float(db_pos.get("take_profit", entry_px * 1.04))
                
                self.open_positions[int_sym] = {
                    "symbol": int_sym,
                    "signal_id": db_pos.get("signal_id", f"sync_{int_sym}"),
                    "action": "BUY" if pos.get("side", "long") == "long" else "SELL",
                    "close_price": entry_px,
                    "entry_price": entry_px,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "quantity": qty,
                    "risk_usd": db_pos.get("risk_usd", qty * abs(entry_px - sl)),
                    "regime": db_pos.get("regime", "NORMAL"),
                    "highest_price": max(entry_px, curr_px),
                    "trailing_stop_active": False,
                    "bars_held": 0,
                    "opened_at": db_pos.get("opened_at", datetime.datetime.utcnow())
                }
                logger.info(f"Synchronized active Alpaca position on startup: {int_sym} Qty: {qty} Entry: ${entry_px:,.2f}")
                
            # Clean up DuckDB positions that are no longer open on Alpaca
            for sym in list(db_positions.keys()):
                if sym not in active_symbols:
                    self.db.remove_position(sym)
        except Exception as e:
            logger.error(f"Error syncing startup positions with Alpaca/DuckDB: {e}", exc_info=True)

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
            
            # Pass live_mode and alpaca settings down into asset pipelines
            cfg_data["live_mode"] = True
            cfg_data["alpaca"] = self.alp_cfg
            asset_cfgs[sym] = cfg_data

        # 1. LOCK EQUITY BASKET V4.3 (FROZEN)
        for sym in self.symbols_equity:
            asset_cfgs[sym]["dynamic_risk_sizer"] = {"enabled": False}
            asset_cfgs[sym]["exit_rules"] = {"enable_early_loss_cut": False, "enable_profit_runner": False}

        # 2. LOCK BTC 4H: MTF Medium + Volatility Regime (Mode-dependent: NORMAL in strict vs NORMAL+CALM in loose_stage1)
        asset_cfgs["BTCUSDT"]["multi_timeframe_filter"] = {"enabled": True, "strength": "Medium", "ema_fast": 50, "ema_slow": 200}
        asset_cfgs["BTCUSDT"]["session_filter"] = {"enabled": False}
        asset_cfgs["BTCUSDT"]["dynamic_risk_sizer"] = {"enabled": False}
        asset_cfgs["BTCUSDT"]["volatility_regime"] = {
            "enabled": True,
            "window": 24,
            "calm_quantile": 0.33,
            "high_quantile": 0.67,
            "allowed_regimes": self.btc_allowed_regimes
        }
        asset_cfgs["BTCUSDT"]["exit_rules"] = {
            "enable_early_loss_cut": False,
            "enable_profit_runner": False,
            "enable_trailing_stop": True,
            "trailing_trigger_pct": 0.025,
            "trailing_dist_pct": 0.020
        }

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

        # =====================================================================
        # 1. EVALUATE EXITS ON ACTIVE OPEN POSITIONS (Stop Loss / Take Profit)
        # =====================================================================
        closed_symbols = []
        for sym, pos in list(self.open_positions.items()):
            if sym not in self.pipeline:
                continue
            p = self.pipeline[sym]
            cfg = p["config"]
            tf_ltf = cfg["asset"]["base_timeframe"]
            
            try:
                df_curr = p["data_provider"].fetch_data(symbol=sym, interval=tf_ltf, days_back=5, live=True)
                if df_curr.empty:
                    continue
                latest_bar = df_curr.iloc[-1]
                latest_close = float(latest_bar["close"])
                latest_high = float(latest_bar["high"])
                latest_low = float(latest_bar["low"])
                
                entry_px = float(pos.get("entry_price", pos.get("close_price", latest_close)))
                highest_px = max(float(pos.get("highest_price", entry_px)), latest_high)
                pos["highest_price"] = highest_px
                pos["bars_held"] = pos.get("bars_held", 0) + 1
                
                # Check Trailing Stop (Locked BTC 4H rules)
                exit_rules = cfg.get("exit_rules", {})
                if exit_rules.get("enable_trailing_stop", False):
                    trig_pct = float(exit_rules.get("trailing_trigger_pct", 0.025))
                    dist_pct = float(exit_rules.get("trailing_dist_pct", 0.020))
                    profit_ratio = (highest_px - entry_px) / entry_px if entry_px > 0 else 0.0
                    if profit_ratio >= trig_pct:
                        pos["trailing_stop_active"] = True
                        trail_sl = highest_px * (1.0 - dist_pct)
                        pos["stop_loss"] = max(float(pos.get("stop_loss", 0.0)), trail_sl)
                        
                sl = float(pos.get("stop_loss", 0.0))
                tp = float(pos.get("take_profit", 0.0))
                
                hit_sl = (latest_low <= sl) if sl > 0 else False
                hit_tp = (latest_high >= tp) if tp > 0 else False
                
                if hit_sl or hit_tp:
                    exit_reason = "PT_HIT" if hit_tp else ("TRAILING_SL_HIT" if pos.get("trailing_stop_active") else "SL_HIT")
                    exit_price = tp if hit_tp else sl
                    qty = float(pos.get("quantity", 0.0))
                    
                    logger.info(f"[POSITION EXIT TRIGGERED] {sym}: {exit_reason} @ ${exit_price:,.2f} (Entry: ${entry_px:,.2f})")
                    
                    # Close position on Alpaca REST API
                    self.alpaca.close_position(sym, qty=qty)
                    
                    # Record Closed Trade in DuckDB Journal
                    now_dt = datetime.datetime.utcnow()
                    pnl_dollars = (exit_price - entry_px) * qty
                    pnl_pct = (exit_price - entry_px) / entry_px if entry_px > 0 else 0.0
                    dollar_risk = float(pos.get("risk_usd", 0.0))
                    r_mult = pnl_dollars / dollar_risk if dollar_risk > 0 else 0.0
                    
                    trade_record = {
                        "trade_id": f"closed_{pos.get('signal_id', sym)}_{now_dt.strftime('%H%M%S')}",
                        "symbol": sym,
                        "strategy": f"portfolio_paper_v5[{pos.get('trading_mode', self.trading_mode)}]",
                        "base_timeframe": tf_ltf,
                        "htf_timeframe": cfg["asset"].get("htf_timeframe", "4h"),
                        "entry_time": pos.get("opened_at", now_dt),
                        "entry_price": entry_px,
                        "exit_time": now_dt,
                        "exit_price": exit_price,
                        "action": "SELL",
                        "quantity": qty,
                        "position_value_usd": qty * exit_price,
                        "pnl_usd": pnl_dollars,
                        "pnl_pct": pnl_pct,
                        "r_multiple": r_mult,
                        "volatility_regime": str(pos.get("regime", "NORMAL")),
                        "risk_pct_used": 0.005,
                        "entry_reason": f"Strategy Signal Buy ({pos.get('loosening_reason', '') or 'Standard Strategy'})",
                        "exit_reason": exit_reason,
                        "trading_mode": str(pos.get("trading_mode", self.trading_mode)),
                        "is_loosened_trade": bool(pos.get("is_loosened_trade", False)),
                        "loosening_reason": str(pos.get("loosening_reason", ""))
                    }
                    self.db.insert_trade_record(trade_record, source="paper_trade")
                    self.db.remove_position(sym)
                    closed_symbols.append(sym)
            except Exception as e:
                logger.error(f"Error evaluating exit for position {sym}: {e}")
                
        for s in closed_symbols:
            self.open_positions.pop(s, None)

        # =====================================================================
        # 2. EVALUATE STRATEGY SIGNALS ON ALL ASSETS (Real-Time Data)
        # =====================================================================
        tick_signals = []
        tick_orders = []
        recent_returns = {}

        for sym in self.all_symbols:
            if sym in self.open_positions:
                logger.debug(f"{sym} already has an active open position. Skipping new entry.")
                continue

            p = self.pipeline[sym]
            cfg = p["config"]
            
            try:
                tf_ltf = cfg["asset"]["base_timeframe"]
                tf_htf = cfg["asset"]["htf_timeframe"]
                
                # Fetch live candles with real-time Alpaca market feed
                df_ltf = p["data_provider"].fetch_data(symbol=sym, interval=tf_ltf, days_back=15, live=True)
                df_htf = p["data_provider"].fetch_data(symbol=sym, interval=tf_htf, days_back=30, live=True)

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

                    # Detect if trade was allowed specifically due to Stage 1 Loosening
                    is_loosened = False
                    loosening_reasons = []

                    if sym == "BTCUSDT" and latest_regime == "CALM":
                        is_loosened = True
                        loosening_reasons.append("BTC_REGIME_CALM (Strict requires NORMAL only)")
                        logger.info(
                            f"[STAGE 1 LOOSENED RULE ACTIVE] BTCUSDT 4H signal generated under 'CALM' regime "
                            f"(in strict mode this signal would be filtered out)."
                        )

                    tick_signals.append({
                        "symbol": sym,
                        "signal_id": sig_id,
                        "action": "BUY",
                        "close_price": latest_close,
                        "entry_price": latest_close,
                        "highest_price": latest_close,
                        "trailing_stop_active": False,
                        "bars_held": 0,
                        "opened_at": datetime.datetime.utcnow(),
                        "stop_loss": sl_price,
                        "take_profit": tp_price,
                        "quantity": qty,
                        "risk_usd": risk_amount_usd,
                        "regime": latest_regime,
                        "trading_mode": self.trading_mode,
                        "is_loosened_trade": is_loosened,
                        "loosening_reason": "; ".join(loosening_reasons)
                    })

            except Exception as e:
                logger.error(f"Error evaluating live signal for {sym}: {e}")

        # Correlation Matrix Check among Candidate & Open Positions
        approved_signals = []
        for sig in tick_signals:
            # Audit log all candidate signals to DuckDB
            try:
                self.db.insert_signal(sig)
            except Exception as e:
                logger.debug(f"Signal audit logging to DuckDB: {e}")

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
                                if not np.isnan(corr_val):
                                    if corr_val > self.max_corr_threshold:
                                        logger.warning(
                                            f"PORTFOLIO CORRELATION BLOCK [{self.trading_mode.upper()}]: "
                                            f"{sym} correlation {corr_val:.2f} > threshold {self.max_corr_threshold:.2f} with active position {open_sym}."
                                        )
                                        too_correlated = True
                                        break
                                    elif self.trading_mode == "loose_stage1" and corr_val > 0.70:
                                        # Trade permitted exclusively due to relaxed correlation threshold (0.70 -> 0.80)
                                        sig["is_loosened_trade"] = True
                                        corr_reason = f"CORRELATION_RELAXED (Corr {corr_val:.2f} > 0.70 strict limit vs {open_sym})"
                                        if sig.get("loosening_reason"):
                                            sig["loosening_reason"] += "; " + corr_reason
                                        else:
                                            sig["loosening_reason"] = corr_reason
                                        logger.info(
                                            f"[STAGE 1 LOOSENED RULE ACTIVE] {sym} correlation {corr_val:.2f} > 0.70 strict threshold "
                                            f"permitted under loose_stage1 (limit {self.max_corr_threshold:.2f}) with active position {open_sym}."
                                        )
                if too_correlated:
                    continue

            # Combined Open Portfolio Dollar Risk Check
            current_open_risk = sum(p.get("risk_usd", 0.0) for p in self.open_positions.values())
            if (current_open_risk + sig["risk_usd"]) / current_equity > self.max_portfolio_risk_pct:
                logger.warning(f"PORTFOLIO MAX RISK BLOCK: Combined risk {(current_open_risk + sig['risk_usd'])/current_equity:.2%} exceeds max limit {self.max_portfolio_risk_pct:.2%}.")
                continue

            if sig.get("is_loosened_trade"):
                logger.info(
                    f"*** [STAGE 1 LOOSENED TRADE APPROVED] *** Symbol: {sym} | "
                    f"Allowed Exclusively Due To: {sig['loosening_reason']} | Price: ${sig['close_price']:,.2f} | Action: BUY"
                )
            else:
                logger.info(
                    f"[STRICT RULE TRADE APPROVED] Symbol: {sym} | Price: ${sig['close_price']:,.2f} | Action: BUY"
                )

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
        """Persists paper trade orders and positions directly into DuckDB (clean, no CSV flooding)."""
        now_dt = datetime.datetime.utcnow()
        sym = sig["symbol"]
        cfg_asset = self.asset_configs.get(sym, {}).get("asset", {})
        
        trade_record = {
            "trade_id": sig.get("signal_id", f"paper_{now_dt.strftime('%Y%m%d_%H%M%S')}"),
            "symbol": sym,
            "strategy": f"portfolio_paper_v5[{self.trading_mode}]",
            "base_timeframe": cfg_asset.get("base_timeframe", "1h"),
            "htf_timeframe": cfg_asset.get("htf_timeframe", "4h"),
            "entry_time": now_dt,
            "entry_price": float(sig["close_price"]),
            "exit_time": now_dt,
            "exit_price": float(sig["close_price"]),
            "action": sig["action"],
            "quantity": float(sig["quantity"]),
            "position_value_usd": float(sig["quantity"]) * float(sig["close_price"]),
            "pnl_usd": 0.0,
            "pnl_pct": 0.0,
            "r_multiple": 0.0,
            "volatility_regime": str(sig.get("regime", "NORMAL")),
            "risk_pct_used": 0.005,
            "entry_reason": f"Paper Order Placed ({sig.get('loosening_reason', '') or 'Standard Strategy'})",
            "exit_reason": "OPEN_PAPER_POSITION",
            "trading_mode": self.trading_mode,
            "is_loosened_trade": bool(sig.get("is_loosened_trade", False)),
            "loosening_reason": str(sig.get("loosening_reason", ""))
        }
        
        try:
            self.db.insert_trade_record(trade_record, source="paper_trade")
            self.db.upsert_position({
                "symbol": sym,
                "signal_id": sig.get("signal_id", ""),
                "action": sig.get("action", "BUY"),
                "entry_price": float(sig["close_price"]),
                "stop_loss": float(sig.get("stop_loss", 0.0)),
                "take_profit": float(sig.get("take_profit", 0.0)),
                "quantity": float(sig["quantity"]),
                "risk_usd": float(sig.get("risk_usd", 0.0)),
                "regime": str(sig.get("regime", "NORMAL")),
                "opened_at": now_dt
            })
            logger.info(
                f"Persisted paper trade to DuckDB: {sym} {sig['action']} Qty: {sig['quantity']:.4f} "
                f"| Mode: {self.trading_mode} | Loosened: {sig.get('is_loosened_trade', False)}"
            )
        except Exception as e:
            logger.error(f"Error persisting paper trade to DuckDB: {e}", exc_info=True)

    def get_daily_summary(self) -> Dict[str, Any]:
        """Generates comprehensive daily paper trading summary report and saves snapshot to DuckDB."""
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
            "trading_mode": self.trading_mode,
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

        # Persist snapshot to DuckDB
        try:
            self.db.insert_portfolio_snapshot(summary)
        except Exception as e:
            logger.debug(f"Portfolio snapshot logging to DuckDB: {e}")

        print("\n" + "=" * 90)
        print("          ALPACA PAPER TRADING DAILY SUMMARY REPORT - PORTFOLIO V5.0          ")
        print("=" * 90)
        print(f"  Active Trading Mode   : {self.trading_mode.upper()}")
        if self.trading_mode == "loose_stage1":
            print(f"  Profile Status        : STAGE 1 TEMPORARY LOOSENING (BTC: ['NORMAL', 'CALM'], Max Corr: {self.max_corr_threshold:.2f})")
        else:
            print(f"  Profile Status        : STRICT LOCKED BASELINE (BTC: ['NORMAL'], Max Corr: 0.70)")
        print(f"  Account Equity        : ${equity:,.2f}")
        print(f"  Starting Daily Equity : ${self.daily_start_equity:,.2f}")
        print(f"  Daily PnL ($ / %)     : ${pnl_usd:+,.2f} ({pnl_pct:+.2f}%)")
        print(f"  Current Drawdown      : {dd_pct:.2f}% (Peak: ${self.peak_portfolio_equity:,.2f})")
        print(f"  Cash / Buying Power   : ${cash:,.2f} / ${buying_power:,.2f}")
        print(f"  Active Positions      : {len(positions)}")
        for pos in positions:
            print(f"    -> {pos.get('symbol'):<8} | Qty: {pos.get('qty')} | Value: ${float(pos.get('market_value', 0)):,.2f} | PnL: ${float(pos.get('unrealized_pl', 0)):+,.2f}")

        # Basic performance tracking audit comparing strict vs loose
        try:
            with self.db.get_connection() as con:
                stats = con.execute("""
                    SELECT 
                        trading_mode, 
                        is_loosened_trade, 
                        COUNT(*) as cnt, 
                        COALESCE(SUM(pnl_usd), 0.0) as sum_pnl
                    FROM trades
                    WHERE source = 'paper_trade'
                    GROUP BY trading_mode, is_loosened_trade
                    ORDER BY trading_mode ASC, is_loosened_trade ASC
                """).df()
            if not stats.empty:
                print("\n  Mode Execution & Performance Tracking Audit (Strict vs Loosened):")
                for _, r in stats.iterrows():
                    m = str(r['trading_mode']).upper()
                    t_type = "Loosened (Stage 1 only)" if r['is_loosened_trade'] else "Strict Baseline Rules"
                    print(f"    - [{m}] {t_type:<26} : {int(r['cnt'])} trades | Total PnL: ${r['sum_pnl']:+,.2f}")
        except Exception as e:
            logger.debug(f"Mode summary query: {e}")

        print("=" * 90 + "\n")

        return summary

    def activate_kill_switch(self) -> Dict[str, Any]:
        """Emergency Flatten All Positions and Cancel Orders."""
        logger.warning("ACTIVATING SYSTEM KILL SWITCH VIA PORTFOLIO PAPER TRADER...")
        res = self.alpaca.flatten_all_positions()
        self.open_positions.clear()
        try:
            self.db.clear_positions()
        except Exception as e:
            logger.debug(f"DuckDB clear positions: {e}")
        return res
