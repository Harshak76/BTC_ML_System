"""
Event-Driven Backtester Module.
Simulates execution with next-bar entry, conservative intrabar resolution,
and comprehensive performance reporting (Net return, CAGR, Max DD, Sharpe, Sortino, Calmar).
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from crypto_ml_trader.src.risk import RiskManager, DecisionEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class EventDrivenBacktester:
    """
    Event-driven backtesting engine for crypto trading strategies.
    Ensures ZERO lookahead bias and realistic cost execution modeling.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.risk_manager = RiskManager(config.get("risk", {}))
        self.decision_engine = DecisionEngine(self.risk_manager, config.get("models", {}))

        execution_cfg = config.get("execution", {})
        self.commission_pct = execution_cfg.get("commission_bps", 10) / 10000.0
        self.slippage_pct = execution_cfg.get("slippage_bps", 5) / 10000.0
        self.total_cost_per_side = self.commission_pct + self.slippage_pct

    def run_backtest(
        self,
        df: pd.DataFrame,
        buy_probs: np.ndarray,
        disagreements: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """Runs event-driven backtest simulation across dataframe."""
        if disagreements is None:
            disagreements = np.zeros(len(df))

        n = len(df)
        equity_curve = [self.risk_manager.initial_capital]
        trades = []
        open_position = None

        current_day = None

        for i in range(n - 1):
            row = df.iloc[i]
            next_row = df.iloc[i + 1]

            timestamp = row["open_time"]
            next_timestamp = next_row["open_time"]

            # Reset daily PnL at midnight UTC
            if current_day is None or timestamp.day != current_day:
                current_day = timestamp.day
                self.risk_manager.reset_daily_pnl(new_day_equity=equity_curve[-1])

            # Decrement cooldown
            self.risk_manager.decrement_cooldown()

            # 1. Update existing open position
            if open_position is not None:
                cur_price = row["close"]
                high = next_row["high"]
                low = next_row["low"]
                next_open = next_row["open"]

                sl = open_position["stop_loss"]
                tp = open_position["take_profit"]

                sl_hit = low <= sl
                tp_hit = high >= tp

                exit_type = None
                exit_price = 0.0

                if sl_hit and tp_hit:
                    # Conservative assumption: Stop-loss hit first
                    exit_type = "STOP_LOSS"
                    exit_price = sl * (1.0 - self.slippage_pct)
                elif sl_hit:
                    exit_type = "STOP_LOSS"
                    exit_price = sl * (1.0 - self.slippage_pct)
                elif tp_hit:
                    exit_type = "TAKE_PROFIT"
                    exit_price = tp * (1.0 - self.slippage_pct)
                elif open_position["holding_bars"] >= 12: # Vertical barrier exit
                    exit_type = "VERTICAL_BARRIER"
                    exit_price = next_open * (1.0 - self.slippage_pct)

                if exit_type is not None:
                    # Execute position exit
                    gross_pnl = open_position["units"] * (exit_price - open_position["entry_price"])
                    exit_commission = open_position["units"] * exit_price * self.commission_pct
                    net_pnl = gross_pnl - open_position["entry_fee"] - exit_commission

                    new_equity = equity_curve[-1] + net_pnl
                    equity_curve.append(new_equity)
                    self.risk_manager.update_equity(new_equity)

                    self.risk_manager.realized_pnl_today += net_pnl
                    self.risk_manager.trigger_cooldown()

                    trades.append({
                        "entry_time": open_position["entry_time"],
                        "exit_time": next_timestamp,
                        "entry_price": open_position["entry_price"],
                        "exit_price": exit_price,
                        "units": open_position["units"],
                        "gross_pnl": gross_pnl,
                        "net_pnl": net_pnl,
                        "pnl_pct": net_pnl / open_position["position_value"],
                        "exit_type": exit_type,
                        "holding_bars": open_position["holding_bars"] + 1,
                        "regime": row.get("market_regime", "UNKNOWN")
                    })

                    open_position = None
                    continue
                else:
                    open_position["holding_bars"] += 1
                    # Update open unrealized PnL
                    unrealized = open_position["units"] * (cur_price - open_position["entry_price"])
                    self.risk_manager.update_equity(equity_curve[-1], open_pnl=unrealized)

            else:
                equity_curve.append(equity_curve[-1])

            # 2. Evaluate decision engine for NEW trade signal
            prob = buy_probs[i]
            disag = disagreements[i]
            htf_permits = row.get("htf_permits_long", True)

            close_p = row["close"]
            norm_atr = row.get("norm_atr_14", 0.02)
            vol = max(norm_atr * close_p, close_p * 0.005)

            sl_price = close_p - 1.0 * vol
            tp_price = close_p + 1.5 * vol

            decision = self.decision_engine.evaluate(
                buy_probability=prob,
                model_disagreement=disag,
                htf_permits_long=htf_permits,
                entry_price=close_p,
                stop_loss_price=sl_price,
                take_profit_price=tp_price,
                has_open_position=(open_position is not None),
                is_market_tradable=True
            )

            if decision["action"] == "BUY":
                # Execute entry at next bar Open with slippage
                actual_entry_price = next_row["open"] * (1.0 + self.slippage_pct)
                entry_fee = decision["position_units"] * actual_entry_price * self.commission_pct

                open_position = {
                    "entry_time": next_timestamp,
                    "entry_price": actual_entry_price,
                    "stop_loss": sl_price,
                    "take_profit": tp_price,
                    "units": decision["position_units"],
                    "position_value": decision["position_value_usdt"],
                    "entry_fee": entry_fee,
                    "holding_bars": 0
                }

        # Calculate metrics report
        metrics = self._calculate_performance_metrics(df, equity_curve, trades)
        return metrics

    def _calculate_performance_metrics(
        self,
        df: pd.DataFrame,
        equity_curve: List[float],
        trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculates performance statistics: Net Return, CAGR, Max DD, Sharpe, Sortino, Calmar."""
        equity_series = pd.Series(equity_curve)
        initial_cap = equity_series.iloc[0]
        final_cap = equity_series.iloc[-1]

        net_return_pct = (final_cap - initial_cap) / initial_cap

        # Total time span in years
        time_span_days = (df["open_time"].max() - df["open_time"].min()).total_seconds() / 86400.0
        years = max(time_span_days / 365.25, 0.01)

        cagr = (final_cap / initial_cap) ** (1.0 / years) - 1.0 if final_cap > 0 else -1.0

        # High water mark and Drawdown
        rolling_max = equity_series.cummax()
        drawdowns = (rolling_max - equity_series) / rolling_max
        max_drawdown_pct = float(drawdowns.max())

        # Returns series for Sharpe / Sortino
        hourly_returns = equity_series.pct_change().fillna(0.0)
        mean_ret = hourly_returns.mean()
        std_ret = hourly_returns.std()

        sharpe_ratio = (mean_ret / (std_ret + 1e-10)) * np.sqrt(8760) if std_ret > 0 else 0.0

        downside_std = hourly_returns[hourly_returns < 0].std()
        sortino_ratio = (mean_ret / (downside_std + 1e-10)) * np.sqrt(8760) if downside_std > 0 else 0.0

        calmar_ratio = cagr / (max_drawdown_pct + 1e-10) if max_drawdown_pct > 0 else 0.0

        # Trade stats
        n_trades = len(trades)
        if n_trades > 0:
            trade_pnls = [t["net_pnl"] for t in trades]
            winning_trades = [p for p in trade_pnls if p > 0]
            losing_trades = [p for p in trade_pnls if p <= 0]

            win_rate = len(winning_trades) / n_trades
            gross_profit = sum(winning_trades)
            gross_loss = abs(sum(losing_trades))
            profit_factor = gross_profit / (gross_loss + 1e-10) if gross_loss > 0 else 999.0

            expectancy_usdt = float(np.mean(trade_pnls))
            avg_win = float(np.mean(winning_trades)) if winning_trades else 0.0
            avg_loss = float(np.mean(losing_trades)) if losing_trades else 0.0
        else:
            win_rate = 0.0
            profit_factor = 0.0
            expectancy_usdt = 0.0
            avg_win = 0.0
            avg_loss = 0.0

        # Buy and Hold Benchmark
        bnh_initial = df["close"].iloc[0]
        bnh_final = df["close"].iloc[-1]
        bnh_return_pct = (bnh_final - bnh_initial) / bnh_initial

        return {
            "initial_capital": float(initial_cap),
            "final_capital": float(final_cap),
            "net_return_pct": float(net_return_pct),
            "cagr": float(cagr),
            "max_drawdown_pct": float(max_drawdown_pct),
            "sharpe_ratio": float(sharpe_ratio),
            "sortino_ratio": float(sortino_ratio),
            "calmar_ratio": float(calmar_ratio),
            "total_trades": int(n_trades),
            "win_rate": float(win_rate),
            "profit_factor": float(profit_factor),
            "expectancy_usdt": float(expectancy_usdt),
            "avg_win_usdt": float(avg_win),
            "avg_loss_usdt": float(avg_loss),
            "buy_and_hold_return_pct": float(bnh_return_pct),
            "trades_detail": trades
        }

    def generate_report(self, metrics: Dict[str, Any], output_path: str = "reports/backtest_report.json"):
        """Saves backtest report to JSON."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Exclude detailed trades list from top summary for clean viewing
        summary = {k: v for k, v in metrics.items() if k != "trades_detail"}
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Saved backtest summary report to {output_path}")
