"""
Strict Out-of-Sample (OOS) Holdout Validation Engine for BTC-ML System V2.
Features:
- Chronological reservation of untouched final holdout dataset
- Zero-leakage enforcement (No parameter optimization, feature selection, or tuning on holdout)
- Standalone holdout performance evaluation
- Direct comparison between In-Sample development and Out-of-Sample holdout performance
"""

import logging
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timezone
import numpy as np
import pandas as pd

from btc_ml_system.src.validation.metrics import calculate_performance_metrics, calculate_drawdown_series

logger = logging.getLogger("btc_ml_system.validation.oos_validation")


class OutOfSampleEngine:
    """
    Partitions chronological data into development set (In-Sample) and holdout set (Out-of-Sample).
    Supports both single-asset DataFrames and multi-asset portfolio simulations.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.oos_cfg = self.config.get("oos_validation", {})
        # Default holdout fraction: final 20% of data
        self.holdout_pct = float(self.oos_cfg.get("holdout_pct", 0.20))
        self.purge_bars = int(self.oos_cfg.get("purge_bars", 24))

    def split_holdout(
        self,
        df: pd.DataFrame,
        holdout_pct: Optional[float] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Splits data chronologically into in-sample development set and untouched holdout set.
        Includes a purge buffer between development and holdout to prevent label overlap.
        """
        pct = holdout_pct or self.holdout_pct
        n = len(df)
        split_idx = int(n * (1.0 - pct))

        df_is = df.iloc[: split_idx - self.purge_bars].copy().reset_index(drop=True)
        df_oos = df.iloc[split_idx :].copy().reset_index(drop=True)

        logger.info(f"OOS Holdout Split: In-Sample bars = {len(df_is)}, Holdout bars = {len(df_oos)}, Purge bars = {self.purge_bars}")
        return df_is, df_oos

    def evaluate_holdout(
        self,
        df_is: pd.DataFrame,
        df_oos: pd.DataFrame,
        strategy_params: Dict[str, Any],
        eval_fn: Callable[[pd.DataFrame, Dict[str, Any]], Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluates the fixed strategy configuration on both In-Sample and untouched Holdout.
        """
        is_metrics = eval_fn(df_is, strategy_params)
        oos_metrics = eval_fn(df_oos, strategy_params)

        # Performance retention ratio
        is_sharpe = is_metrics.get("sharpe_ratio", 0.0)
        oos_sharpe = oos_metrics.get("sharpe_ratio", 0.0)
        sharpe_retention = (oos_sharpe / is_sharpe) if abs(is_sharpe) > 1e-4 else 0.0

        is_ret = is_metrics.get("total_return_pct", 0.0)
        oos_ret = oos_metrics.get("total_return_pct", 0.0)
        return_retention = (oos_ret / is_ret) if abs(is_ret) > 1e-4 else 0.0

        return {
            "in_sample": is_metrics,
            "out_of_sample": oos_metrics,
            "sharpe_retention_ratio": sharpe_retention,
            "return_retention_ratio": return_retention,
            "is_holdout_profitable": bool(oos_metrics.get("total_return_pct", 0.0) > 0.0),
            "holdout_drawdown_acceptable": bool(oos_metrics.get("max_drawdown_pct", 0.0) <= 10.0),
            "passed_oos_gate": bool(
                oos_metrics.get("total_return_pct", 0.0) > 0.0 and
                oos_metrics.get("max_drawdown_pct", 0.0) <= 10.0 and
                oos_metrics.get("profit_factor", 0.0) >= 1.0
            ),
            "is_contaminated": True,
            "contamination_note": "Single-asset dataset has been previously inspected during backtest iterations."
        }

    def evaluate_portfolio_holdout(
        self,
        portfolio_config: Dict[str, Any],
        asset_configs: Dict[str, Dict[str, Any]],
        prepared_asset_dfs: Optional[Dict[str, pd.DataFrame]] = None,
        holdout_pct: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Executes a genuine independent portfolio simulation on the quarantined chronological holdout slice.
        
        Requirements Enforced (Phase 2.2 Correction):
        ---------------------------------------------
        1. Exact Date Boundaries:
           Computes global chronological bounds across all symbols. Slices development (In-Sample)
           and final holdout (Out-of-Sample) using an explicit purge buffer.
        2. Zero Leakage & Boundary Quarantine:
           No parameter fitting or feature scaling across the split boundary.
        3. Portfolio State Initialization:
           Initializes holdout cash cleanly to portfolio initial_capital ($100k).
           Enforces a flat start (open positions = 0); boundary-crossing positions are closed at split time.
        4. Independent Drawdown & Performance Calculation:
           Reconstructs holdout equity curve and computes holdout max drawdown directly from
           the holdout equity series itself (NEVER copied from total portfolio backtest).
        5. Contamination Tracking:
           Flags is_contaminated=True because the 2024-2026 dataset has been repeatedly queried during research.
        """
        from btc_ml_system.src.portfolio_manager import PortfolioManager
        from btc_ml_system.src.data_provider import DataProvider
        from btc_ml_system.src.regimes import VolatilityRegimeClassifier
        from btc_ml_system.src.direction import SessionFilter
        from btc_ml_system.src.strategies import StrategyFactory
        from btc_ml_system.src.signal_engine import SignalEngine

        pct = holdout_pct or self.holdout_pct

        # 1. Prepare/Load Signal DataFrames for all symbols if not provided
        asset_dfs = {}
        if prepared_asset_dfs:
            asset_dfs = {sym: df.copy() for sym, df in prepared_asset_dfs.items()}
        else:
            for sym, cfg in asset_configs.items():
                if "prepared_df" in cfg:
                    asset_dfs[sym] = cfg["prepared_df"].copy()
                else:
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
                    asset_dfs[sym] = df_strat

        # 2. Find Unified Chronological Time Bounds
        all_timestamps = set()
        for sym, df in asset_dfs.items():
            ts = pd.to_datetime(df["open_time"], utc=True)
            all_timestamps.update(ts)
        sorted_timestamps = sorted(list(all_timestamps))
        n_bars = len(sorted_timestamps)

        split_idx = int(n_bars * (1.0 - pct))
        purge_idx = max(0, split_idx - self.purge_bars)

        train_start = sorted_timestamps[0]
        train_end = sorted_timestamps[purge_idx]
        holdout_start = sorted_timestamps[split_idx]
        holdout_end = sorted_timestamps[-1]

        logger.info(
            f"Independent Portfolio Holdout Split: "
            f"Train [{train_start} to {train_end}] ({purge_idx + 1} bars) | "
            f"Holdout [{holdout_start} to {holdout_end}] ({n_bars - split_idx} bars)"
        )

        # 3. Partition DataFrames by Date Bounds
        is_asset_configs = {}
        oos_asset_configs = {}
        for sym, cfg in asset_configs.items():
            df_full = asset_dfs[sym]
            df_full["dt_utc"] = pd.to_datetime(df_full["open_time"], utc=True)

            # In-Sample slice
            df_is = df_full[df_full["dt_utc"] <= train_end].copy().drop(columns=["dt_utc"]).reset_index(drop=True)
            cfg_is = dict(cfg)
            cfg_is["prepared_df"] = df_is
            is_asset_configs[sym] = cfg_is

            # Out-of-Sample slice
            df_oos = df_full[df_full["dt_utc"] >= holdout_start].copy().drop(columns=["dt_utc"]).reset_index(drop=True)
            cfg_oos = dict(cfg)
            cfg_oos["prepared_df"] = df_oos
            oos_asset_configs[sym] = cfg_oos

        # 4. Execute Independent In-Sample Simulation
        pm_is = PortfolioManager(portfolio_config)
        is_results = pm_is.run_portfolio_backtest(is_asset_configs)
        is_trades = is_results.get("trades", [])
        is_eq = [step["equity"] for step in is_results.get("equity_curve", [])]
        is_metrics = calculate_performance_metrics(
            trades=is_trades,
            equity_curve=is_eq,
            initial_capital=portfolio_config.get("portfolio", {}).get("initial_capital", 100000.0),
            periods_per_year=252 * 24,
            is_crypto=True
        )

        # 5. Execute Independent Holdout Simulation
        # Initialize holdout state cleanly: cash = initial_capital, open_positions = 0
        pm_oos = PortfolioManager(portfolio_config)
        oos_results = pm_oos.run_portfolio_backtest(oos_asset_configs)
        oos_trades = oos_results.get("trades", [])
        oos_eq = [step["equity"] for step in oos_results.get("equity_curve", [])]
        oos_metrics = calculate_performance_metrics(
            trades=oos_trades,
            equity_curve=oos_eq,
            initial_capital=portfolio_config.get("portfolio", {}).get("initial_capital", 100000.0),
            periods_per_year=252 * 24,
            is_crypto=True
        )

        # 6. Retention Ratios
        is_sharpe = is_metrics.get("sharpe_ratio", 0.0)
        oos_sharpe = oos_metrics.get("sharpe_ratio", 0.0)
        sharpe_retention = (oos_sharpe / is_sharpe) if abs(is_sharpe) > 1e-4 else 0.0

        is_ret = is_metrics.get("total_return_pct", 0.0)
        oos_ret = oos_metrics.get("total_return_pct", 0.0)
        return_retention = (oos_ret / is_ret) if abs(is_ret) > 1e-4 else 0.0

        return {
            "date_boundaries": {
                "train_start": str(train_start),
                "train_end": str(train_end),
                "holdout_start": str(holdout_start),
                "holdout_end": str(holdout_end),
                "purge_bars": self.purge_bars,
                "total_timeline_bars": n_bars,
                "holdout_fraction": pct
            },
            "in_sample": is_metrics,
            "out_of_sample": oos_metrics,
            "sharpe_retention_ratio": sharpe_retention,
            "return_retention_ratio": return_retention,
            "is_holdout_profitable": bool(oos_metrics.get("total_return_pct", 0.0) > 0.0),
            "holdout_drawdown_acceptable": bool(oos_metrics.get("max_drawdown_pct", 0.0) <= 10.0),
            "passed_oos_gate": bool(
                oos_metrics.get("total_return_pct", 0.0) > 0.0 and
                oos_metrics.get("max_drawdown_pct", 0.0) <= 10.0 and
                oos_metrics.get("profit_factor", 0.0) >= 1.0
            ),
            "is_contaminated": True,
            "contamination_note": (
                "The historical 2024–2026 multi-asset dataset was repeatedly inspected during Phase 0-2 research. "
                "This chronological holdout slice is statistically contaminated by repeated backtesting. "
                "A fresh forward dataset or live paper trading buffer is mandatory prior to live trading certification."
            ),
            "holdout_trades_count": len(oos_trades),
            "holdout_final_equity": oos_eq[-1] if oos_eq else portfolio_config.get("portfolio", {}).get("initial_capital", 100000.0)
        }
