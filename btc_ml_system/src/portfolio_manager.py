"""
Portfolio Manager & Multi-Asset Combined Backtest Engine for btc_ml_system.
Implements Simple Portfolio Mode with:
1. Independent capital allocation weights across Equities (50%), BTC (25%), and ETH (25%).
2. Portfolio-level risk controls: Max Total Portfolio Risk, Daily Loss Limit, Max Drawdown Circuit Breaker.
3. Rolling Pairwise Correlation Filter: Blocks new positions if correlation with open positions > threshold.
4. Unified multi-asset equity curve calculation and reporting.
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
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

logger = logging.getLogger("btc_ml_system.portfolio_manager")


class PortfolioManager:
    """
    Manages multi-asset portfolio capital allocation, cross-asset correlation filtering,
    portfolio risk controls, and combined performance reporting.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.port_cfg = config.get("portfolio", {})
        self.initial_capital = float(self.port_cfg.get("initial_capital", 100000.0))
        
        # Capital Allocation Weights
        self.weights = self.port_cfg.get("weights", {
            "equity_basket": 0.50,
            "BTCUSDT": 0.25,
            "ETHUSDT": 0.25
        })
        
        # Risk Limits
        self.risk_cfg = self.port_cfg.get("risk_limits", {})
        self.max_portfolio_risk_pct = float(self.risk_cfg.get("max_portfolio_risk_pct", 0.03))
        self.max_daily_loss_pct = float(self.risk_cfg.get("max_daily_loss_pct", 0.02))
        self.max_drawdown_limit_pct = float(self.risk_cfg.get("max_drawdown_limit_pct", 0.10))
        
        # Correlation Control
        self.corr_cfg = self.port_cfg.get("correlation_control", {})
        self.corr_enabled = bool(self.corr_cfg.get("enabled", True))
        self.corr_lookback = int(self.corr_cfg.get("lookback_window", 30))
        self.max_corr_threshold = float(self.corr_cfg.get("max_correlation_threshold", 0.70))

    def run_portfolio_backtest(self, asset_configs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Executes a synchronized multi-asset portfolio simulation.
        asset_configs mapping e.g.:
        {
          'AAPL': config_dict,
          'MSFT': config_dict,
          'NVDA': config_dict,
          'TSLA': config_dict,
          'AMZN': config_dict,
          'BTCUSDT': config_dict,
          'ETHUSDT': config_dict
        }
        """
        logger.info("Initializing multi-asset portfolio dataset and strategy pipelines...")

        # 1. Load Data & Evaluate Signals per Asset
        asset_data = {}
        for sym, cfg in asset_configs.items():
            years = cfg.get("data", {}).get("history_years", 2)
            days_back = years * 365
            provider = DataProvider(cfg)
            df_ltf = provider.fetch_data(symbol=sym, interval=cfg['asset']['base_timeframe'], days_back=days_back)
            df_htf = provider.fetch_data(symbol=sym, interval=cfg['asset']['htf_timeframe'], days_back=days_back * 2)

            vol_classifier = VolatilityRegimeClassifier(cfg)
            df_reg = vol_classifier.predict_regimes(df_ltf)

            session_filter = SessionFilter(cfg)
            df_sess = session_filter.apply_filter(df_reg)

            strategy_engine = StrategyFactory.get_strategy(cfg)
            df_strat = strategy_engine.evaluate_signals(df_sess, df_htf)

            signal_engine = SignalEngine(cfg)
            df_strat["atr"] = signal_engine.compute_atr(df_strat)

            # Precalculate returns for correlation checks
            df_strat["returns"] = df_strat["close"].pct_change().fillna(0.0)

            asset_data[sym] = {
                "config": cfg,
                "df": df_strat.sort_values("open_time").reset_index(drop=True),
                "sl_atr_mult": signal_engine.sl_atr_mult,
                "tp_atr_mult": signal_engine.tp_atr_mult,
                "enable_trailing_stop": cfg.get("exit_rules", {}).get("enable_trailing_stop", False),
                "trailing_trigger_pct": cfg.get("exit_rules", {}).get("trailing_trigger_pct", 0.02),
                "trailing_dist_pct": cfg.get("exit_rules", {}).get("trailing_dist_pct", 0.015),
            }

        # 2. Assign Allocation Weights per Asset
        equity_symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]
        equity_weight_total = float(self.weights.get("equity_basket", 0.50))
        per_stock_weight = equity_weight_total / len(equity_symbols)

        asset_allocations = {}
        for sym in asset_data:
            if sym in equity_symbols:
                asset_allocations[sym] = per_stock_weight
            else:
                asset_allocations[sym] = float(self.weights.get(sym, 0.25))

        # 3. Create Unified Hourly Time Grid
        all_timestamps = set()
        for sym, d in asset_data.items():
            ts_set = set(pd.to_datetime(d["df"]["open_time"], utc=True))
            all_timestamps.update(ts_set)

        sorted_timestamps = sorted(list(all_timestamps))
        
        # Index dataframes by open_time for O(1) lookup
        indexed_dfs = {}
        for sym, d in asset_data.items():
            df_c = d["df"].copy()
            df_c["open_time"] = pd.to_datetime(df_c["open_time"], utc=True)
            indexed_dfs[sym] = df_c.set_index("open_time")

        # 4. Initialize Portfolio Simulation State
        portfolio_capital = self.initial_capital
        cash = portfolio_capital
        peak_equity = portfolio_capital

        open_positions = {}  # sym -> position_dict
        completed_trades = []  # list of trade dicts
        equity_curve = []  # list of {timestamp, equity, drawdown, cash, open_count}

        blocked_by_correlation_count = 0
        blocked_by_portfolio_risk_count = 0
        blocked_by_circuit_breaker_count = 0

        current_day = None
        day_start_equity = portfolio_capital

        # Track latest prices for continuous mark-to-market across non-trading hours
        latest_prices = {sym: float(d["df"]["open"].iloc[0]) for sym, d in asset_data.items()}

        # 5. Synchronized Timeline Simulation Loop
        for t in sorted_timestamps:
            # Update latest prices for assets active at timestamp t
            for sym, df_idx in indexed_dfs.items():
                if t in df_idx.index:
                    latest_prices[sym] = float(df_idx.loc[t]["close"])

            # Check for new day to update daily loss baseline
            t_date = t.date()
            if current_day != t_date:
                current_day = t_date
                day_start_equity = portfolio_capital

            # A. Mark to Market Open Positions & Check Exits
            closed_in_this_step = []

            for sym, pos in list(open_positions.items()):
                df_sym = indexed_dfs[sym]
                if t in df_sym.index:
                    row = df_sym.loc[t]
                    curr_open = float(row["open"])
                    curr_high = float(row["high"])
                    curr_low = float(row["low"])
                    curr_close = float(row["close"])

                    pos["bars_held"] += 1
                    pos["highest_price"] = max(pos["highest_price"], curr_high)

                    # Check Profit Runner Activation (Part B)
                    if pos.get("enable_profit_runner", False) and not pos["trailing_active"]:
                        dollar_risk = abs(pos["entry_price"] - pos["initial_sl_price"])
                        current_r = (pos["highest_price"] - pos["entry_price"]) / dollar_risk if dollar_risk > 0 else 0.0
                        if current_r >= pos.get("profit_runner_trigger_r", 2.0):
                            pos["trailing_active"] = True
                            pos["trailing_dist_pct"] = pos.get("profit_runner_trail_dist_pct", 0.015)
                            pos["sl_price"] = max(pos["sl_price"], pos["highest_price"] * (1.0 - pos["trailing_dist_pct"]))

                    # Trailing stop check
                    if pos["enable_trailing_stop"] and not pos["trailing_active"]:
                        profit_ratio = (pos["highest_price"] - pos["entry_price"]) / pos["entry_price"]
                        if profit_ratio >= pos["trailing_trigger_pct"]:
                            pos["trailing_active"] = True
                            pos["sl_price"] = max(pos["sl_price"], pos["highest_price"] * (1.0 - pos["trailing_dist_pct"]))

                    if pos["trailing_active"]:
                        new_trail_sl = pos["highest_price"] * (1.0 - pos["trailing_dist_pct"])
                        pos["sl_price"] = max(pos["sl_price"], new_trail_sl)

                    # Check Early Loss Cut / Stagnation Exit (Part B)
                    hit_early_cut = False
                    if pos.get("enable_early_loss_cut", False) and pos["bars_held"] >= pos.get("early_loss_cut_bars", 5) and not pos["trailing_active"]:
                        dollar_risk = abs(pos["entry_price"] - pos["initial_sl_price"])
                        current_r = (curr_close - pos["entry_price"]) / dollar_risk if dollar_risk > 0 else 0.0
                        if current_r <= pos.get("early_loss_cut_max_pnl_r", 0.0):
                            hit_early_cut = True

                    hit_sl = curr_low <= pos["sl_price"]
                    hit_tp = curr_high >= pos["tp_price"]

                    if hit_sl or hit_tp or hit_early_cut:
                        if hit_early_cut and not hit_sl:
                            exit_price = curr_close
                            reason = "EARLY_LOSS_CUT"
                        elif hit_sl:
                            exit_price = pos["sl_price"]
                            reason = "PROFIT_RUNNER_HIT" if (pos.get("enable_profit_runner", False) and pos["trailing_active"]) else ("TRAILING_SL_HIT" if pos["trailing_active"] else "SL_HIT")
                        else:
                            exit_price = pos["tp_price"]
                            reason = "PT_HIT"

                        slip_bps = asset_configs[sym].get("execution", {}).get("slippage_bps", 5)
                        comm_bps = asset_configs[sym].get("execution", {}).get("commission_bps", 10)
                        slip = slip_bps / 10000.0
                        comm = comm_bps / 10000.0

                        exit_price_adj = exit_price * (1.0 - slip)
                        raw_pnl = (exit_price_adj - pos["entry_price"]) / pos["entry_price"]
                        net_pnl_pct = raw_pnl - comm

                        pnl_dollars = pos["position_value"] * net_pnl_pct
                        cash += pos["position_value"] + pnl_dollars
                        portfolio_capital += pnl_dollars

                        completed_trades.append({
                            "symbol": sym,
                            "entry_time": pos["entry_time"],
                            "exit_time": t,
                            "entry_price": pos["entry_price"],
                            "exit_price": exit_price_adj,
                            "position_value": pos["position_value"],
                            "pnl_usd": pnl_dollars,
                            "pnl_pct": net_pnl_pct,
                            "r_multiple": pnl_dollars / pos["dollar_risk"] if pos["dollar_risk"] > 0 else net_pnl_pct / 0.005,
                            "duration_bars": pos["bars_held"],
                            "reason": reason,
                            "volatility_regime": pos["volatility_regime"]
                        })
                        closed_in_this_step.append(sym)

            for sym in closed_in_this_step:
                del open_positions[sym]

            # Recalculate Current Portfolio Equity using latest_prices for active positions
            current_portfolio_equity = cash + sum(pos["quantity"] * latest_prices[pos["symbol"]] for pos in open_positions.values())
            peak_equity = max(peak_equity, current_portfolio_equity)
            current_drawdown = (peak_equity - current_portfolio_equity) / peak_equity if peak_equity > 0 else 0.0

            # Record Equity Curve
            equity_curve.append({
                "timestamp": t,
                "equity": current_portfolio_equity,
                "cash": cash,
                "drawdown_pct": current_drawdown * 100.0,
                "open_positions": len(open_positions)
            })

            # B. Evaluate Entry Signals across Assets at time t
            daily_loss_pct = (day_start_equity - current_portfolio_equity) / day_start_equity if day_start_equity > 0 else 0.0

            for sym, d in asset_data.items():
                if sym in open_positions:
                    continue  # Already in position for this asset

                df_sym = indexed_dfs[sym]
                if t not in df_sym.index:
                    continue

                row = df_sym.loc[t]

                # Extract filter flags
                is_vol_favorable = bool(row.get("vol_regime_favorable", True))
                is_session_valid = bool(row.get("session_valid", True))
                dir_valid = bool(row.get("direction_valid", False))
                htf_valid = bool(row.get("htf_trend_valid", True))

                if not (is_vol_favorable and is_session_valid and dir_valid and htf_valid):
                    continue

                # Portfolio Circuit Breaker Check
                if current_drawdown >= self.max_drawdown_limit_pct:
                    blocked_by_circuit_breaker_count += 1
                    logger.debug(f"[{t}] Portfolio Circuit Breaker active ({current_drawdown:.2%}). Blocked entry on {sym}.")
                    continue

                # Portfolio Daily Loss Limit Check
                if daily_loss_pct >= self.max_daily_loss_pct:
                    blocked_by_circuit_breaker_count += 1
                    logger.debug(f"[{t}] Portfolio Daily Loss Limit reached ({daily_loss_pct:.2%}). Blocked entry on {sym}.")
                    continue

                # Position Risk Calculation
                entry_price = float(row["close"])
                atr_val = float(row["atr"]) if not pd.isna(row["atr"]) else entry_price * 0.01

                vol_regime_str = str(row.get("volatility_regime", "NORMAL"))
                regime_params = asset_configs[sym].get("volatility_regime", {}).get("regime_params", {}).get(vol_regime_str, {})
                sl_m = float(regime_params.get("sl_atr_multiplier", d["sl_atr_mult"]))
                tp_m = float(regime_params.get("tp_atr_multiplier", d["tp_atr_mult"]))
                tr_trig = regime_params.get("trailing_trigger_pct", d["trailing_trigger_pct"])
                tr_dist = regime_params.get("trailing_dist_pct", d["trailing_dist_pct"])

                sl_price = entry_price - (sl_m * atr_val)
                tp_price = entry_price + (tp_m * atr_val)

                # Sub-capital for this asset based on allocation weight
                allocated_sub_capital = self.initial_capital * asset_allocations[sym]
                risk_pct = float(asset_configs[sym].get("position_sizer", {}).get("risk_pct", 0.005))
                dollar_risk = allocated_sub_capital * risk_pct

                stop_dist = abs(entry_price - sl_price)
                if stop_dist <= 0:
                    continue

                qty = dollar_risk / stop_dist
                pos_value = qty * entry_price

                # Portfolio Max Total Risk Check
                current_open_risk = sum(p["dollar_risk"] for p in open_positions.values())
                if (current_open_risk + dollar_risk) > (self.max_portfolio_risk_pct * current_portfolio_equity):
                    blocked_by_portfolio_risk_count += 1
                    logger.debug(f"[{t}] Portfolio Max Risk Exceeded on {sym}. OpenRisk=${current_open_risk:.2f} + NewRisk=${dollar_risk:.2f}")
                    continue

                # Correlation Filter Check
                if self.corr_enabled and len(open_positions) > 0:
                    is_correlated = False
                    for open_sym in open_positions:
                        corr_val = self._compute_pairwise_correlation(indexed_dfs, sym, open_sym, t)
                        if corr_val > self.max_corr_threshold:
                            is_correlated = True
                            blocked_by_correlation_count += 1
                            logger.info(f"[{t}] Signal on {sym} REJECTED by Correlation Filter -> Pairwise correlation with open position {open_sym} is {corr_val:.2f} (Threshold: {self.max_corr_threshold:.2f})")
                            break
                    if is_correlated:
                        continue

                # Execute Trade Entry
                slip_bps = asset_configs[sym].get("execution", {}).get("slippage_bps", 5)
                entry_price_adj = entry_price * (1.0 + (slip_bps / 10000.0))

                exit_rules_cfg = asset_configs[sym].get("exit_rules", {})

                open_positions[sym] = {
                    "symbol": sym,
                    "entry_time": t,
                    "entry_price": entry_price_adj,
                    "quantity": qty,
                    "position_value": pos_value,
                    "dollar_risk": dollar_risk,
                    "initial_sl_price": sl_price,
                    "sl_price": sl_price,
                    "tp_price": tp_price,
                    "bars_held": 0,
                    "highest_price": entry_price_adj,
                    "trailing_active": False,
                    "enable_trailing_stop": d["enable_trailing_stop"],
                    "trailing_trigger_pct": tr_trig,
                    "trailing_dist_pct": tr_dist,
                    "enable_early_loss_cut": bool(exit_rules_cfg.get("enable_early_loss_cut", False)),
                    "early_loss_cut_bars": int(exit_rules_cfg.get("early_loss_cut_bars", 5)),
                    "early_loss_cut_max_pnl_r": float(exit_rules_cfg.get("early_loss_cut_max_pnl_r", 0.0)),
                    "enable_profit_runner": bool(exit_rules_cfg.get("enable_profit_runner", False)),
                    "profit_runner_trigger_r": float(exit_rules_cfg.get("profit_runner_trigger_r", 2.0)),
                    "profit_runner_trail_dist_pct": float(exit_rules_cfg.get("profit_runner_trail_dist_pct", 0.015)),
                    "volatility_regime": str(row.get("volatility_regime", "NORMAL"))
                }
                cash -= pos_value

        # 6. Aggregate Performance Metrics
        portfolio_metrics = self._calculate_performance_metrics(
            self.initial_capital, portfolio_capital, completed_trades, equity_curve,
            blocked_by_correlation_count, blocked_by_portfolio_risk_count, blocked_by_circuit_breaker_count, asset_allocations
        )

        return portfolio_metrics

    def _compute_pairwise_correlation(self, indexed_dfs: Dict[str, pd.DataFrame], sym1: str, sym2: str, current_time: pd.Timestamp) -> float:
        """Calculates rolling return correlation between two assets up to current_time."""
        try:
            df1 = indexed_dfs[sym1]
            df2 = indexed_dfs[sym2]

            sub1 = df1.loc[:current_time]["returns"].tail(self.corr_lookback)
            sub2 = df2.loc[:current_time]["returns"].tail(self.corr_lookback)

            if len(sub1) < 10 or len(sub2) < 10:
                return 0.0

            # Align on timestamps
            combined = pd.concat([sub1, sub2], axis=1, join="inner").dropna()
            if len(combined) < 10:
                return 0.0

            corr_matrix = np.corrcoef(combined.iloc[:, 0], combined.iloc[:, 1])
            val = corr_matrix[0, 1]
            return float(val) if not np.isnan(val) else 0.0
        except Exception:
            return 0.0

    def _calculate_performance_metrics(
        self,
        initial_capital: float,
        final_capital: float,
        trades: List[Dict[str, Any]],
        equity_curve: List[Dict[str, Any]],
        blocked_corr: int,
        blocked_risk: int,
        blocked_cb: int,
        allocations: Dict[str, float]
    ) -> Dict[str, Any]:
        """Calculates full portfolio and individual strategy performance metrics."""
        total_trades = len(trades)
        wins = [t for t in trades if t["pnl_usd"] > 0]
        losses = [t for t in trades if t["pnl_usd"] <= 0]

        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
        gross_profit = sum(t["pnl_usd"] for t in wins)
        gross_loss = abs(sum(t["pnl_usd"] for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

        total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100.0

        # Max Drawdown from equity curve
        eq_df = pd.DataFrame(equity_curve)
        max_dd_pct = float(eq_df["drawdown_pct"].max()) if not eq_df.empty else 0.0

        # Individual Asset Performance Breakdown
        asset_breakdown = {}
        all_symbols = list(set([t["symbol"] for t in trades] + list(allocations.keys())))
        for sym in all_symbols:
            sym_trades = [t for t in trades if t["symbol"] == sym]
            sym_wins = [t for t in sym_trades if t["pnl_usd"] > 0]
            sym_losses = [t for t in sym_trades if t["pnl_usd"] <= 0]
            sym_count = len(sym_trades)
            sym_wr = len(sym_wins) / sym_count if sym_count > 0 else 0.0
            sym_gp = sum(t["pnl_usd"] for t in sym_wins)
            sym_gl = abs(sum(t["pnl_usd"] for t in sym_losses))
            sym_pf = sym_gp / sym_gl if sym_gl > 0 else (sym_gp if sym_gp > 0 else 1.0)
            sym_pnl = sum(t["pnl_usd"] for t in sym_trades)
            sub_cap = initial_capital * allocations.get(sym, 0.10)
            sym_ret = (sym_pnl / sub_cap) * 100.0 if sub_cap > 0 else 0.0

            asset_breakdown[sym] = {
                "total_trades": sym_count,
                "win_rate": sym_wr,
                "total_pnl_usd": sym_pnl,
                "return_pct": sym_ret,
                "profit_factor": sym_pf
            }

        # Component Performance Breakdown (Equities Basket, BTC 4H, ETH 1H)
        equity_symbols = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]
        equity_trades = [t for t in trades if t["symbol"] in equity_symbols]
        eq_wins = [t for t in equity_trades if t["pnl_usd"] > 0]
        eq_losses = [t for t in equity_trades if t["pnl_usd"] <= 0]
        eq_count = len(equity_trades)
        eq_wr = len(eq_wins) / eq_count if eq_count > 0 else 0.0
        eq_gp = sum(t["pnl_usd"] for t in eq_wins)
        eq_gl = abs(sum(t["pnl_usd"] for t in eq_losses))
        eq_pf = eq_gp / eq_gl if eq_gl > 0 else (eq_gp if eq_gp > 0 else 1.0)
        eq_pnl = sum(t["pnl_usd"] for t in equity_trades)
        eq_sub_cap = initial_capital * self.weights.get("equity_basket", 0.50)
        eq_ret = (eq_pnl / eq_sub_cap) * 100.0 if eq_sub_cap > 0 else 0.0

        component_breakdown = {
            "Equity Basket (V4.3 Frozen)": {
                "weight_pct": self.weights.get("equity_basket", 0.50) * 100.0,
                "allocated_capital": eq_sub_cap,
                "total_trades": eq_count,
                "win_rate": eq_wr,
                "total_pnl_usd": eq_pnl,
                "return_pct": eq_ret,
                "profit_factor": eq_pf
            },
            "BTCUSDT (4H NORMAL Vol Filter)": asset_breakdown.get("BTCUSDT", {
                "total_trades": 0, "win_rate": 0.0, "total_pnl_usd": 0.0, "return_pct": 0.0, "profit_factor": 1.0
            }),
            "ETHUSDT (1H Clean Version)": asset_breakdown.get("ETHUSDT", {
                "total_trades": 0, "win_rate": 0.0, "total_pnl_usd": 0.0, "return_pct": 0.0, "profit_factor": 1.0
            })
        }
        # Add weights to BTC/ETH component dicts
        component_breakdown["BTCUSDT (4H NORMAL Vol Filter)"]["weight_pct"] = self.weights.get("BTCUSDT", 0.25) * 100.0
        component_breakdown["BTCUSDT (4H NORMAL Vol Filter)"]["allocated_capital"] = initial_capital * self.weights.get("BTCUSDT", 0.25)
        component_breakdown["ETHUSDT (1H Clean Version)"]["weight_pct"] = self.weights.get("ETHUSDT", 0.25) * 100.0
        component_breakdown["ETHUSDT (1H Clean Version)"]["allocated_capital"] = initial_capital * self.weights.get("ETHUSDT", 0.25)

        return {
            "initial_capital": initial_capital,
            "final_capital": final_capital,
            "total_return_pct": total_return_pct,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "max_drawdown_pct": max_dd_pct,
            "profit_factor": profit_factor,
            "blocked_by_correlation_count": blocked_corr,
            "blocked_by_portfolio_risk_count": blocked_risk,
            "blocked_by_circuit_breaker_count": blocked_cb,
            "component_breakdown": component_breakdown,
            "asset_breakdown": asset_breakdown,
            "equity_curve": equity_curve,
            "trades": trades
        }
