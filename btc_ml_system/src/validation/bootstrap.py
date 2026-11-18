"""
Bootstrap Validation Engine for BTC-ML System V2.
Features:
- Trade-return IID bootstrap resampling
- Moving Block Bootstrap (preserves short-term serial autocorrelation)
- Stationary Bootstrap (Politis & Romano 1994, random geometric block sizes)
- Configurable simulation iterations & reproducible random seeds
- Non-parametric Confidence Intervals (90%, 95%, 99%)
- Full distributions of Total Return, Sharpe Ratio, Win Rate, and Max Drawdown
- Empirical Probability of Negative Return & Risk of Ruin
"""

import logging
from typing import Dict, Any, List, Optional, Union
import numpy as np
import pandas as pd

from btc_ml_system.src.validation.metrics import calculate_drawdown_series

logger = logging.getLogger("btc_ml_system.validation.bootstrap")


class BootstrapEngine:
    """
    Executes non-parametric statistical bootstrap resampling on trade records and return series.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.bs_cfg = self.config.get("bootstrap", {})
        self.n_iterations = int(self.bs_cfg.get("n_iterations", 1000))
        self.random_seed = int(self.bs_cfg.get("random_seed", 42))
        self.ruin_threshold_pct = float(self.bs_cfg.get("ruin_threshold_pct", 50.0)) # 50% capital loss = ruin

    def trade_bootstrap(
        self,
        trades: List[Dict[str, Any]],
        initial_capital: float = 10000.0,
        n_iterations: Optional[int] = None,
        random_seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        IID Trade-return bootstrap.
        Resamples trade PnLs with replacement over n_iterations synthetic histories.
        """
        n_iter = n_iterations or self.n_iterations
        seed = random_seed or self.random_seed
        rng = np.random.default_rng(seed)

        if not trades:
            logger.warning("Bootstrap received empty trade list.")
            return {"error": "No trades provided"}

        pnl_dollars = np.array([float(t.get("pnl_usd", t.get("pnl", 0.0))) for t in trades])
        n_trades = len(pnl_dollars)

        bootstrapped_returns = np.zeros(n_iter)
        bootstrapped_win_rates = np.zeros(n_iter)
        bootstrapped_max_dds = np.zeros(n_iter)
        bootstrapped_profit_factors = np.zeros(n_iter)
        ruin_count = 0

        for b in range(n_iter):
            # Resample indices with replacement
            sampled_indices = rng.integers(0, n_trades, size=n_trades)
            sample_pnls = pnl_dollars[sampled_indices]

            # Construct equity curve
            eq = np.zeros(n_trades + 1)
            eq[0] = initial_capital
            eq[1:] = initial_capital + np.cumsum(sample_pnls)

            # Prevent negative equity in simulation
            eq = np.maximum(eq, 1.0)

            final_cap = eq[-1]
            ret_pct = ((final_cap - initial_capital) / initial_capital) * 100.0
            bootstrapped_returns[b] = ret_pct

            # Win rate
            wins = sample_pnls > 0
            bootstrapped_win_rates[b] = np.sum(wins) / n_trades

            # Profit Factor
            gross_profit = np.sum(sample_pnls[wins])
            gross_loss = np.abs(np.sum(sample_pnls[~wins]))
            bootstrapped_profit_factors[b] = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

            # Drawdown
            _, max_dd, _ = calculate_drawdown_series(eq)
            bootstrapped_max_dds[b] = max_dd * 100.0

            # Ruin check
            if max_dd * 100.0 >= self.ruin_threshold_pct:
                ruin_count += 1

        prob_negative_return = float(np.mean(bootstrapped_returns < 0))
        prob_ruin = float(ruin_count / n_iter)

        return {
            "method": "trade_iid",
            "iterations": n_iter,
            "original_trades_count": n_trades,
            "mean_return_pct": float(np.mean(bootstrapped_returns)),
            "std_return_pct": float(np.std(bootstrapped_returns)),
            "ci_90_return": (float(np.percentile(bootstrapped_returns, 5)), float(np.percentile(bootstrapped_returns, 95))),
            "ci_95_return": (float(np.percentile(bootstrapped_returns, 2.5)), float(np.percentile(bootstrapped_returns, 97.5))),
            "ci_99_return": (float(np.percentile(bootstrapped_returns, 0.5)), float(np.percentile(bootstrapped_returns, 99.5))),
            "prob_negative_return": prob_negative_return,
            "mean_win_rate": float(np.mean(bootstrapped_win_rates)),
            "ci_95_win_rate": (float(np.percentile(bootstrapped_win_rates, 2.5)), float(np.percentile(bootstrapped_win_rates, 97.5))),
            "mean_profit_factor": float(np.mean(bootstrapped_profit_factors)),
            "ci_95_profit_factor": (float(np.percentile(bootstrapped_profit_factors, 2.5)), float(np.percentile(bootstrapped_profit_factors, 97.5))),
            "mean_max_drawdown_pct": float(np.mean(bootstrapped_max_dds)),
            "percentile_95_max_dd": float(np.percentile(bootstrapped_max_dds, 95)),
            "percentile_99_max_dd": float(np.percentile(bootstrapped_max_dds, 99)),
            "prob_ruin_pct": prob_ruin * 100.0,
            "ruin_definition": f"Loss >= {self.ruin_threshold_pct}% of initial capital"
        }

    def block_bootstrap(
        self,
        returns: Union[np.ndarray, pd.Series],
        block_size: int = 24, # 24 bars block
        n_iterations: Optional[int] = None,
        random_seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Moving Block Bootstrap. Preserves serial correlation within blocks of length block_size.
        """
        n_iter = n_iterations or self.n_iterations
        seed = random_seed or self.random_seed
        rng = np.random.default_rng(seed)

        r = np.array(returns).flatten()
        n = len(r)
        if n < block_size * 2:
            return self.trade_bootstrap([{"pnl_usd": val} for val in r], n_iterations=n_iter, random_seed=seed)

        n_blocks = int(np.ceil(n / block_size))
        valid_starts = n - block_size

        bootstrapped_cum_returns = np.zeros(n_iter)
        bootstrapped_sharpes = np.zeros(n_iter)

        for b in range(n_iter):
            starts = rng.integers(0, valid_starts, size=n_blocks)
            sampled_series = np.concatenate([r[start:start + block_size] for start in starts])[:n]

            cum_ret = np.prod(1.0 + sampled_series) - 1.0
            bootstrapped_cum_returns[b] = cum_ret * 100.0

            std = np.std(sampled_series)
            sharpe = (np.mean(sampled_series) / std * np.sqrt(252 * 24)) if std > 1e-12 else 0.0
            bootstrapped_sharpes[b] = sharpe

        return {
            "method": "moving_block",
            "block_size": block_size,
            "iterations": n_iter,
            "mean_cum_return_pct": float(np.mean(bootstrapped_cum_returns)),
            "ci_95_cum_return": (float(np.percentile(bootstrapped_cum_returns, 2.5)), float(np.percentile(bootstrapped_cum_returns, 97.5))),
            "mean_sharpe": float(np.mean(bootstrapped_sharpes)),
            "ci_95_sharpe": (float(np.percentile(bootstrapped_sharpes, 2.5)), float(np.percentile(bootstrapped_sharpes, 97.5)))
        }

    def stationary_bootstrap(
        self,
        returns: Union[np.ndarray, pd.Series],
        expected_block_size: int = 24,
        n_iterations: Optional[int] = None,
        random_seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Stationary Bootstrap (Politis & Romano 1994).
        Resamples blocks with geometrically distributed random block lengths (mean = expected_block_size).
        Guarantees stationarity of the resampled series.
        """
        n_iter = n_iterations or self.n_iterations
        seed = random_seed or self.random_seed
        rng = np.random.default_rng(seed)

        r = np.array(returns).flatten()
        n = len(r)
        p = 1.0 / expected_block_size

        bootstrapped_cum_returns = np.zeros(n_iter)
        bootstrapped_sharpes = np.zeros(n_iter)

        for b in range(n_iter):
            sampled_indices = []
            curr_idx = rng.integers(0, n)
            while len(sampled_indices) < n:
                sampled_indices.append(curr_idx)
                if rng.uniform(0, 1) < p:
                    curr_idx = rng.integers(0, n)
                else:
                    curr_idx = (curr_idx + 1) % n

            sampled_series = r[sampled_indices]
            cum_ret = np.prod(1.0 + sampled_series) - 1.0
            bootstrapped_cum_returns[b] = cum_ret * 100.0

            std = np.std(sampled_series)
            sharpe = (np.mean(sampled_series) / std * np.sqrt(252 * 24)) if std > 1e-12 else 0.0
            bootstrapped_sharpes[b] = sharpe

        return {
            "method": "stationary",
            "expected_block_size": expected_block_size,
            "iterations": n_iter,
            "mean_cum_return_pct": float(np.mean(bootstrapped_cum_returns)),
            "ci_95_cum_return": (float(np.percentile(bootstrapped_cum_returns, 2.5)), float(np.percentile(bootstrapped_cum_returns, 97.5))),
            "mean_sharpe": float(np.mean(bootstrapped_sharpes)),
            "ci_95_sharpe": (float(np.percentile(bootstrapped_sharpes, 2.5)), float(np.percentile(bootstrapped_sharpes, 97.5)))
        }
