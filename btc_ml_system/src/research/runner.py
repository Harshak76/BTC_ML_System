"""
Quantitative Research Simulation Runner for BTC-ML System V2.
Orchestrates offline, non-broker historical simulations for research strategies.
Enforces completed-candle filtering, next-bar open execution, realistic transaction costs,
unit standardization, stop anchoring, intrabar collision handling, session filtering,
and persistent experiment tracking.
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
        risk_per_trade_pct: float = 0.005,  # 0.5% risk
        enforce_equity_sessions: bool = True,
        cost_multiplier: float = 1.0,
        execution_delay_bars: int = 0,
        drop_trade_prob: float = 0.0,
        random_seed: int = 42
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.max_open_positions = max_open_positions
        self.risk_per_trade_pct = risk_per_trade_pct
        self.enforce_equity_sessions = enforce_equity_sessions
        self.cost_multiplier = cost_multiplier
        self.execution_delay_bars = execution_delay_bars
        self.drop_trade_prob = drop_trade_prob
        self.rng = np.random.RandomState(random_seed)
        self.execution = strategy.execution_assumptions

    @staticmethod
    def is_crypto_symbol(symbol: str) -> bool:
        """Determines if the asset is a cryptocurrency (trades 24/7 continuous)."""
        s = symbol.upper()
        return "USDT" in s or s in ("BTC", "ETH", "BTCUSDT", "ETHUSDT")

    def is_market_session_open(self, symbol: str, timestamp: pd.Timestamp) -> bool:
        """
        Checks whether the market session is open for execution.
        - Crypto (BTC, ETH, etc.): Continuous 24/7/365 trading.
        - Equities (AAPL, MSFT, etc.): Regular session Monday-Friday, 14:00-21:00 UTC (9:30 AM - 4:00 PM ET).
        """
        if self.is_crypto_symbol(symbol):
            return True

        if not self.enforce_equity_sessions:
            return True

        # Equities: Weekends are closed (Saturday=5, Sunday=6)
        if timestamp.weekday() >= 5:
            return False

        # Equities: US Regular Market Hours in UTC (14:00 to 21:00 UTC)
        hour = timestamp.hour
        return 14 <= hour < 21

    def get_transaction_costs(self, symbol: str) -> Tuple[float, float]:
        """
        Returns (slippage_bps, commission_bps) for entry/exit.
        - Equities: 2 bps slippage entry, 2 bps slippage exit, 0 bps commission.
        - Crypto: 5 bps slippage entry, 5 bps slippage exit, 10 bps commission.
        """
        is_crypto = self.is_crypto_symbol(symbol)
        base_slip = 5.0 if is_crypto else 2.0
        base_comm = 10.0 if is_crypto else 0.0

        slip_bps = base_slip * self.cost_multiplier
        comm_bps = base_comm * self.cost_multiplier
        return slip_bps, comm_bps

    def run_simulation(
        self,
        data_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """
        Runs multi-asset chronological simulation.
        
        Execution Protocol:
        1. At bar close t, evaluate strategy signals on completed candles.
        2. Queue pending orders for entry on bar t+1 open (or after execution_delay_bars).
        3. Fills incur asset-specific slippage (5 bps crypto, 2 bps equities) at open.
        4. ATR stops and take-profits are anchored to actual simulated fill price.
        5. Conservative collision rule: if both SL and TP are touched in the same bar, assume SL hit first.
        6. Trailing stops update strictly without lookahead bias using prior bar high.
        7. Equities only execute during market sessions (14:00-21:00 UTC, Mon-Fri); crypto is 24/7 continuous.
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

        # Mark tracking for research integrity
        actual_observations = {sym: 0 for sym in prepared_dfs}
        carried_forward_marks = {sym: 0 for sym in prepared_dfs}
        current_mark_age = {sym: 0 for sym in prepared_dfs}
        max_mark_age = {sym: 0 for sym in prepared_dfs}
        signal_counts = {sym: 0 for sym in prepared_dfs}
        execution_counts = {sym: 0 for sym in prepared_dfs}

        # 3. Chronological Step Loop
        for t in sorted_timeline:
            # A. Update latest prices for available assets
            for sym, df in prepared_dfs.items():
                if t in df.index:
                    latest_prices[sym] = float(df.loc[t, "close"])
                    actual_observations[sym] += 1
                    current_mark_age[sym] = 0
                else:
                    carried_forward_marks[sym] += 1
                    current_mark_age[sym] += 1
                    if current_mark_age[sym] > max_mark_age[sym]:
                        max_mark_age[sym] = current_mark_age[sym]

            # Current portfolio equity mark-to-market
            pos_equity = sum(pos["quantity"] * latest_prices[pos["symbol"]] for pos in open_positions.values())
            current_equity = cash + pos_equity

            # B. Execute Pending Orders from t-1 on current bar Open
            for sym in list(pending_orders.keys()):
                df_sym = prepared_dfs[sym]
                if t in df_sym.index and sym not in open_positions:
                    order = pending_orders[sym]

                    # Check execution delay
                    if order.get("delay_bars_remaining", 0) > 0:
                        order["delay_bars_remaining"] -= 1
                        continue

                    # Check market session availability
                    if not self.is_market_session_open(sym, t):
                        # Equity market closed; order remains queued for next open session
                        continue

                    # Remove from pending queue
                    del pending_orders[sym]

                    # Check simulated missed trades (robustness stress testing)
                    if self.drop_trade_prob > 0.0 and self.rng.uniform(0.0, 1.0) < self.drop_trade_prob:
                        logger.info(f"Stress test: Missed trade for {sym} at {t}")
                        continue

                    p_open = float(df_sym.loc[t, "open"])
                    slip_bps, _ = self.get_transaction_costs(sym)
                    fill_price = p_open * (1.0 + (slip_bps / 10000.0))

                    # Position sizing: risk-based or capital-capped
                    sl_dist = order["sl_distance"]
                    tp_dist = order["tp_distance"]

                    risk_usd = current_equity * self.risk_per_trade_pct
                    if sl_dist > 0 and order["signal_close"] > 0:
                        risk_pct = sl_dist / order["signal_close"]
                        calculated_size = risk_usd / risk_pct
                        max_cap = current_equity / self.max_open_positions
                        pos_val = min(calculated_size, max_cap)
                    else:
                        pos_val = current_equity / self.max_open_positions

                    pos_val = min(pos_val, cash)

                    if cash >= pos_val and len(open_positions) < self.max_open_positions and pos_val >= 10.0:
                        qty = pos_val / fill_price
                        cash -= pos_val

                        # Anchoring: stop loss and take profit are anchored to the actual fill price
                        actual_sl = fill_price - sl_dist
                        actual_tp = fill_price + tp_dist

                        execution_counts[sym] += 1

                        open_positions[sym] = {
                            "symbol": sym,
                            "entry_time": t,
                            "entry_price": fill_price,
                            "quantity": qty,
                            "position_value": pos_val,
                            "initial_sl": actual_sl,
                            "sl_price": actual_sl,
                            "tp_price": actual_tp,
                            "trailing_pct": order["trailing_pct"],
                            "highest_price": fill_price,
                            "bars_held": 0
                        }

            # C. Check Exits for Open Positions
            closed_this_bar = []
            for sym, pos in open_positions.items():
                df_sym = prepared_dfs[sym]
                if t in df_sym.index:
                    # Check market session availability for equities
                    if not self.is_market_session_open(sym, t):
                        # Equity market closed; position cannot exit until market opens
                        continue

                    row = df_sym.loc[t]
                    curr_open = float(row["open"])
                    curr_high = float(row["high"])
                    curr_low = float(row["low"])
                    curr_close = float(row["close"])
                    sig = int(row.get("signal", 0))

                    active_sl = pos["sl_price"]
                    active_tp = pos["tp_price"]

                    hit_sl = curr_low <= active_sl
                    hit_tp = curr_high >= active_tp
                    sig_exit = (sig == 0)

                    if hit_sl or hit_tp or sig_exit:
                        # Intrabar collision rule: if both SL and TP are touched in the same bar,
                        # assume the adverse excursion (stop loss) occurred first (conservative quantitative standard).
                        if hit_sl and hit_tp:
                            exit_p = curr_open if curr_open < active_sl else active_sl
                            reason = "STOP_LOSS_COLLISION"
                        elif hit_sl:
                            # Gap-through-stop behavior: if open is already below stop loss, fill at open
                            exit_p = curr_open if curr_open < active_sl else active_sl
                            reason = "STOP_LOSS"
                        elif hit_tp:
                            exit_p = active_tp
                            reason = "TAKE_PROFIT"
                        else:
                            exit_p = curr_close
                            reason = "SIGNAL_EXIT"

                        # Apply exit slippage and commission
                        slip_bps, comm_bps = self.get_transaction_costs(sym)

                        exit_adj = exit_p * (1.0 - (slip_bps / 10000.0))
                        gross_pnl_pct = (exit_adj - pos["entry_price"]) / pos["entry_price"]
                        net_pnl_pct = gross_pnl_pct - (comm_bps / 10000.0)

                        pnl_usd = pos["position_value"] * net_pnl_pct
                        cash += pos["position_value"] + pnl_usd

                        completed_trades.append({
                            "symbol": sym,
                            "entry_time": str(pos["entry_time"]),
                            "exit_time": str(t),
                            "entry_price": float(pos["entry_price"]),
                            "exit_price": float(exit_adj),
                            "position_value": float(pos["position_value"]),
                            "pnl_usd": float(pnl_usd),
                            "pnl_pct": float(net_pnl_pct * 100.0),  # Expressed in PERCENTAGE_POINTS
                            "bars_held": int(pos["bars_held"]),
                            "reason": reason
                        })
                        closed_this_bar.append(sym)
                    else:
                        # Position survives bar t: update trailing stop strictly after exit checks for bar t+1
                        pos["bars_held"] += 1
                        pos["highest_price"] = max(pos["highest_price"], curr_high)
                        if pos["trailing_pct"] and pos["trailing_pct"] > 0:
                            trail_sl = pos["highest_price"] * (1.0 - pos["trailing_pct"])
                            pos["sl_price"] = max(pos["sl_price"], trail_sl)

            for sym in closed_this_bar:
                del open_positions[sym]

            # D. Evaluate New Entry Signals at Bar Close t
            for sym, df_sym in prepared_dfs.items():
                if t in df_sym.index and sym not in open_positions and sym not in pending_orders:
                    row = df_sym.loc[t]
                    sig = int(row.get("signal", 0))
                    if sig == 1:
                        signal_counts[sym] += 1
                    if sig == 1 and len(open_positions) + len(pending_orders) < self.max_open_positions:
                        c_price = float(row["close"])
                        raw_sl = float(row.get("stop_loss_price", c_price * 0.98))
                        raw_tp = float(row.get("take_profit_price", c_price * 1.04))
                        trail_pct = float(row.get("trailing_stop_pct", 0.02))

                        sl_dist = max(c_price * 0.002, c_price - raw_sl)
                        tp_dist = max(c_price * 0.002, raw_tp - c_price)

                        pending_orders[sym] = {
                            "symbol": sym,
                            "signal_time": t,
                            "signal_close": c_price,
                            "sl_distance": sl_dist,
                            "tp_distance": tp_dist,
                            "trailing_pct": trail_pct,
                            "delay_bars_remaining": self.execution_delay_bars
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
        is_crypto_sim = any(self.is_crypto_symbol(s) for s in data_dict.keys())
        periods_per_year = (365 * 24) if is_crypto_sim else int(252 * 6.5)

        metrics = calculate_performance_metrics(
            trades=completed_trades,
            equity_curve=eq_series,
            initial_capital=self.initial_capital,
            periods_per_year=periods_per_year,
            is_crypto=is_crypto_sim
        )

        # 5. Extract Periodic Return Stream for CSCV/PBO
        eq_arr = np.array(eq_series)
        periodic_returns = np.diff(eq_arr) / np.maximum(eq_arr[:-1], 1.0) * 100.0  # in PERCENTAGE_POINTS

        # Unit enforcement validation
        self.strategy.validate_return_units(periodic_returns, ReturnUnit.PERCENTAGE_POINTS)

        total_steps = len(sorted_timeline)
        stale_pct = {
            sym: (carried_forward_marks[sym] / total_steps) * 100.0 if total_steps > 0 else 0.0
            for sym in prepared_dfs
        }
        mark_alignment_stats = {
            "total_timeline_steps": total_steps,
            "actual_observations": actual_observations,
            "carried_forward_marks": carried_forward_marks,
            "max_mark_age_hours": max_mark_age,
            "stale_valuation_pct": stale_pct,
            "signal_counts": signal_counts,
            "execution_counts": execution_counts
        }

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
            "mark_alignment_stats": mark_alignment_stats,
            "is_broker_connected": False  # Strictly offline
        }
