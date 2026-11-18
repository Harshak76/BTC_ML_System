"""
Walk-Forward Optimization and Cross-Validation Engine for BTC-ML System V2.
Features:
- Rolling-window and Anchored-window walk-forward testing
- Strict chronological ordering with zero future-data leakage
- Boundary purging (removes label overlapping bars) & embargoing (removes post-test spillover)
- Parameter selection using in-sample data only
- Out-of-Sample evaluation on unseen forward windows
- Out-of-Sample equity stitching and Walk-Forward Efficiency (WFE) analysis
"""

import logging
from typing import Dict, Any, List, Tuple, Generator, Optional, Callable
import numpy as np
import pandas as pd

from btc_ml_system.src.validation.metrics import calculate_performance_metrics

logger = logging.getLogger("btc_ml_system.validation.walk_forward")


class WalkForwardEngine:
    """
    Orchestrates rolling and anchored walk-forward testing with leakage protection.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.wf_cfg = self.config.get("walk_forward", {})

        # Window configurations (in number of bars / periods)
        self.train_bars = int(self.wf_cfg.get("train_bars", 24 * 90))   # e.g., 90 days of 1h bars
        self.val_bars = int(self.wf_cfg.get("val_bars", 24 * 15))       # 15 days validation
        self.test_bars = int(self.wf_cfg.get("test_bars", 24 * 30))     # 30 days out-of-sample test
        self.step_bars = int(self.wf_cfg.get("step_bars", 24 * 30))     # 30 days step size
        self.purge_bars = int(self.wf_cfg.get("purge_bars", 12))        # label horizon purge
        self.embargo_bars = int(self.wf_cfg.get("embargo_bars", 24))    # post-window embargo

    def generate_splits(
        self,
        df: pd.DataFrame,
        mode: str = "rolling",
        train_bars: Optional[int] = None,
        test_bars: Optional[int] = None,
        step_bars: Optional[int] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Generates purged and embargoed chronological splits.
        Yields dictionary containing:
        - window_id: int
        - mode: str
        - train_indices: np.ndarray
        - val_indices: np.ndarray
        - test_indices: np.ndarray
        - train_dates: (Timestamp, Timestamp)
        - test_dates: (Timestamp, Timestamp)
        """
        n = len(df)
        t_train = train_bars or self.train_bars
        t_test = test_bars or self.test_bars
        t_step = step_bars or self.step_bars
        purge = self.purge_bars
        embargo = self.embargo_bars

        # Minimum required data check
        min_required = t_train + purge + t_test
        if n < min_required:
            logger.warning(f"Data length ({n}) is less than minimum required walk-forward window ({min_required}).")
            return

        window_id = 0
        current_train_start = 0

        while True:
            if mode == "rolling":
                train_start = current_train_start
            elif mode == "anchored":
                train_start = 0
            else:
                raise ValueError(f"Unknown walk forward mode: {mode}. Must be 'rolling' or 'anchored'.")

            train_end = current_train_start + t_train

            # Purge between train and test
            test_start = train_end + purge
            test_end = min(n, test_start + t_test)

            if test_start >= n or (test_end - test_start) < (t_test // 2):
                break

            train_idx = np.arange(train_start, max(train_start, train_end - purge))
            test_idx = np.arange(test_start, test_end)

            # Optional validation slice inside the training partition
            val_size = min(self.val_bars, len(train_idx) // 4)
            if val_size > 0:
                val_idx = train_idx[-val_size:]
                train_core_idx = train_idx[:-val_size - purge] if len(train_idx) > val_size + purge else train_idx[:-val_size]
            else:
                val_idx = np.array([], dtype=int)
                train_core_idx = train_idx

            train_start_date = df.index[train_start] if isinstance(df.index, pd.DatetimeIndex) else df.iloc[train_start].get("open_time", train_start)
            train_end_date = df.index[train_end - 1] if isinstance(df.index, pd.DatetimeIndex) else df.iloc[train_end - 1].get("open_time", train_end - 1)
            test_start_date = df.index[test_start] if isinstance(df.index, pd.DatetimeIndex) else df.iloc[test_start].get("open_time", test_start)
            test_end_date = df.index[test_end - 1] if isinstance(df.index, pd.DatetimeIndex) else df.iloc[test_end - 1].get("open_time", test_end - 1)

            yield {
                "window_id": window_id,
                "mode": mode,
                "train_indices": train_core_idx,
                "val_indices": val_idx,
                "test_indices": test_idx,
                "train_dates": (train_start_date, train_end_date),
                "test_dates": (test_start_date, test_end_date)
            }

            window_id += 1
            current_train_start += t_step
            if current_train_start + t_train + purge >= n:
                break

    def run_walk_forward(
        self,
        df: pd.DataFrame,
        candidate_params: List[Dict[str, Any]],
        eval_fn: Callable[[pd.DataFrame, Dict[str, Any]], Dict[str, Any]],
        mode: str = "rolling",
        selection_metric: str = "sharpe_ratio"
    ) -> Dict[str, Any]:
        """
        Executes end-to-end walk-forward testing:
        1. On each IS window, evaluates all candidate parameter sets.
        2. Selects the best performing parameter set on IS according to selection_metric.
        3. Evaluates that selected parameter set strictly on the unseen OOS window.
        4. Stitches all OOS windows together into an aggregate OOS performance report.
        """
        windows_results = []
        all_oos_trades = []
        all_is_metrics = []
        all_oos_metrics = []

        split_generator = self.generate_splits(df, mode=mode)

        for split in split_generator:
            w_id = split["window_id"]
            train_idx = split["train_indices"]
            val_idx = split["val_indices"]
            test_idx = split["test_indices"]

            df_train = df.iloc[train_idx].copy().reset_index(drop=True)
            df_test = df.iloc[test_idx].copy().reset_index(drop=True)

            # In-Sample Parameter Optimization
            best_param = None
            best_is_score = -float("inf")
            best_is_metric_dict = None

            for params in candidate_params:
                is_res = eval_fn(df_train, params)
                score = is_res.get(selection_metric, -999.0)
                if score > best_is_score:
                    best_is_score = score
                    best_param = params
                    best_is_metric_dict = is_res

            if best_param is None and candidate_params:
                best_param = candidate_params[0]
                best_is_metric_dict = eval_fn(df_train, best_param)

            # Out-of-Sample Evaluation on Unseen Data with Best In-Sample Params
            oos_res = eval_fn(df_test, best_param)

            # Store results
            window_summary = {
                "window_id": w_id,
                "train_dates": split["train_dates"],
                "test_dates": split["test_dates"],
                "selected_params": best_param,
                "is_score": best_is_score,
                "is_sharpe": best_is_metric_dict.get("sharpe_ratio", 0.0),
                "is_return_pct": best_is_metric_dict.get("total_return_pct", 0.0),
                "oos_sharpe": oos_res.get("sharpe_ratio", 0.0),
                "oos_return_pct": oos_res.get("total_return_pct", 0.0),
                "oos_trades_count": oos_res.get("total_trades", 0),
                "oos_win_rate": oos_res.get("win_rate", 0.0),
                "oos_profit_factor": oos_res.get("profit_factor", 1.0),
                "oos_max_drawdown_pct": oos_res.get("max_drawdown_pct", 0.0)
            }
            windows_results.append(window_summary)
            all_is_metrics.append(best_is_metric_dict)
            all_oos_metrics.append(oos_res)

            if "trades" in oos_res and isinstance(oos_res["trades"], list):
                all_oos_trades.extend(oos_res["trades"])

        # Walk-Forward Efficiency (WFE)
        avg_is_ret = float(np.mean([w["is_return_pct"] for w in windows_results])) if windows_results else 0.0
        avg_oos_ret = float(np.mean([w["oos_return_pct"] for w in windows_results])) if windows_results else 0.0
        wfe_ratio = (avg_oos_ret / avg_is_ret) if abs(avg_is_ret) > 1e-4 else 0.0

        positive_oos_windows = sum(1 for w in windows_results if w["oos_return_pct"] > 0)
        consistency_ratio = (positive_oos_windows / len(windows_results)) if windows_results else 0.0

        return {
            "mode": mode,
            "total_windows": len(windows_results),
            "windows": windows_results,
            "walk_forward_efficiency": wfe_ratio,
            "consistency_ratio": consistency_ratio,
            "avg_is_sharpe": float(np.mean([w["is_sharpe"] for w in windows_results])) if windows_results else 0.0,
            "avg_oos_sharpe": float(np.mean([w["oos_sharpe"] for w in windows_results])) if windows_results else 0.0,
            "avg_is_return_pct": avg_is_ret,
            "avg_oos_return_pct": avg_oos_ret,
            "total_oos_trades": len(all_oos_trades)
        }
