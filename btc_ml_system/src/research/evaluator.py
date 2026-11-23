"""
Comprehensive Research Strategy Evaluator for BTC-ML System V2.
Orchestrates independent candidate evaluations across supported assets:
- Equities: AAPL, MSFT, NVDA, TSLA, AMZN
- Crypto: BTCUSDT, ETHUSDT
Computes benchmarks, regime breakdowns, calendar breakdowns, robustness stress tests,
genuine CSCV/PBO matrices, Deflated Sharpe Ratios, and logs to DuckDB experiment_registry.
"""

import os
import glob
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from btc_ml_system.src.research.base import BaseResearchStrategy, ReturnUnit
from btc_ml_system.src.research.registry import ResearchStrategyRegistry
from btc_ml_system.src.research.runner import ResearchSimulationRunner
from btc_ml_system.src.research.candidate_matrix import GenuineCandidateMatrixBuilder
from btc_ml_system.src.validation.metrics import (
    calculate_performance_metrics,
    calculate_drawdown_series,
    calculate_returns_series
)
from btc_ml_system.src.validation.pbo_cscv import PBOCSCVEngine
from btc_ml_system.src.validation.deflated_sharpe import DeflatedSharpeEngine
from btc_ml_system.src.validation.experiment_tracker import ExperimentTracker

logger = logging.getLogger("btc_ml_system.research.evaluator")


