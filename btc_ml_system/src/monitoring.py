"""
Drift & Feature Stability Monitoring Module for V2 btc_ml_system.
Includes:
- Population Stability Index (PSI) tracking
- Kolmogorov-Smirnov (KS) test for feature distribution shifts
- Retraining signal trigger based on drift magnitude
- SHAP feature contribution logging
"""

import logging
from typing import Dict, Any, Tuple, List, Optional, Union
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger("btc_ml_system.monitoring")


class ModelMonitor:
    """Monitors live data drift and feature stability over time."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mon_cfg = config.get("monitoring", {})
        self.psi_threshold = self.mon_cfg.get("psi_threshold", 0.20)
        self.ks_threshold = self.mon_cfg.get("ks_threshold", 0.10)
        self.window = self.mon_cfg.get("prediction_drift_window", 100)

    def calculate_psi(self, reference: np.ndarray, current: np.ndarray, num_bins: int = 10) -> float:
        """Calculates Population Stability Index (PSI) between reference train set and live predictions."""
        if len(reference) == 0 or len(current) == 0:
            return 0.0

        bins = np.linspace(0, 1, num_bins + 1)
        ref_counts, _ = np.histogram(reference, bins=bins)
        curr_counts, _ = np.histogram(current, bins=bins)

        ref_pct = (ref_counts + 1e-5) / (len(reference) + 1e-5 * num_bins)
        curr_pct = (curr_counts + 1e-5) / (len(current) + 1e-5 * num_bins)

        psi_val = np.sum((curr_pct - ref_pct) * np.log(curr_pct / ref_pct))
        return float(psi_val)

    def check_feature_drift(self, train_df: pd.DataFrame, live_df: pd.DataFrame, features: list) -> Dict[str, Any]:
        """
        Runs Kolmogorov-Smirnov 2-sample test across all features.
        Returns drift summary dict and boolean flag for retraining signal.
        """
        drift_results = {}
        drift_count = 0

        for col in features:
            if col in train_df.columns and col in live_df.columns:
                ref_vals = train_df[col].dropna().values
                curr_vals = live_df[col].dropna().values

                if len(ref_vals) > 10 and len(curr_vals) > 10:
                    ks_stat, p_val = stats.ks_2samp(ref_vals, curr_vals)
                    is_drifted = p_val < self.ks_threshold
                    if is_drifted:
                        drift_count += 1
                    drift_results[col] = {"ks_stat": float(ks_stat), "p_val": float(p_val), "drifted": is_drifted}

        drift_ratio = drift_count / max(1, len(features))
        retrain_signal = drift_ratio >= self.mon_cfg.get("retrain_signal_threshold", 0.25)

        logger.info(f"Drift Audit: {drift_count}/{len(features)} features drifted ({drift_ratio:.1%}). Retrain Signal: {retrain_signal}")

        return {
            "drift_ratio": drift_ratio,
            "drifted_feature_count": drift_count,
            "retrain_recommended": retrain_signal,
            "feature_details": drift_results
        }


class TradeJournal:
    """
    Trade Journal Module for btc_ml_system.
    Records closed trades with rich contextual metadata, active filter states, session details, and PnL metrics.
    Persists journal records and equity curves directly into clean DuckDB analytical storage.
    Includes on-demand CSV export functionality.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.asset_cfg = config.get("asset", {})
        self.symbol = self.asset_cfg.get("symbol", "BTCUSDT")
        self.strat_name = config.get("strategy", {}).get("name", "strategy")
        self.base_tf = self.asset_cfg.get("base_timeframe", "1h")
        self.htf_tf = self.asset_cfg.get("htf_timeframe", "4h")
        self.records: List[Dict[str, Any]] = []

    def record_trade(self, trade_data: Dict[str, Any]):
        """Records a closed trade entry into the journal buffer."""
        record = {
            "trade_id": str(trade_data.get("trade_id", len(self.records) + 1)),
            "symbol": self.symbol,
            "strategy": self.strat_name,
            "base_timeframe": self.base_tf,
            "htf_timeframe": self.htf_tf,
            "entry_idx": trade_data.get("entry_idx"),
            "entry_time": pd.to_datetime(trade_data.get("entry_time"), format="mixed"),
            "entry_price": float(trade_data.get("entry_price", 0.0)),
            "exit_idx": trade_data.get("exit_idx"),
            "exit_time": pd.to_datetime(trade_data.get("exit_time"), format="mixed"),
            "exit_price": float(trade_data.get("exit_price", 0.0)),
            "action": trade_data.get("action", "BUY"),
            "quantity": float(trade_data.get("quantity", 0.0)),
            "position_value_usd": float(trade_data.get("position_value_usd", 0.0)),
            "pnl_usd": float(trade_data.get("pnl_usd", 0.0)),
            "pnl_pct": float(trade_data.get("pnl_pct", 0.0)),
            "r_multiple": float(trade_data.get("r_multiple", 0.0)),
            "duration_bars": int(trade_data.get("duration_bars", 0)),
            "duration_hours": float(trade_data.get("duration_hours", 0.0)),
            "volatility_regime": str(trade_data.get("volatility_regime", "UNKNOWN")),
            "htf_trend_valid": bool(trade_data.get("htf_trend_valid", True)),
            "direction_valid": bool(trade_data.get("direction_valid", True)),
            "risk_pct_used": float(trade_data.get("risk_pct_used", 0.005)),
            "atr_at_entry": float(trade_data.get("atr_at_entry", 0.0)),
            "rsi_at_entry": float(trade_data.get("rsi_at_entry", 0.0)),
            "session": str(trade_data.get("session", "UNKNOWN")),
            "day_of_week": str(trade_data.get("day_of_week", "UNKNOWN")),
            "hour_of_day": int(trade_data.get("hour_of_day", 0)),
            "entry_reason": str(trade_data.get("entry_reason", "Trade Approved")),
            "exit_reason": str(trade_data.get("exit_reason", "EXIT"))
        }
        self.records.append(record)

    def to_dataframe(self) -> pd.DataFrame:
        """Converts journal records into a structured pandas DataFrame."""
        if not self.records:
            return pd.DataFrame()
        return pd.DataFrame(self.records)

    def save(self, db_path: Optional[str] = None, source: str = "backtest") -> str:
        """
        Saves journal directly to DuckDB 'trades' table.
        Replaces legacy CSV flooding with clean analytical storage.
        """
        df = self.to_dataframe()
        if df.empty:
            logger.warning("Trade journal is empty, skipping save.")
            return ""

        from btc_ml_system.src.database import DatabaseManager
        db = DatabaseManager(db_path)
        db.insert_trades(df, source=source)
        logger.info(f"Trade Journal safely persisted to DuckDB: {db.db_path} (table: trades)")
        return str(db.db_path)

    def save_equity_curve(self, equity_df: pd.DataFrame, db_path: Optional[str] = None) -> int:
        """Saves backtest equity curve to DuckDB 'equity_curve' table."""
        if equity_df.empty:
            return 0
        from btc_ml_system.src.database import DatabaseManager
        db = DatabaseManager(db_path)
        return db.insert_equity_curve(equity_df, symbol=self.symbol, strategy=self.strat_name)

    def export_csv(self, output_path: str) -> str:
        """Exports buffered trade records to CSV on demand."""
        df = self.to_dataframe()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info(f"Trade Journal exported on demand to CSV: {output_path}")
        return output_path

    def clear(self):
        """Clears the in-memory trade buffer."""
        self.records.clear()


