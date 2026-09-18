"""
Backtester Module for V3 btc_ml_system.
Executes event-driven backtesting for V3 TradeSignals and V2 decisions.
Applies next-bar open execution, realistic commissions, slippage, and trailing stop exits.
"""

import logging
from typing import Dict, Any, List, Tuple, Union
from dataclasses import dataclass
import numpy as np
import pandas as pd

from btc_ml_system.src.signal_engine import TradeSignal

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
    """Simulates event-driven backtesting and Monte Carlo robustness."""

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
        signals: List[Union[TradeSignal, Any]],
        cost_multiplier: float = 1.0
    ) -> Tuple[pd.DataFrame, List[Trade], Dict[str, Any]]:
        """
        Executes event-driven backtest for V3 TradeSignals or V2 decision objects.
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
        pos_value = 0.0
        sl_price = 0.0
        pt_price = 0.0
        bars_held = 0
        max_holding_bars = self.config.get("exit_rules", {}).get("max_holding_bars", 24)

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

            # 1. Position Management
            if in_position:
                bars_held += 1
                hit_sl = curr_low <= sl_price
                hit_pt = curr_high >= pt_price
                hit_max_hold = bars_held >= max_holding_bars

                if hit_sl or hit_pt or hit_max_hold:
                    if hit_sl:
                        exit_price = sl_price
                        reason = "SL_HIT"
                    elif hit_pt:
                        exit_price = pt_price
                        reason = "PT_HIT"
                    else:
                        exit_price = curr_close
                        reason = "MAX_HOLD_HORIZON"

                    exit_price_adj = exit_price * (1.0 - slip)
                    raw_pnl = (exit_price_adj - entry_price) / entry_price
                    net_pnl_pct = raw_pnl - comm

                    pnl_dollars = pos_value * net_pnl_pct
                    capital += pnl_dollars

                    trades.append(Trade(
                        entry_idx=entry_idx,
                        entry_time=entry_time,
                        entry_price=entry_price,
                        exit_idx=i + 1,
                        exit_time=curr_time,
                        exit_price=exit_price_adj,
                        position_size=pos_value / capital if capital > 0 else 0.0,
                        pnl=pnl_dollars,
                        pnl_pct=net_pnl_pct,
                        reason=reason
                    ))
                    in_position = False

            # 2. Check Signal Entry
            if not in_position and i < len(signals):
                sig = signals[i]
                # Support both TradeSignal (V3) and RiskDecision (V2)
                is_allowed = getattr(sig, "allowed_trade", False) or getattr(sig, "allow_trade", False)
                if is_allowed:
                    in_position = True
                    bars_held = 0
                    entry_idx = i + 1
                    entry_time = curr_time
                    entry_price = curr_open * (1.0 + slip)

                    if hasattr(sig, "stop_loss_price") and sig.stop_loss_price > 0:
                        sl_price = sig.stop_loss_price
                        pt_price = sig.take_profit_price
                        pos_value = sig.position_value_usd if sig.position_value_usd > 0 else (capital * 0.25)
                    else:
                        sl_price = entry_price * (1.0 - sig.stop_loss_pct)
                        pt_price = entry_price * (1.0 + sig.take_profit_pct)
                        pos_value = capital * sig.position_size

                    capital -= pos_value * comm

            equity_curve.append(capital)

        equity_series = pd.Series(equity_curve)
        total_return = (capital - self.initial_capital) / self.initial_capital
        cum_max = equity_series.cummax()
        drawdowns = (equity_series - cum_max) / (cum_max + 1e-10)
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
        """Runs Monte Carlo resampled equity paths."""
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
            dd = (equity - cum_max) / (cum_max + 1e-10)
            max_drawdowns.append(abs(np.min(dd)))

        return {
            "mc_5th_pct_return": np.percentile(final_returns, 5) * 100,
            "mc_median_return": np.median(final_returns) * 100,
            "mc_95th_pct_drawdown": np.percentile(max_drawdowns, 95) * 100
        }