class ResearchEvaluator:
    """
    Independent Research Strategy Evaluator for Phase 3B.
    Guarantees strict offline execution, zero broker connections,
    and genuine return streams without synthetic perturbation.
    """

    SUPPORTED_EQUITIES = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN"]
    SUPPORTED_CRYPTO = ["BTCUSDT", "ETHUSDT"]
    ALL_ASSETS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "BTCUSDT", "ETHUSDT"]

    def __init__(
        self,
        data_dir: Optional[str] = None,
        db_path: Optional[str] = None,
        initial_capital: float = 100000.0,
        random_seed: int = 42
    ):
        if data_dir:
            resolved = Path(data_dir).resolve()
            if not resolved.exists():
                raise FileNotFoundError(f"Explicitly specified data_dir does not exist: {resolved}")
            self.data_dir = resolved
        else:
            # Reliably locate the authentic dataset directory from repository roots and working directories
            evaluator_path = Path(__file__).resolve()
            possible_roots = [
                Path.cwd(),                                # Current working directory
                evaluator_path.parents[3],                 # Repository root (BTC_ML_System)
                evaluator_path.parent.parent.parent,       # Package root (btc_ml_system)
            ]
            found_auth_dir = None
            for r in possible_roots:
                cand = r / "data" / "authentic_raw"
                if cand.exists() and any(cand.glob("*.csv")):
                    found_auth_dir = cand.resolve()
                    break

            if found_auth_dir is None:
                for parent in evaluator_path.parents:
                    cand = parent / "data" / "authentic_raw"
                    if cand.exists() and any(cand.glob("*.csv")):
                        found_auth_dir = cand.resolve()
                        break

            if found_auth_dir is None:
                raise FileNotFoundError(
                    "Authentic data directory 'data/authentic_raw' could not be resolved from working directory "
                    f"({Path.cwd()}) or repository structure. Silent fallback to legacy cloned data in 'data/raw' "
                    "is strictly forbidden."
                )

            self.data_dir = found_auth_dir

        logger.info(f"Resolved authentic data directory: {self.data_dir.resolve()}")

        self.initial_capital = initial_capital
        self.random_seed = random_seed
        self.tracker = ExperimentTracker(db_path=db_path)
        self.pbo_engine = PBOCSCVEngine({"pbo_cscv": {"n_blocks": 10, "random_seed": random_seed}})
        self.dsr_engine = DeflatedSharpeEngine()

    def load_asset_data(self, symbol: str, preferred_timeframe: Optional[str] = None) -> pd.DataFrame:
        """
        Loads raw historical market data for a given asset.
        Supports 1h, 4h, and 1d candles from data/raw.
        """
        sym_clean = symbol.lower().replace("usdt", "")
        sym_full = symbol.lower()

        # Prioritize candidate files
        tf_candidates = [preferred_timeframe] if preferred_timeframe else []
        if symbol in self.SUPPORTED_CRYPTO:
            if symbol == "BTCUSDT":
                tf_candidates.extend(["4h", "1h", "1d"])
            else:
                tf_candidates.extend(["1h", "4h"])
        else:
            tf_candidates.extend(["1h", "1d"])

        found_path = None
        for tf in tf_candidates:
            if not tf:
                continue
            cand_paths = [
                self.data_dir / f"{sym_full}_{tf}.csv",
                self.data_dir / f"{sym_clean}_{tf}.csv",
            ]
            for p in cand_paths:
                if p.exists():
                    found_path = p
                    break
            if found_path:
                break

        if not found_path:
            raise FileNotFoundError(f"Could not find market data file for {symbol} in {self.data_dir}")

        df = pd.read_csv(found_path)
        if "open_time" not in df.columns:
            raise ValueError(f"Data file {found_path} missing open_time column.")

        df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
        df = df.sort_values("open_time").drop_duplicates(subset=["open_time"]).reset_index(drop=True)

        # Ensure required OHLCV columns
        for c in ["open", "high", "low", "close", "volume"]:
            if c not in df.columns:
                raise ValueError(f"Data file {found_path} missing column: {c}")
            df[c] = pd.to_numeric(df[c], errors="coerce")

        df = df.dropna(subset=["open", "high", "low", "close", "volume"]).reset_index(drop=True)
        return df

    def validate_dataset(
        self,
        data_dict: Dict[str, pd.DataFrame],
        expected_symbols: Optional[List[str]] = None
    ) -> bool:
        """
        Validates that all expected symbols are present and contain valid OHLCV columns
        with zero missing or corrupted values prior to simulation execution.
        """
        expected = expected_symbols or self.ALL_ASSETS
        missing = [sym for sym in expected if sym not in data_dict]
        if missing:
            raise ValueError(
                f"Universe validation failed: missing expected assets {missing}. "
                f"Loaded assets: {list(data_dict.keys())}"
            )

        required_cols = ["open_time", "open", "high", "low", "close", "volume"]
        for sym, df in data_dict.items():
            if df is None or len(df) == 0:
                raise ValueError(f"Universe validation failed: asset {sym} contains empty DataFrame.")
            missing_cols = [c for c in required_cols if c not in df.columns]
            if missing_cols:
                raise ValueError(f"Universe validation failed for {sym}: missing required columns {missing_cols}.")
            null_count = int(df[required_cols].isnull().sum().sum())
            if null_count > 0:
                raise ValueError(f"Universe validation failed for {sym}: {null_count} null values found in OHLCV columns.")

        return True

    def compute_buy_and_hold_benchmark(
        self,
        symbol: str,
        df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Computes Buy-and-Hold benchmark equity curve and performance metrics.
        Incurs realistic entry/exit slippage and commission.
        """
        is_crypto = symbol in self.SUPPORTED_CRYPTO
        slip_bps = 5.0 if is_crypto else 2.0
        comm_bps = 10.0 if is_crypto else 0.0

        p_entry = float(df["open"].iloc[0]) * (1.0 + (slip_bps / 10000.0))
        qty = self.initial_capital / p_entry

        equity_curve = []
        for _, row in df.iterrows():
            close_p = float(row["close"])
            eq = qty * close_p
            equity_curve.append(eq)

        # Terminal exit adjustment
        p_exit = float(df["close"].iloc[-1]) * (1.0 - (slip_bps / 10000.0))
        final_eq = qty * p_exit * (1.0 - (comm_bps / 10000.0))
        equity_curve[-1] = final_eq

        periods_per_year = (365 * 24) if is_crypto else int(252 * 6.5)
        trade = [{
            "symbol": symbol,
            "entry_time": str(df["open_time"].iloc[0]),
            "exit_time": str(df["open_time"].iloc[-1]),
            "entry_price": p_entry,
            "exit_price": p_exit,
            "pnl_usd": final_eq - self.initial_capital,
            "pnl_pct": ((final_eq - self.initial_capital) / self.initial_capital) * 100.0,
            "duration_bars": len(df),
            "reason": "TERMINAL_HOLD"
        }]

        metrics = calculate_performance_metrics(
            trades=trade,
            equity_curve=equity_curve,
            initial_capital=self.initial_capital,
            periods_per_year=periods_per_year,
            is_crypto=is_crypto
        )

        return {
            "benchmark_name": "Buy_and_Hold",
            "symbol": symbol,
            "metrics": metrics,
            "equity_curve": equity_curve
        }

    def compute_cash_benchmark(self, n_bars: int) -> Dict[str, Any]:
        """Computes cash / zero-exposure baseline (0% return, 0 drawdown)."""
        equity_curve = [self.initial_capital] * n_bars
        return {
            "benchmark_name": "Cash_Baseline",
            "metrics": {
                "total_return_pct": 0.0,
                "cagr_pct": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "max_drawdown_pct": 0.0,
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 1.0,
                "expectancy_usd": 0.0,
                "exposure_pct": 0.0
            },
            "equity_curve": equity_curve
        }

    def compute_sma_trend_benchmark(
        self,
        symbol: str,
        df: pd.DataFrame,
        sma_period: int = 50
    ) -> Dict[str, Any]:
        """
        Simple Moving Average trend filter benchmark (Long when Price > SMA(50), flat otherwise).
        Enforces next-bar open execution and transaction frictions.
        """
        is_crypto = symbol in self.SUPPORTED_CRYPTO
        slip_bps = 5.0 if is_crypto else 2.0
        comm_bps = 10.0 if is_crypto else 0.0

        close = df["close"]
        sma = close.rolling(window=sma_period).mean()

        cash = self.initial_capital
        pos_qty = 0.0
        entry_price = 0.0
        trades = []
        equity_curve = []

        pending_signal = 0

        for idx, row in df.iterrows():
            p_open = float(row["open"])
            p_close = float(row["close"])
            curr_sma = sma.iloc[idx]

            # Execute pending signal on open
            if pending_signal == 1 and pos_qty == 0.0:
                fill_p = p_open * (1.0 + (slip_bps / 10000.0))
                pos_qty = cash / fill_p
                entry_price = fill_p
                cash = 0.0
            elif pending_signal == 0 and pos_qty > 0.0:
                fill_p = p_open * (1.0 - (slip_bps / 10000.0))
                net_p = fill_p * (1.0 - (comm_bps / 10000.0))
                pnl = (net_p - entry_price) * pos_qty
                cash = pos_qty * net_p
                trades.append({
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "exit_price": net_p,
                    "pnl_usd": pnl,
                    "duration_bars": 1
                })
                pos_qty = 0.0

            # Current mark-to-market
            curr_eq = cash + (pos_qty * p_close)
            equity_curve.append(curr_eq)

            # Signal evaluation at bar close
            if not np.isnan(curr_sma):
                pending_signal = 1 if p_close > curr_sma else 0

        periods_per_year = (365 * 24) if is_crypto else int(252 * 6.5)
        metrics = calculate_performance_metrics(
            trades=trades,
            equity_curve=equity_curve,
            initial_capital=self.initial_capital,
            periods_per_year=periods_per_year,
            is_crypto=is_crypto
        )

        return {
            "benchmark_name": f"SMA_{sma_period}_Trend",
            "symbol": symbol,
            "metrics": metrics,
            "equity_curve": equity_curve
        }

    def compute_asset_regime_features(
        self,
        df: pd.DataFrame,
        rolling_window: int = 250
    ) -> pd.DataFrame:
        """
        Classifies historical market into volatility and directional regimes independently for an asset.
        Guarantees zero full-sample lookahead by using strictly backward-looking rolling quantiles.
        """
        out = df.copy()
        close = out["close"]
        high = out["high"]
        low = out["low"]

        # 1. Volatility Regime: 20-period ATR normalized by price
        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        norm_vol = (tr.rolling(20).mean() / (close + 1e-12)) * 100.0

        # Point-in-time rolling quantiles (strictly backward-looking, zero lookahead)
        min_p = min(20, max(5, len(out) // 4))
        p33_series = norm_vol.rolling(rolling_window, min_periods=min_p).quantile(0.33)
        p67_series = norm_vol.rolling(rolling_window, min_periods=min_p).quantile(0.67)

        vol_regimes = pd.Series("NORMAL", index=out.index, dtype=object)
        vol_regimes[norm_vol <= p33_series] = "CALM"
        vol_regimes[norm_vol > p67_series] = "HIGH"
        vol_regimes[norm_vol.isna() | p33_series.isna()] = "WARMUP_UNCLASSIFIED"

        # 2. Directional Regime: 14-period ADX
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        tr_smooth = tr.rolling(14).sum()
        plus_di = 100.0 * (pd.Series(plus_dm, index=out.index).rolling(14).sum() / (tr_smooth + 1e-12))
        minus_di = 100.0 * (pd.Series(minus_dm, index=out.index).rolling(14).sum() / (tr_smooth + 1e-12))
        dx = 100.0 * (plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-12)
        adx = dx.rolling(14).mean()

        dir_regimes = pd.Series("NEUTRAL", index=out.index, dtype=object)
        dir_regimes[adx < 20.0] = "RANGING"
        dir_regimes[adx >= 25.0] = "TRENDING"
        dir_regimes[adx.isna()] = "WARMUP_UNCLASSIFIED"

        out["vol_regime"] = vol_regimes
        out["dir_regime"] = dir_regimes
        out["dt_str"] = out["open_time"].astype(str)
        return out

    def evaluate_regimes(
        self,
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        trades: List[Dict[str, Any]],
        rolling_window: int = 250
    ) -> Dict[str, Any]:
        """
        Classifies market into point-in-time volatility and directional regimes per asset,
        and aggregates strategy trade performance across each regime using composite key (asset, entry_time).
        Does NOT default unmatched trades to RANGING or NORMAL.
        """
        if isinstance(data, pd.DataFrame):
            data_dict = {"DEFAULT": data}
        elif isinstance(data, dict):
            data_dict = data
        else:
            raise TypeError("data must be a pd.DataFrame or Dict[str, pd.DataFrame]")

        # Build composite regime map: (symbol, entry_time_str) -> {vol_regime, dir_regime, feature_time}
        composite_regime_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for sym, df_raw in data_dict.items():
            features_df = self.compute_asset_regime_features(df_raw, rolling_window=rolling_window)
            for _, row in features_df.iterrows():
                ts_str = str(row["dt_str"])
                composite_regime_map[(sym, ts_str)] = {
                    "vol_regime": row["vol_regime"],
                    "dir_regime": row["dir_regime"],
                    "feature_time": ts_str
                }
                if len(data_dict) == 1:
                    composite_regime_map[("DEFAULT", ts_str)] = composite_regime_map[(sym, ts_str)]

        regime_stats = {
            "CALM": {"trades": 0, "wins": 0, "pnl_usd": 0.0},
            "NORMAL": {"trades": 0, "wins": 0, "pnl_usd": 0.0},
            "HIGH": {"trades": 0, "wins": 0, "pnl_usd": 0.0},
            "TRENDING": {"trades": 0, "wins": 0, "pnl_usd": 0.0},
            "RANGING": {"trades": 0, "wins": 0, "pnl_usd": 0.0},
            "NEUTRAL": {"trades": 0, "wins": 0, "pnl_usd": 0.0},
            "WARMUP_UNCLASSIFIED": {"trades": 0, "wins": 0, "pnl_usd": 0.0}
        }

        matched_trades = 0
        unmatched_trades = []

        for t in trades:
            e_time = str(t.get("entry_time", ""))
            sym = t.get("symbol") or t.get("asset") or "DEFAULT"
            pnl = float(t.get("pnl_usd", 0.0))
            is_win = pnl > 0

            # Match on composite key (asset, entry_timestamp)
            key = (sym, e_time)
            info = composite_regime_map.get(key)
            if info is None and len(data_dict) == 1:
                info = composite_regime_map.get(("DEFAULT", e_time))

            if info is None:
                # Explicit unmatched handling - DO NOT default to RANGING or NORMAL
                unmatched_trades.append({
                    "symbol": sym,
                    "entry_time": e_time,
                    "pnl_usd": pnl
                })
                continue

            matched_trades += 1
            v_reg = info["vol_regime"]
            d_reg = info["dir_regime"]

            for reg in (v_reg, d_reg):
                if reg in regime_stats:
                    regime_stats[reg]["trades"] += 1
                    if is_win:
                        regime_stats[reg]["wins"] += 1
                    regime_stats[reg]["pnl_usd"] += pnl

        # Calculate win rates
        for reg, st in regime_stats.items():
            st["win_rate"] = (st["wins"] / st["trades"]) if st["trades"] > 0 else 0.0

        regime_stats["total_trades_evaluated"] = len(trades)
        regime_stats["matched_trades_count"] = matched_trades
        regime_stats["unmatched_trades_count"] = len(unmatched_trades)
        regime_stats["unmatched_trades"] = unmatched_trades

        return regime_stats

    def evaluate_calendar_periods(
        self,
        trades: List[Dict[str, Any]],
        equity_curve: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Breaks down performance by calendar year."""
        yearly_trades: Dict[str, List[Dict[str, Any]]] = {}
        for t in trades:
            e_time = str(t.get("entry_time", ""))
            year = e_time[:4] if len(e_time) >= 4 else "UNKNOWN"
            yearly_trades.setdefault(year, []).append(t)

        results = {}
        for y, t_list in sorted(yearly_trades.items()):
            pnls = [float(tr.get("pnl_usd", 0.0)) for tr in t_list]
            wins = [p for p in pnls if p > 0]
            results[y] = {
                "total_trades": len(t_list),
                "total_pnl_usd": sum(pnls),
                "win_rate": len(wins) / len(t_list) if t_list else 0.0,
                "avg_trade_usd": np.mean(pnls) if pnls else 0.0
            }
        return results

    def run_robustness_battery(
        self,
        strategy: BaseResearchStrategy,
        data_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """
        Runs comprehensive sensitivity stress battery:
        - Baseline
        - Cost Stress (2x slippage & commission)
        - Latency Stress (1-bar execution delay)
        - Missed Trades Stress (10% random drops)
        - Subperiod Splits (First 50% vs Second 50%)
        """
        runner_base = ResearchSimulationRunner(strategy, initial_capital=self.initial_capital)
        base_res = runner_base.run_simulation(data_dict)

        # 1. Cost Stress (2x transaction frictions)
        runner_cost = ResearchSimulationRunner(strategy, initial_capital=self.initial_capital, cost_multiplier=2.0)
        cost_res = runner_cost.run_simulation(data_dict)

        # 2. Latency Stress (1-bar execution delay)
        runner_delay = ResearchSimulationRunner(strategy, initial_capital=self.initial_capital, execution_delay_bars=1)
        delay_res = runner_delay.run_simulation(data_dict)

        # 3. Missed Trades Stress (10% drop probability)
        runner_miss = ResearchSimulationRunner(strategy, initial_capital=self.initial_capital, drop_trade_prob=0.10, random_seed=self.random_seed)
        miss_res = runner_miss.run_simulation(data_dict)

        # 4. Chronological Subperiods (First Half vs Second Half)
        sub_h1_data = {}
        sub_h2_data = {}
        for sym, df in data_dict.items():
            mid = len(df) // 2
            sub_h1_data[sym] = df.iloc[:mid].reset_index(drop=True)
            sub_h2_data[sym] = df.iloc[mid:].reset_index(drop=True)

        h1_res = runner_base.run_simulation(sub_h1_data)
        h2_res = runner_base.run_simulation(sub_h2_data)

        return {
            "baseline": {
                "sharpe": base_res["metrics"]["sharpe_ratio"],
                "total_return_pct": base_res["metrics"]["total_return_pct"],
                "max_dd_pct": base_res["metrics"]["max_drawdown_pct"],
                "trades": base_res["total_trades"]
            },
            "cost_stress_2x": {
                "sharpe": cost_res["metrics"]["sharpe_ratio"],
                "total_return_pct": cost_res["metrics"]["total_return_pct"],
                "max_dd_pct": cost_res["metrics"]["max_drawdown_pct"],
                "trades": cost_res["total_trades"]
            },
            "latency_stress_1bar": {
                "sharpe": delay_res["metrics"]["sharpe_ratio"],
                "total_return_pct": delay_res["metrics"]["total_return_pct"],
                "max_dd_pct": delay_res["metrics"]["max_drawdown_pct"],
                "trades": delay_res["total_trades"]
            },
            "missed_trades_10pct": {
                "sharpe": miss_res["metrics"]["sharpe_ratio"],
                "total_return_pct": miss_res["metrics"]["total_return_pct"],
                "max_dd_pct": miss_res["metrics"]["max_drawdown_pct"],
                "trades": miss_res["total_trades"]
            },
            "subperiod_first_half": {
                "sharpe": h1_res["metrics"]["sharpe_ratio"],
                "total_return_pct": h1_res["metrics"]["total_return_pct"],
                "max_dd_pct": h1_res["metrics"]["max_drawdown_pct"],
                "trades": h1_res["total_trades"]
            },
            "subperiod_second_half": {
                "sharpe": h2_res["metrics"]["sharpe_ratio"],
                "total_return_pct": h2_res["metrics"]["total_return_pct"],
                "max_dd_pct": h2_res["metrics"]["max_drawdown_pct"],
                "trades": h2_res["total_trades"]
            }
        }

    def run_all_evaluations(
        self,
        strategy_ids: Optional[List[str]] = None,
        assets: Optional[List[str]] = None,
        log_to_registry: bool = True
    ) -> Dict[str, Any]:
        """
        Executes the full Phase 3B evaluation pipeline across all strategies and assets.
        Guarantees genuine candidate matrix construction and DuckDB logging.
        """
        target_strategies = strategy_ids or [
            "RS_TF_DUAL_EMA_21_55_V1",
            "RS_TF_DUAL_EMA_20_50_V1",
            "RS_TF_DUAL_EMA_50_100_V1",
            "RS_MOM_DONCHIAN_20_V1",
            "RS_MOM_DONCHIAN_40_V1",
            "RS_MOM_DONCHIAN_55_V1",
            "RS_MR_BB_RSI_20_STD_V1",
            "RS_MR_BB_RSI_22_STD_V1",
            "RS_MR_BB_RSI_25_STD_V1",
        ]
        target_assets = assets or self.ALL_ASSETS

        # 1. Load Data for all assets
        data_dict = {}
        for sym in target_assets:
            data_dict[sym] = self.load_asset_data(sym)
            logger.info(f"Loaded {sym}: {len(data_dict[sym])} bars.")

        # Validate universe dataset integrity before simulation
        self.validate_dataset(data_dict, expected_symbols=target_assets)

        # 2. Benchmarks for each asset
        benchmarks = {}
        for sym, df in data_dict.items():
            bh = self.compute_buy_and_hold_benchmark(sym, df)
            cash = self.compute_cash_benchmark(len(df))
            sma = self.compute_sma_trend_benchmark(sym, df)
            benchmarks[sym] = {
                "buy_and_hold": bh["metrics"],
                "cash_baseline": cash["metrics"],
                "sma_50_trend": sma["metrics"]
            }

        # 3. Evaluate each strategy
        strategy_results = {}
        asset_level_results: Dict[str, Dict[str, Any]] = {}
        multi_asset_sim_results = []
        registered_experiments = []

        for strat_id in target_strategies:
            strat = ResearchStrategyRegistry.get(strat_id)
            meta = strat.metadata

            # A. Multi-Asset Portfolio Simulation
            runner = ResearchSimulationRunner(strat, initial_capital=self.initial_capital)
            sim_res = runner.run_simulation(data_dict)
            multi_asset_sim_results.append(sim_res)

            # B. Asset-Level Simulations
            asset_res_map = {}
            for sym, df in data_dict.items():
                runner_single = ResearchSimulationRunner(strat, initial_capital=self.initial_capital)
                single_res = runner_single.run_simulation({sym: df})
                asset_res_map[sym] = {
                    "metrics": single_res["metrics"],
                    "total_trades": single_res["total_trades"]
                }
                asset_level_results.setdefault(sym, {})[strat_id] = single_res["metrics"]

            # C. Regime Analysis (using multi-asset dataset with composite (asset, timestamp) key)
            regimes = self.evaluate_regimes(data_dict, sim_res["trades"])

            # D. Calendar Period Breakdown
            calendar = self.evaluate_calendar_periods(sim_res["trades"], sim_res["equity_curve"])

            # E. Robustness Battery
            robustness = self.run_robustness_battery(strat, data_dict)

            # F. Log Experiment to DuckDB
            exp_id = self.tracker.create_experiment_id()
            if log_to_registry:
                try:
                    self.tracker.log_experiment(
                        experiment_id=exp_id,
                        strategy_name=meta.strategy_name,
                        strategy_version=meta.version,
                        asset="MULTI_ASSET",
                        timeframe="1h_4h",
                        parameter_config=meta.parameters_schema,
                        dataset_info={
                            "symbols": list(data_dict.keys()),
                            "date_range": "2024-2026",
                            "n_assets": len(data_dict)
                        },
                        validation_results={
                            "metrics": sim_res["metrics"],
                            "robustness": robustness,
                            "regimes": regimes
                        },
                        candidate_count=len(target_strategies),
                        completed_trials=1,
                        return_frequency="1h"
                    )
                    registered_experiments.append(exp_id)
                except Exception as e:
                    logger.warning(f"Could not log experiment {exp_id} to DuckDB: {e}")

            strategy_results[strat_id] = {
                "metadata": meta,
                "portfolio_metrics": sim_res["metrics"],
                "asset_metrics": asset_res_map,
                "regimes": regimes,
                "calendar": calendar,
                "robustness": robustness,
                "experiment_id": exp_id
            }

        # 4. Genuine Candidate Matrix & CSCV / PBO Analysis
        candidate_matrix_info = GenuineCandidateMatrixBuilder.build_matrix(multi_asset_sim_results)

        pbo_result = None
        if candidate_matrix_info.get("is_sufficient_for_pbo") and candidate_matrix_info.get("candidates_matrix") is not None:
            pbo_result = self.pbo_engine.compute_pbo_from_returns_matrix(candidate_matrix_info["candidates_matrix"])
        else:
            pbo_result = {
                "status": "INCOMPLETE",
                "reason": candidate_matrix_info.get("reason", "Insufficient candidates or length for PBO."),
                "pbo": None
            }

        # 5. Deflated Sharpe Ratio calculation
        all_sharpes = [res["metrics"]["sharpe_ratio"] for res in multi_asset_sim_results]
        top_idx = int(np.argmax(all_sharpes)) if all_sharpes else 0
        top_strat_id = target_strategies[top_idx] if target_strategies else "None"
        top_sim = multi_asset_sim_results[top_idx] if multi_asset_sim_results else None

        dsr_result = None
        if top_sim is not None:
            dsr_result = self.dsr_engine.calculate_dsr(
                observed_sharpe=top_sim["metrics"]["sharpe_ratio"],
                n_observations=len(top_sim["periodic_returns_pct"]),
                all_trial_sharpes=all_sharpes,
                returns=top_sim["periodic_returns_pct"] / 100.0,
                annualization_factor=252 * 24
            )

        return {
            "strategy_results": strategy_results,
            "asset_level_results": asset_level_results,
            "benchmarks": benchmarks,
            "candidate_matrix_info": candidate_matrix_info,
            "pbo_result": pbo_result,
            "dsr_result": dsr_result,
            "top_candidate": {
                "strategy_id": top_strat_id,
                "sharpe": all_sharpes[top_idx] if all_sharpes else 0.0
            },
            "registered_experiments": registered_experiments
        }