class AutoAnalyzer:
    """
    Automated Quantitative Analysis Engine for btc_ml_system.
    Processes trade journals post-backtest or directly from DuckDB to generate rich actionable insights:
    - Expectancy & Profit Factor by trade setup
    - MTF alignment breakdown
    - Volatility regime performance
    - Session / day / hour patterns
    - Winners vs Losers R-multiple separation
    - Pattern discovery separating good trades from bad trades
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def analyze(
        self,
        journal_df: Optional[pd.DataFrame] = None,
        backtest_metrics: Optional[Dict[str, Any]] = None,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs quantitative analysis on the trade journal.
        Accepts either an in-memory DataFrame or directly queries DuckDB.
        """
        if journal_df is None or journal_df.empty:
            # Query directly from DuckDB
            from btc_ml_system.src.database import DatabaseManager
            db = DatabaseManager(db_path)
            journal_df = db.get_trades(symbol=symbol, strategy=strategy)

        if journal_df.empty:
            return {"status": "NO_TRADES"}

        df = journal_df.copy()
        total_trades = len(df)
        wins = df[df["pnl_usd"] > 0]
        losses = df[df["pnl_usd"] <= 0]
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0

        gross_profit = wins["pnl_usd"].sum()
        gross_loss = abs(losses["pnl_usd"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        avg_r_win = wins["r_multiple"].mean() if not wins.empty else 0.0
        avg_r_loss = losses["r_multiple"].mean() if not losses.empty else 0.0
        expectancy_r = df["r_multiple"].mean() if not df.empty else 0.0
        expectancy_usd = df["pnl_usd"].mean() if not df.empty else 0.0

        # 1. Volatility Regime Performance
        vol_summary = {}
        if "volatility_regime" in df.columns:
            for reg, group in df.groupby("volatility_regime"):
                g_wins = group[group["pnl_usd"] > 0]
                g_loss = group[group["pnl_usd"] <= 0]
                g_pf = g_wins["pnl_usd"].sum() / abs(g_loss["pnl_usd"].sum()) if abs(g_loss["pnl_usd"].sum()) > 0 else 0.0
                vol_summary[str(reg)] = {
                    "count": len(group),
                    "win_rate": len(g_wins) / len(group) if len(group) > 0 else 0.0,
                    "total_pnl": float(group["pnl_usd"].sum()),
                    "profit_factor": float(g_pf),
                    "avg_r": float(group["r_multiple"].mean())
                }

        # 2. MTF Trend Alignment Performance
        mtf_summary = {}
        if "htf_trend_valid" in df.columns:
            for mtf_state, group in df.groupby("htf_trend_valid"):
                g_wins = group[group["pnl_usd"] > 0]
                g_loss = group[group["pnl_usd"] <= 0]
                g_pf = g_wins["pnl_usd"].sum() / abs(g_loss["pnl_usd"].sum()) if abs(g_loss["pnl_usd"].sum()) > 0 else 0.0
                label = "HTF Confirmed (Bullish)" if mtf_state else "HTF Unconfirmed"
                mtf_summary[label] = {
                    "count": len(group),
                    "win_rate": len(g_wins) / len(group) if len(group) > 0 else 0.0,
                    "total_pnl": float(group["pnl_usd"].sum()),
                    "profit_factor": float(g_pf),
                    "avg_r": float(group["r_multiple"].mean())
                }

        # 3. Session & Time Analysis
        session_summary = {}
        if "session" in df.columns:
            for sess, group in df.groupby("session"):
                g_wins = group[group["pnl_usd"] > 0]
                g_loss = group[group["pnl_usd"] <= 0]
                g_pf = g_wins["pnl_usd"].sum() / abs(g_loss["pnl_usd"].sum()) if abs(g_loss["pnl_usd"].sum()) > 0 else 0.0
                session_summary[str(sess)] = {
                    "count": len(group),
                    "win_rate": len(g_wins) / len(group) if len(group) > 0 else 0.0,
                    "total_pnl": float(group["pnl_usd"].sum()),
                    "profit_factor": float(g_pf)
                }

        day_summary = {}
        if "day_of_week" in df.columns:
            for day, group in df.groupby("day_of_week"):
                day_summary[str(day)] = {
                    "count": len(group),
                    "win_rate": (group["pnl_usd"] > 0).mean(),
                    "total_pnl": float(group["pnl_usd"].sum())
                }

        # 4. Exit Reason Breakdown
        exit_summary = {}
        if "exit_reason" in df.columns:
            for ex, group in df.groupby("exit_reason"):
                exit_summary[str(ex)] = {
                    "count": len(group),
                    "win_rate": (group["pnl_usd"] > 0).mean(),
                    "total_pnl": float(group["pnl_usd"].sum()),
                    "avg_pnl": float(group["pnl_usd"].mean())
                }

        # 5. Key Pattern Separators (Winners vs Losers)
        separators = {}
        num_cols = ["atr_at_entry", "rsi_at_entry", "duration_bars", "risk_pct_used"]
        for col in num_cols:
            if col in df.columns:
                w_val = wins[col].mean() if not wins.empty else 0.0
                l_val = losses[col].mean() if not losses.empty else 0.0
                separators[col] = {"winner_avg": float(w_val), "loser_avg": float(l_val), "diff": float(w_val - l_val)}

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "gross_profit": float(gross_profit),
            "gross_loss": float(gross_loss),
            "expectancy_usd": float(expectancy_usd),
            "expectancy_r": float(expectancy_r),
            "winner_avg_r": float(avg_r_win),
            "loser_avg_r": float(avg_r_loss),
            "volatility_regime_breakdown": vol_summary,
            "mtf_breakdown": mtf_summary,
            "session_breakdown": session_summary,
            "day_breakdown": day_summary,
            "exit_breakdown": exit_summary,
            "pattern_separators": separators
        }

    def analyze_from_db(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        source: Optional[str] = None,
        db_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyzes trades queried directly from DuckDB."""
        from btc_ml_system.src.database import DatabaseManager
        db = DatabaseManager(db_path)
        df = db.get_trades(symbol=symbol, strategy=strategy, source=source)
        return self.analyze(journal_df=df)

    def generate_db_report(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        source: Optional[str] = None,
        db_path: Optional[str] = None
    ) -> str:
        """Runs quantitative analysis directly on DuckDB and generates formatted text report."""
        analysis = self.analyze_from_db(symbol=symbol, strategy=strategy, source=source, db_path=db_path)
        return self.generate_report(analysis, symbol=symbol or "ALL_ASSETS", strat_name=strategy or "ALL_STRATEGIES")
        if journal_df.empty:
            return {"status": "NO_TRADES"}

        df = journal_df.copy()
        total_trades = len(df)
        wins = df[df["pnl_usd"] > 0]
        losses = df[df["pnl_usd"] <= 0]
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0

        gross_profit = wins["pnl_usd"].sum()
        gross_loss = abs(losses["pnl_usd"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

        avg_r_win = wins["r_multiple"].mean() if not wins.empty else 0.0
        avg_r_loss = losses["r_multiple"].mean() if not losses.empty else 0.0
        expectancy_r = df["r_multiple"].mean() if not df.empty else 0.0
        expectancy_usd = df["pnl_usd"].mean() if not df.empty else 0.0

        # 1. Volatility Regime Performance
        vol_summary = {}
        if "volatility_regime" in df.columns:
            for reg, group in df.groupby("volatility_regime"):
                g_wins = group[group["pnl_usd"] > 0]
                g_loss = group[group["pnl_usd"] <= 0]
                g_pf = g_wins["pnl_usd"].sum() / abs(g_loss["pnl_usd"].sum()) if abs(g_loss["pnl_usd"].sum()) > 0 else 0.0
                vol_summary[str(reg)] = {
                    "count": len(group),
                    "win_rate": len(g_wins) / len(group) if len(group) > 0 else 0.0,
                    "total_pnl": float(group["pnl_usd"].sum()),
                    "profit_factor": float(g_pf),
                    "avg_r": float(group["r_multiple"].mean())
                }

        # 2. MTF Trend Alignment Performance
        mtf_summary = {}
        if "htf_trend_valid" in df.columns:
            for mtf_state, group in df.groupby("htf_trend_valid"):
                g_wins = group[group["pnl_usd"] > 0]
                g_loss = group[group["pnl_usd"] <= 0]
                g_pf = g_wins["pnl_usd"].sum() / abs(g_loss["pnl_usd"].sum()) if abs(g_loss["pnl_usd"].sum()) > 0 else 0.0
                label = "HTF Confirmed (Bullish)" if mtf_state else "HTF Unconfirmed"
                mtf_summary[label] = {
                    "count": len(group),
                    "win_rate": len(g_wins) / len(group) if len(group) > 0 else 0.0,
                    "total_pnl": float(group["pnl_usd"].sum()),
                    "profit_factor": float(g_pf),
                    "avg_r": float(group["r_multiple"].mean())
                }

        # 3. Session & Time Analysis
        session_summary = {}
        if "session" in df.columns:
            for sess, group in df.groupby("session"):
                g_wins = group[group["pnl_usd"] > 0]
                g_loss = group[group["pnl_usd"] <= 0]
                g_pf = g_wins["pnl_usd"].sum() / abs(g_loss["pnl_usd"].sum()) if abs(g_loss["pnl_usd"].sum()) > 0 else 0.0
                session_summary[str(sess)] = {
                    "count": len(group),
                    "win_rate": len(g_wins) / len(group) if len(group) > 0 else 0.0,
                    "total_pnl": float(group["pnl_usd"].sum()),
                    "profit_factor": float(g_pf)
                }

        day_summary = {}
        if "day_of_week" in df.columns:
            for day, group in df.groupby("day_of_week"):
                day_summary[str(day)] = {
                    "count": len(group),
                    "win_rate": (group["pnl_usd"] > 0).mean(),
                    "total_pnl": float(group["pnl_usd"].sum())
                }

        # 4. Exit Reason Breakdown
        exit_summary = {}
        if "exit_reason" in df.columns:
            for ex, group in df.groupby("exit_reason"):
                exit_summary[str(ex)] = {
                    "count": len(group),
                    "win_rate": (group["pnl_usd"] > 0).mean(),
                    "total_pnl": float(group["pnl_usd"].sum()),
                    "avg_pnl": float(group["pnl_usd"].mean())
                }

        # 5. Key Pattern Separators (Winners vs Losers)
        separators = {}
        num_cols = ["atr_at_entry", "rsi_at_entry", "duration_bars", "risk_pct_used"]
        for col in num_cols:
            if col in df.columns:
                w_val = wins[col].mean() if not wins.empty else 0.0
                l_val = losses[col].mean() if not losses.empty else 0.0
                separators[col] = {"winner_avg": float(w_val), "loser_avg": float(l_val), "diff": float(w_val - l_val)}

        return {
            "total_trades": total_trades,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "gross_profit": float(gross_profit),
            "gross_loss": float(gross_loss),
            "expectancy_usd": float(expectancy_usd),
            "expectancy_r": float(expectancy_r),
            "winner_avg_r": float(avg_r_win),
            "loser_avg_r": float(avg_r_loss),
            "volatility_regime_breakdown": vol_summary,
            "mtf_breakdown": mtf_summary,
            "session_breakdown": session_summary,
            "day_breakdown": day_summary,
            "exit_breakdown": exit_summary,
            "pattern_separators": separators
        }

    def generate_report(self, analysis: Dict[str, Any], symbol: str = "BTCUSDT", strat_name: str = "Strategy") -> str:
        """Generates a clean, actionable formatted text report."""
        if analysis.get("status") == "NO_TRADES":
            return "No trades recorded for auto analysis."

        lines = []
        lines.append("=" * 95)
        lines.append(f"   AUTO-ANALYSIS & TRADE JOURNAL REPORT: {symbol} ({strat_name})   ")
        lines.append("=" * 95)

        lines.append(f"Overview Metrics:")
        lines.append(f"  • Total Trades      : {analysis['total_trades']}")
        lines.append(f"  • Win Rate          : {analysis['win_rate']:.2%}")
        lines.append(f"  • Profit Factor     : {analysis['profit_factor']:.2f}")
        lines.append(f"  • Trade Expectancy  : ${analysis['expectancy_usd']:.2f} ({analysis['expectancy_r']:+.2f} R)")
        lines.append(f"  • Avg Winner R      : {analysis['winner_avg_r']:+.2f} R")
        lines.append(f"  • Avg Loser R       : {analysis['loser_avg_r']:+.2f} R")

        lines.append("\n[1] Performance Breakdown by Volatility Regime:")
        for reg, stats_val in analysis.get("volatility_regime_breakdown", {}).items():
            lines.append(f"  -> Regime {reg:<8}: Trades={stats_val['count']:<3} | WinRate={stats_val['win_rate']:>6.2%} | PF={stats_val['profit_factor']:>5.2f} | NetPnL=${stats_val['total_pnl']:>8.2f} | AvgR={stats_val['avg_r']:+.2f}R")

        lines.append("\n[2] Performance Breakdown by MTF Trend Status:")
        for mtf_lbl, stats_val in analysis.get("mtf_breakdown", {}).items():
            lines.append(f"  -> {mtf_lbl:<22}: Trades={stats_val['count']:<3} | WinRate={stats_val['win_rate']:>6.2%} | PF={stats_val['profit_factor']:>5.2f} | NetPnL=${stats_val['total_pnl']:>8.2f}")

        lines.append("\n[3] Session Performance Breakdown (UTC Timezones):")
        for sess, stats_val in analysis.get("session_breakdown", {}).items():
            lines.append(f"  -> Session {sess:<10}: Trades={stats_val['count']:<3} | WinRate={stats_val['win_rate']:>6.2%} | PF={stats_val['profit_factor']:>5.2f} | NetPnL=${stats_val['total_pnl']:>8.2f}")

        lines.append("\n[4] Exit Reason Analysis:")
        for ex, stats_val in analysis.get("exit_breakdown", {}).items():
            lines.append(f"  -> Exit Type {ex:<18}: Trades={stats_val['count']:<3} | WinRate={stats_val['win_rate']:>6.2%} | NetPnL=${stats_val['total_pnl']:>8.2f} | AvgPnL=${stats_val['avg_pnl']:>6.2f}")

        lines.append("\n[5] Key Quantitative Pattern Separators (Winners vs Losers):")
        for feature, vals in analysis.get("pattern_separators", {}).items():
            lines.append(f"  -> {feature:<16}: Winners Avg={vals['winner_avg']:>8.4f} | Losers Avg={vals['loser_avg']:>8.4f} | Diff={vals['diff']:>+8.4f}")

        lines.append("=" * 95 + "\n")
        return "\n".join(lines)

