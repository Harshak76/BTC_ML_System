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
import numpy as np
import pandas as pd

from btc_ml_system.src.validation.metrics import calculate_performance_metrics

logger = logging.getLogger("btc_ml_system.validation.oos_validation")


class OutOfSampleEngine:
    """
    Partitions chronological data into development set (In-Sample) and holdout set (Out-of-Sample).
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
            )
        }
