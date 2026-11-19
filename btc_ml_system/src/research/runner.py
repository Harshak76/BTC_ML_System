"""
Quantitative Research Simulation Runner for BTC-ML System V2.
Orchestrates offline, non-broker historical simulations for research strategies.
Enforces completed-candle filtering, next-bar open execution, realistic transaction costs,
unit standardization, and persistent experiment tracking.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from btc_ml_system.src.research.base import BaseResearchStrategy, ReturnUnit
from btc_ml_system.src.validation.metrics import calculate_performance_metrics, calculate_drawdown_series
from btc_ml_system.src.validation.experiment_tracker import ExperimentTracker

logger = logging.getLogger("btc_ml_system.research.runner")


class ResearchSimulationRunner:
    """
    Executes independent research backtests for candidate strategies.
    Guarantees zero broker connection and deterministic results.
    """

    def __init__(
        self,
        strategy: BaseResearchStrategy,
        initial_capital: float = 100000.0,
        max_open_positions: int = 4,
        risk_per_trade_pct: float = 0.005  # 0.5% risk
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.max_open_positions = max_open_positions
        self.risk_per_trade_pct = risk_per_trade_pct
        self.execution = strategy.execution_assumptions

    def run_simulation(
        self,
        data_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """
        Runs multi-asset chronological simulation.
        
        Execution Protocol:
        1. At bar close t, evaluate strategy signals on completed candles.
        2. Queue pending orders for entry on bar t+1 open.
        3. Fills incur slippage (5 bps crypto, 2 bps equities) at open.
        4. Exits trigger on SL/TP/Signal hit; commission deducted on exit.
        """
        if not data_dict:
            raise ValueError("data_dict cannot be empty.")

        # 1. Evaluate Signals on all assets
        prepared_dfs = {}
        all_timestamps = set()
        for sym, df in data_dict.items():
            self.strategy.validate_input_dataframe(df)
            sig_df = self.strategy.generate_signals(df)
            sig_df["dt_utc"] = pd.to_datetime(sig_df["open_time"], utc=True)
            sig_df = sig_df.set_index("dt_utc").sort_index()
            prepared_dfs[sym] = sig_df
            all_timestamps.update(sig_df.index)

        sorted_timeline = sorted(list(all_timestamps))
        if not sorted_timeline:
            raise ValueError("No valid timestamps found in market data.")

        # 2. Simulation State
        cash = self.initial_capital
        open_positions: Dict[str, Dict[str, Any]] = {}
        pending_orders: Dict[str, Dict[str, Any]] = {}
        completed_trades: List[Dict[str, Any]] = []
        equity_curve: List[Dict[str, Any]] = []

        latest_prices = {sym: float(prepared_dfs[sym]["close"].iloc[0]) for sym in prepared_dfs}

        # 3. Chronological Step Loop
        for t in sorted_timeline:
            # A. Update latest prices for available assets
            for sym, df in prepared_dfs.items():
                if t in df.index:
                    latest_prices[sym] = float(df.loc[t, "close"])

            # B. Execute Pending Orders from t-1 on current bar Open
            for sym in list(pending_orders.keys()):
                df_sym = prepared_dfs[sym]
                if t in df_sym.index and sym not in open_positions:
                    order = pending_orders.pop(sym)
                    p_open = float(df_sym.loc[t, "open"])

                    # Asset-specific slippage (2 bps for equities, 5 bps for crypto)
                    is_crypto = "USDT" in sym or sym in ("BTC", "ETH")
                    slip_bps = 5.0 if is_crypto else 2.0
                    fill_price = p_open * (1.0 + (slip_bps / 10000.0))

                    pos_val = order["position_size_usd"]
                    if cash >= pos_val and len(open_positions) < self.max_open_positions:
                        qty = pos_val / fill_price
                        cash -= pos_val
                        open_positions[sym] = {
                            "symbol": sym,
                            "entry_time": t,
                            "entry_price": fill_price,
                            "quantity": qty,
                            "position_value": pos_val,
                            "initial_sl": order["sl_price"],
                            "sl_price": order["sl_price"],
                            "tp_price": order["tp_price"],
                            "trailing_pct": order["trailing_pct"],
                            "highest_price": fill_price,
                            "bars_held": 0
                        }

            # C. Check Exits for Open Positions
            closed_this_bar = []
            for sym, pos in open_positions.items():
                df_sym = prepared_dfs[sym]
                if t in df_sym.index:
                    row = df_sym.loc[t]
                    curr_open = float(row["open"])
                    curr_high = float(row["high"])
                    curr_low = float(row["low"])
                    curr_close = float(row["close"])
                    sig = int(row.get("signal", 0))

                    pos["bars_held"] += 1
                    pos["highest_price"] = max(pos["highest_price"], curr_high)

                    # Update trailing stop
                    if pos["trailing_pct"] and pos["trailing_pct"] > 0:
                        trail_sl = pos["highest_price"] * (1.0 - pos["trailing_pct"])
                        pos["sl_price"] = max(pos["sl_price"], trail_sl)

                    hit_sl = curr_low <= pos["sl_price"]
                    hit_tp = curr_high >= pos["tp_price"]
                    sig_exit = (sig == 0)

                    if hit_sl or hit_tp or sig_exit:
                        if hit_sl:
                            exit_p = curr_open if curr_open < pos["sl_price"] else pos["sl_price"]
                            reason = "STOP_LOSS"
                        elif hit_tp:
                            exit_p = pos["tp_price"]
                            reason = "TAKE_PROFIT"
                        else:
                            exit_p = curr_close
                            reason = "SIGNAL_EXIT"

                        # Apply exit slippage and commission
                        is_crypto = "USDT" in sym or sym in ("BTC", "ETH")
                        slip_bps = 5.0 if is_crypto else 2.0
                        comm_bps = 10.0 if is_crypto else 0.0

                        exit_adj = exit_p * (1.0 - (slip_bps / 10000.0))
                        gross_pnl_pct = (exit_adj - pos["entry_price"]) / pos["entry_price"]
                        net_pnl_pct = gross_pnl_pct - (comm_bps / 10000.0)

                        pnl_usd = pos["position_value"] * net_pnl_pct
                        cash += pos["position_value"] + pnl_usd

                        completed_trades.append({
                            "symbol": sym,
                            "entry_time": pos["entry_time"],
                            "exit_time": t,
                            "entry_price": pos["entry_price"],
                            "exit_price": exit_adj,
                            "position_value": pos["position_value"],
                            "pnl_usd": pnl_usd,
                            "pnl_pct": net_pnl_pct * 100.0,  # Expressed in PERCENTAGE_POINTS
                            "bars_held": pos["bars_held"],
                            "reason": reason
                        })
                        closed_this_bar.append(sym)

            for sym in closed_this_bar:
                del open_positions[sym]

            # D. Evaluate New Entry Signals at Bar Close t
            for sym, df_sym in prepared_dfs.items():
                if t in df_sym.index and sym not in open_positions and sym not in pending_orders:
                    row = df_sym.loc[t]
                    sig = int(row.get("signal", 0))
                    if sig == 1 and len(open_positions) + len(pending_orders) < self.max_open_positions:
                        c_price = float(row["close"])
                        sl_price = float(row.get("stop_loss_price", c_price * 0.98))
                        tp_price = float(row.get("take_profit_price", c_price * 1.04))
                        trail_pct = float(row.get("trailing_stop_pct", 0.02))

                        # Sizing: fixed fraction of capital per trade
                        alloc_per_trade = self.initial_capital / self.max_open_positions
                        pending_orders[sym] = {
                            "symbol": sym,
                            "signal_time": t,
                            "position_size_usd": alloc_per_trade,
                            "sl_price": sl_price,
                            "tp_price": tp_price,
                            "trailing_pct": trail_pct
                        }

            # E. Mark to Market Equity
            pos_equity = sum(pos["quantity"] * latest_prices[pos["symbol"]] for pos in open_positions.values())
            total_equity = cash + pos_equity
            equity_curve.append({
                "timestamp": str(t),
                "equity": total_equity,
                "cash": cash,
                "open_positions_count": len(open_positions)
            })

        # 4. Compute Metrics
        eq_series = [step["equity"] for step in equity_curve]
        metrics = calculate_performance_metrics(
            trades=completed_trades,
            equity_curve=eq_series,
            initial_capital=self.initial_capital,
            periods_per_year=252 * 24,
            is_crypto=True
        )

        # 5. Extract Periodic Return Stream for CSCV/PBO
        eq_arr = np.array(eq_series)
        periodic_returns = np.diff(eq_arr) / np.maximum(eq_arr[:-1], 1.0) * 100.0  # in PERCENTAGE_POINTS

        # Unit enforcement validation
        self.strategy.validate_return_units(periodic_returns, ReturnUnit.PERCENTAGE_POINTS)

        return {
            "strategy_id": self.strategy.metadata.strategy_id,
            "strategy_name": self.strategy.metadata.strategy_name,
            "family": self.strategy.metadata.family.value,
            "version": self.strategy.metadata.version,
            "metrics": metrics,
            "total_trades": len(completed_trades),
            "trades": completed_trades,
            "equity_curve": equity_curve,
            "periodic_returns_pct": periodic_returns,
            "return_unit": ReturnUnit.PERCENTAGE_POINTS.value,
            "is_broker_connected": False  # Strictly offline
        }
