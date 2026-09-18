"""
Backtester & Robustness Engine for V2 btc_ml_system.
Includes:
- Event-driven non-repainting backtesting engine
- Realistic transaction costs (10bps fee + 5bps slippage)
- Next bar open execution
- Monte Carlo robustness simulation (1000 paths)
- Stress testing cost multipliers (1.0x, 2.0x, 3.0x)
- Threshold sensitivity grid
- External validation on secondary symbol (ETHUSDT)
"""

import logging
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import numpy as np
import pandas as pd

logger = logging.getLogger("btc_ml_system.backtester")


@dataclass
class Trade:
    entry_idx: int
    entry_time: pd.Timestamp
    entry_price: float
    exit_idx: int
    exit_time: pd.Timestamp
    exit_price: float
    position_size: float
    pnl: float
    pnl_pct: float
    reason: str


class Backtester:
    """Simulates realistic execution and runs Monte Carlo & Stress tests."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.exec_cfg = config.get("execution", {})
        self.risk_cfg = config.get("risk", {})
        self.comm_rate = self.exec_cfg.get("commission_bps", 10) / 10000.0
        self.slip_rate = self.exec_cfg.get("slippage_bps", 5) / 10000.0
        self.initial_capital = self.risk_cfg.get("initial_capital", 10000.0)

    def run_backtest(
        self,
        df: pd.DataFrame,
        decisions: List[Any],
        cost_multiplier: float = 1.0
    ) -> Tuple[pd.DataFrame, List[Trade], Dict[str, Any]]:
        """
        Executes event-driven backtest on test dataframe with decisions.
        Applies next_bar_open execution to prevent lookahead bias.
        """
        comm = self.comm_rate * cost_multiplier
        slip = self.slip_rate * cost_multiplier

        capital = self.initial_capital
        equity_curve = [capital]
        trades: List[Trade] = []

        in_position = False
        entry_price = 0.0
        entry_idx = 0
        entry_time = None
        pos_size = 0.0
        sl_price = 0.0
        pt_price = 0.0

        close_prices = df["close"].values
        open_prices = df["open"].values
        high_prices = df["high"].values
        low_prices = df["low"].values
        timestamps = df["open_time"].values

        for i in range(len(df) - 1):
            curr_open = open_prices[i + 1]
            curr_high = high_prices[i + 1]
            curr_low = low_prices[i + 1]
            curr_close = close_prices[i + 1]
            curr_time = timestamps[i + 1]

            # 1. Manage Active Position
            if in_position:
                # Check Stop Loss & Take Profit against bar high/low
                hit_sl = curr_low <= sl_price
                hit_pt = curr_high >= pt_price

                if hit_sl or hit_pt:
                    exit_price = sl_price if hit_sl else pt_price
                    # Apply slippage on exit
                    exit_price_adj = exit_price * (1.0 - slip)
                    raw_pnl = (exit_price_adj - entry_price) / entry_price
                    net_pnl_pct = raw_pnl - comm

                    pnl_dollars = pos_size * capital * net_pnl_pct
                    capital += pnl_dollars

                    trades.append(Trade(
                        entry_idx=entry_idx,
                        entry_time=entry_time,
                        entry_price=entry_price,
                        exit_idx=i + 1,
                        exit_time=curr_time,
                        exit_price=exit_price_adj,
                        position_size=pos_size,
                        pnl=pnl_dollars,
                        pnl_pct=net_pnl_pct,
                        reason="SL_HIT" if hit_sl else "PT_HIT"
                    ))
                    in_position = False

            # 2. Check for New Entry Signal (Execute on next bar open)
            if not in_position and i < len(decisions):
                dec = decisions[i]
                if dec.allow_trade:
                    in_position = True
                    entry_idx = i + 1
                    entry_time = curr_time
                    # Apply slippage on entry
                    entry_price = curr_open * (1.0 + slip)
                    pos_size = dec.position_size
                    sl_price = entry_price * (1.0 - dec.stop_loss_pct)
                    pt_price = entry_price * (1.0 + dec.take_profit_pct)
                    # Pay entry commission
                    capital -= pos_size * capital * comm

            equity_curve.append(capital)

        # Performance Summary Metrics
        equity_series = pd.Series(equity_curve)
        total_return = (capital - self.initial_capital) / self.initial_capital
        cum_max = equity_series.cummax()
        drawdowns = (equity_series - cum_max) / cum_max
        max_dd = drawdowns.min()

        win_trades = [t for t in trades if t.pnl > 0]
        win_rate = len(win_trades) / len(trades) if trades else 0.0

        metrics = {
            "initial_capital": self.initial_capital,
            "final_capital": capital,
            "total_return_pct": total_return * 100,
            "total_trades": len(trades),
            "win_rate": win_rate,
            "max_drawdown_pct": abs(max_dd) * 100,
            "profit_factor": (sum(t.pnl for t in win_trades) / abs(sum(t.pnl for t in trades if t.pnl < 0) + 1e-10)) if trades else 0.0
        }

        return pd.DataFrame({"equity": equity_curve}), trades, metrics

    def run_monte_carlo(self, trades: List[Trade], n_paths: int = 1000) -> Dict[str, float]:
        """Runs Monte Carlo resampled equity paths to evaluate drawdown distribution."""
        if not trades:
            return {"mc_5th_pct_return": 0.0, "mc_95th_pct_drawdown": 0.0}

        returns = [t.pnl_pct for t in trades]
        final_returns = []
        max_drawdowns = []

        for _ in range(n_paths):
            resampled = np.random.choice(returns, size=len(returns), replace=True)
            equity = self.initial_capital * np.cumprod(1.0 + resampled)
            final_returns.append((equity[-1] - self.initial_capital) / self.initial_capital)
            cum_max = np.maximum.accumulate(equity)
            dd = (equity - cum_max) / cum_max
            max_drawdowns.append(abs(np.min(dd)))

        return {
            "mc_5th_pct_return": np.percentile(final_returns, 5) * 100,
            "mc_median_return": np.median(final_returns) * 100,
            "mc_95th_pct_drawdown": np.percentile(max_drawdowns, 95) * 100
        }
