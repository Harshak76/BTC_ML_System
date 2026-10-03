"""
Backtester Module for V4 btc_ml_system.
Executes event-driven backtesting for V4 TradeSignals with trailing stop support.
Applies next-bar open execution, realistic commissions, slippage, and trailing stop exits.
"""

import logging
from typing import Dict, Any, List, Tuple, Union
from dataclasses import dataclass
import numpy as np
import pandas as pd

from btc_ml_system.src.signal_engine import TradeSignal
from btc_ml_system.src.position_sizing import DynamicRiskSizer
from btc_ml_system.src.monitoring import TradeJournal, AutoAnalyzer

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
    """Simulates event-driven backtesting with trailing stops, Monte Carlo robustness, TradeJournal, and AutoAnalyzer."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.exec_cfg = config.get("execution", {})
        self.risk_cfg = config.get("risk_engine", config.get("risk", {}))
        self.comm_rate = self.exec_cfg.get("commission_bps", 10) / 10000.0
        self.slip_rate = self.exec_cfg.get("slippage_bps", 5) / 10000.0
        self.initial_capital = self.risk_cfg.get("initial_capital", 10000.0)
        self.dynamic_risk_sizer = DynamicRiskSizer(config)
        self.journal = TradeJournal(config)
        self.auto_analyzer = AutoAnalyzer(config)

        # Exit Rules & Trailing Stop Config
        self.exit_cfg = config.get("exit_rules", {})
        self.enable_trailing_stop = self.exit_cfg.get("enable_trailing_stop", True)
        self.trailing_trigger_pct = self.exit_cfg.get("trailing_trigger_pct", 0.015) # 1.5% profit triggers trailing
        self.trailing_dist_pct = self.exit_cfg.get("trailing_dist_pct", 0.012)        # 1.2% trailing distance

        # Part B Exit Upgrades
        self.enable_early_loss_cut = bool(self.exit_cfg.get("enable_early_loss_cut", False))
        self.early_loss_cut_bars = int(self.exit_cfg.get("early_loss_cut_bars", 5))
        self.early_loss_cut_max_pnl_r = float(self.exit_cfg.get("early_loss_cut_max_pnl_r", 0.0))

        self.enable_profit_runner = bool(self.exit_cfg.get("enable_profit_runner", False))
        self.profit_runner_trigger_r = float(self.exit_cfg.get("profit_runner_trigger_r", 2.0))
        self.profit_runner_trail_dist_pct = float(self.exit_cfg.get("profit_runner_trail_dist_pct", 0.015))

    def run_backtest(
        self,
        df: pd.DataFrame,
        signals: List[Union[TradeSignal, Any]],
        cost_multiplier: float = 1.0
    ) -> Tuple[pd.DataFrame, List[Trade], Dict[str, Any]]:
        """
        Executes event-driven backtest for TradeSignals with dynamic trailing stop loss, TradeJournal, and AutoAnalyzer.
        """
        comm = self.comm_rate * cost_multiplier
        slip = self.slip_rate * cost_multiplier

        capital = self.initial_capital
        equity_curve = [capital]
        trades: List[Trade] = []
        risk_used_list: List[float] = []

        in_position = False
        entry_price = 0.0
        entry_idx = 0
        entry_time = None
        pos_value = 0.0
        sl_price = 0.0
        pt_price = 0.0
        initial_sl_price = 0.0
        curr_trig_pct = self.trailing_trigger_pct
        curr_dist_pct = self.trailing_dist_pct
        highest_price = 0.0
        trailing_stop_active = False
        bars_held = 0
        max_holding_bars = self.exit_cfg.get("max_holding_bars", 72)

        # Entry context trackers
        current_risk_pct = 0.005
        entry_atr = 0.0
        entry_rsi = 0.0
        vol_regime = "NORMAL"
        htf_valid = True
        dir_valid = True
        entry_sig_ref = None

        # Prepare ATR for Dynamic Risk Sizer if enabled
        if "atr" not in df.columns:
            high, low, close = df["high"], df["low"], df["close"]
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            df["atr"] = tr.ewm(alpha=1/14, adjust=False).mean()

        avg_atr_series = df["atr"].rolling(self.dynamic_risk_sizer.vol_lookback).mean()

        close_prices = df["close"].values
        open_prices = df["open"].values
        high_prices = df["high"].values
        low_prices = df["low"].values
        timestamps = df["open_time"].values
        atr_values = df["atr"].values
        avg_atr_values = avg_atr_series.values

        rsi_values = df["rsi"].values if "rsi" in df.columns else np.zeros(len(df))
        regime_values = df["volatility_regime"].values if "volatility_regime" in df.columns else np.full(len(df), "NORMAL")
        htf_valid_values = df["htf_trend_valid"].values if "htf_trend_valid" in df.columns else np.ones(len(df), dtype=bool)
        dir_valid_values = df["direction_valid"].values if "direction_valid" in df.columns else np.ones(len(df), dtype=bool)

        for i in range(len(df) - 1):
            curr_open = open_prices[i + 1]
            curr_high = high_prices[i + 1]
            curr_low = low_prices[i + 1]
            curr_close = close_prices[i + 1]
            curr_time = timestamps[i + 1]

            # 1. Position Management
            if in_position:
                bars_held += 1
                highest_price = max(highest_price, curr_high)

                # Check Profit Runner Activation (Part B)
                if self.enable_profit_runner and not trailing_stop_active:
                    dollar_risk = abs(entry_price - initial_sl_price)
                    current_r = (highest_price - entry_price) / dollar_risk if dollar_risk > 0 else 0.0
                    if current_r >= self.profit_runner_trigger_r:
                        trailing_stop_active = True
                        curr_dist_pct = self.profit_runner_trail_dist_pct
                        sl_price = max(sl_price, highest_price * (1.0 - curr_dist_pct))

                # Check Standard Trailing Stop
                if self.enable_trailing_stop and not trailing_stop_active:
                    profit_ratio = (highest_price - entry_price) / entry_price
                    if profit_ratio >= curr_trig_pct:
                        trailing_stop_active = True
                        sl_price = max(sl_price, highest_price * (1.0 - curr_dist_pct))

                # Update trailing stop if active
                if trailing_stop_active:
                    new_trail_sl = highest_price * (1.0 - curr_dist_pct)
                    sl_price = max(sl_price, new_trail_sl)

                # Check Early Loss Cut / Stagnation Exit (Part B)
                hit_early_cut = False
                if self.enable_early_loss_cut and bars_held >= self.early_loss_cut_bars and not trailing_stop_active:
                    dollar_risk = abs(entry_price - initial_sl_price)
                    current_r = (curr_close - entry_price) / dollar_risk if dollar_risk > 0 else 0.0
                    if current_r <= self.early_loss_cut_max_pnl_r:
                        hit_early_cut = True

                hit_sl = curr_low <= sl_price
                hit_pt = curr_high >= pt_price
                hit_max_hold = bars_held >= max_holding_bars

                if hit_sl or hit_pt or hit_max_hold or hit_early_cut:
                    if hit_early_cut and not hit_sl:
                        exit_price = curr_close
                        reason = "EARLY_LOSS_CUT"
                    elif hit_sl:
                        exit_price = sl_price
                        reason = "PROFIT_RUNNER_HIT" if (self.enable_profit_runner and trailing_stop_active) else ("TRAILING_SL_HIT" if trailing_stop_active else "SL_HIT")
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

                    trade_obj = Trade(
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
                    )
                    trades.append(trade_obj)

                    # Record to TradeJournal
                    entry_dt = pd.to_datetime(entry_time)
                    exit_dt = pd.to_datetime(curr_time)
                    dur_hours = (exit_dt - entry_dt).total_seconds() / 3600.0
                    hr = entry_dt.hour
                    if 0 <= hr < 8:
                        session_str = "Asian (00-08 UTC)"
                    elif 8 <= hr < 14:
                        session_str = "European (08-14 UTC)"
                    elif 14 <= hr < 22:
                        session_str = "US (14-22 UTC)"
                    else:
                        session_str = "Off-hours (22-24 UTC)"

                    dollar_risk = capital * current_risk_pct
                    r_mult = pnl_dollars / dollar_risk if dollar_risk > 0 else (net_pnl_pct / current_risk_pct if current_risk_pct > 0 else 0.0)

                    self.journal.record_trade({
                        "trade_id": len(trades),
                        "entry_idx": entry_idx,
                        "entry_time": entry_time,
                        "entry_price": entry_price,
                        "exit_idx": i + 1,
                        "exit_time": curr_time,
                        "exit_price": exit_price_adj,
                        "action": "BUY",
                        "quantity": pos_value / entry_price if entry_price > 0 else 0.0,
                        "position_value_usd": pos_value,
                        "pnl_usd": pnl_dollars,
                        "pnl_pct": net_pnl_pct,
                        "r_multiple": r_mult,
                        "duration_bars": bars_held,
                        "duration_hours": dur_hours,
                        "volatility_regime": vol_regime,
                        "htf_trend_valid": htf_valid,
                        "direction_valid": dir_valid,
                        "risk_pct_used": current_risk_pct,
                        "atr_at_entry": entry_atr,
                        "rsi_at_entry": entry_rsi,
                        "session": session_str,
                        "day_of_week": entry_dt.strftime("%A"),
                        "hour_of_day": hr,
                        "entry_reason": getattr(entry_sig_ref, "rejection_reason", "Trade Approved"),
                        "exit_reason": reason
                    })

                    in_position = False

            # 2. Check Signal Entry
            if not in_position and i < len(signals):
                sig = signals[i]
                is_allowed = getattr(sig, "allowed_trade", False) or getattr(sig, "allow_trade", False)
                if is_allowed:
                    in_position = True
                    bars_held = 0
                    entry_idx = i + 1
                    entry_time = curr_time
                    entry_price = curr_open * (1.0 + slip)
                    highest_price = entry_price
                    trailing_stop_active = False

                    entry_sig_ref = sig
                    entry_atr = float(atr_values[i]) if not np.isnan(atr_values[i]) else 0.0
                    entry_rsi = float(rsi_values[i]) if not np.isnan(rsi_values[i]) else 0.0
                    vol_regime = str(regime_values[i])
                    htf_valid = bool(htf_valid_values[i])
                    dir_valid = bool(dir_valid_values[i])

                    if hasattr(sig, "stop_loss_price") and sig.stop_loss_price > 0:
                        sl_price = sig.stop_loss_price
                        pt_price = sig.take_profit_price
                        initial_sl_price = sl_price
                        trig_sig = getattr(sig, "trailing_trigger_pct", None)
                        if trig_sig is not None:
                            curr_trig_pct = float(trig_sig)
                        dist_sig = getattr(sig, "trailing_dist_pct", None)
                        if dist_sig is not None:
                            curr_dist_pct = float(dist_sig)

                        if self.dynamic_risk_sizer.enabled:
                            curr_atr_val = float(atr_values[i]) if not np.isnan(atr_values[i]) else 0.0
                            avg_atr_val = float(avg_atr_values[i]) if not np.isnan(avg_atr_values[i]) else 0.0
                            trade_risk_pct = self.dynamic_risk_sizer.calculate_risk_pct(
                                recent_trades=trades,
                                current_atr=curr_atr_val,
                                historical_avg_atr=avg_atr_val
                            )
                            stop_dist = abs(entry_price - sl_price)
                            if stop_dist > 0:
                                qty = (capital * trade_risk_pct) / stop_dist
                                pos_value = min(qty * entry_price, capital * 0.25)
                            else:
                                pos_value = sig.position_value_usd if (hasattr(sig, "position_value_usd") and sig.position_value_usd > 0) else (capital * 0.25)
                        else:
                            trade_risk_pct = self.risk_cfg.get("risk_per_trade_pct", 0.005)
                            pos_value = sig.position_value_usd if (hasattr(sig, "position_value_usd") and sig.position_value_usd > 0) else (capital * 0.25)

                        current_risk_pct = trade_risk_pct
                        risk_used_list.append(trade_risk_pct)
                    else:
                        sl_price = entry_price * 0.985
                        pt_price = entry_price * 1.035
                        pos_value = capital * 0.25
                        trade_risk_pct = self.risk_cfg.get("risk_per_trade_pct", 0.005)
                        current_risk_pct = trade_risk_pct
                        risk_used_list.append(trade_risk_pct)

            equity_curve.append(capital)

        # Metrics calculation
        eq_series = pd.Series(equity_curve)
        total_return_pct = ((capital - self.initial_capital) / self.initial_capital) * 100.0

        cummax = eq_series.cummax()
        drawdown = (eq_series - cummax) / cummax
        max_drawdown_pct = abs(drawdown.min()) * 100.0

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        win_rate = len(wins) / len(trades) if trades else 0.0

        gross_profit = sum([t.pnl for t in wins])
        gross_loss = abs(sum([t.pnl for t in losses]))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        if risk_used_list:
            avg_risk = float(np.mean(risk_used_list)) * 100.0
            max_risk = float(np.max(risk_used_list)) * 100.0
            min_risk = float(np.min(risk_used_list)) * 100.0
        else:
            base_r = self.risk_cfg.get("risk_per_trade_pct", 0.005) * 100.0
            avg_risk, max_risk, min_risk = base_r, base_r, base_r

        metrics = {
            "initial_capital": self.initial_capital,
            "final_capital": capital,
            "total_return_pct": total_return_pct,
            "total_trades": len(trades),
            "win_rate": win_rate,
            "max_drawdown_pct": max_drawdown_pct,
            "profit_factor": profit_factor,
            "avg_risk_pct": avg_risk,
            "max_risk_pct": max_risk,
            "min_risk_pct": min_risk
        }

        # Save Trade Journal & Auto Analyzer Report
        journal_df = self.journal.to_dataframe()
        journal_path = self.journal.save()
        analysis_res = self.auto_analyzer.analyze(journal_df, metrics)
        report_text = self.auto_analyzer.generate_report(analysis_res, symbol=self.journal.symbol, strat_name=self.journal.strat_name)
        print("\n" + report_text)

        metrics["journal_csv"] = journal_path
        metrics["auto_analysis"] = analysis_res

        equity_df = pd.DataFrame({"equity": equity_curve})
        return equity_df, trades, metrics


