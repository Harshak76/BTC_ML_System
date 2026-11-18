"""
Deflated Sharpe Ratio (DSR) and Probabilistic Sharpe Ratio (PSR) Engine.
Reference:
Bailey, D. H., & López de Prado, M. (2014).
"The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality".
Journal of Portfolio Management / Annals of Applied Statistics.

Mathematical Foundations:
- Corrects for multiple testing across N trials.
- Adjusts for non-normal return distributions (skewness and kurtosis).
- Uses Mertens (2002) asymptotic variance formulation.
- Uses Euler-Mascheroni approximation for expected maximum Sharpe ratio under the null hypothesis.
"""

import logging
from typing import Dict, Any, List, Optional, Union
import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger("btc_ml_system.validation.deflated_sharpe")

EULER_MASCHERONI = 0.5772156649015328606065120900824


class DeflatedSharpeEngine:
    """
    Computes Mertens standard error, Probabilistic Sharpe Ratio (PSR),
    Expected Maximum Sharpe Ratio, and Deflated Sharpe Ratio (DSR).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @staticmethod
    def compute_mertens_standard_error(
        sharpe: float,
        n_observations: int,
        skewness: float = 0.0,
        kurtosis: float = 3.0
    ) -> float:
        """
        Computes the asymptotic standard deviation of the Sharpe ratio estimator
        under non-normality (Mertens 2002, Lo 2002).
        Note: kurtosis is uncentered Pearson kurtosis (Normal = 3.0).
        """
        if n_observations <= 2:
            return 1.0

        var = (1.0 / (n_observations - 1.0)) * (
            1.0 - (skewness * sharpe) + (((kurtosis - 1.0) / 4.0) * (sharpe ** 2))
        )
        return float(np.sqrt(max(var, 1e-12)))

    @staticmethod
    def compute_probabilistic_sharpe_ratio(
        observed_sharpe: float,
        benchmark_sharpe: float,
        n_observations: int,
        skewness: float = 0.0,
        kurtosis: float = 3.0
    ) -> float:
        """
        Calculates Probabilistic Sharpe Ratio: PSR(SR*) = Phi((SR - SR*) / sigma_SR).
        Represents the probability that the true Sharpe ratio exceeds benchmark_sharpe.
        """
        se = DeflatedSharpeEngine.compute_mertens_standard_error(
            observed_sharpe, n_observations, skewness, kurtosis
        )
        z = (observed_sharpe - benchmark_sharpe) / se
        psr = float(stats.norm.cdf(z))
        return psr

    @staticmethod
    def expected_max_sharpe(
        n_trials: int,
        var_trials: float,
        mean_sharpe: float = 0.0
    ) -> float:
        """
        Approximates the expected maximum Sharpe ratio among N independent trials
        under the null hypothesis that true Sharpe = 0, using extreme value theory
        (Euler-Mascheroni approximation).
        """
        if n_trials <= 1 or var_trials <= 1e-12:
            return float(mean_sharpe)

        std_trials = np.sqrt(var_trials)
        z1 = stats.norm.ppf(1.0 - (1.0 / n_trials))
        z2 = stats.norm.ppf(1.0 - (1.0 / (n_trials * np.e)))

        expected_max = std_trials * (((1.0 - EULER_MASCHERONI) * z1) + (EULER_MASCHERONI * z2))
        return float(expected_max + mean_sharpe)

    def calculate_dsr(
        self,
        observed_sharpe: float,
        n_observations: int,
        all_trial_sharpes: List[float],
        returns: Optional[Union[np.ndarray, pd.Series]] = None,
        skewness: Optional[float] = None,
        kurtosis: Optional[float] = None,
        annualization_factor: float = 1.0
    ) -> Dict[str, Any]:
        """
        Computes Deflated Sharpe Ratio (DSR) correcting for multiple trials and non-normality.
        """
        n_trials = len(all_trial_sharpes)
        if n_trials == 0:
            all_trial_sharpes = [observed_sharpe]
            n_trials = 1

        # Calculate sample moments if returns provided
        if returns is not None:
            r = np.array(returns).flatten()
            if len(r) > 3:
                calc_skew = float(pd.Series(r).skew())
                calc_kurt = float(pd.Series(r).kurtosis() + 3.0)
            else:
                calc_skew, calc_kurt = 0.0, 3.0
        else:
            calc_skew = skewness if skewness is not None else 0.0
            calc_kurt = kurtosis if kurtosis is not None else 3.0

        # Adjust unannualized sharpe for Mertens SE calculation
        # If observed_sharpe is annualized by sqrt(ann_factor), periodic sharpe is observed_sharpe / sqrt(ann_factor)
        periodic_sharpe = observed_sharpe / np.sqrt(annualization_factor) if annualization_factor > 1.0 else observed_sharpe
        periodic_trials = [s / np.sqrt(annualization_factor) if annualization_factor > 1.0 else s for s in all_trial_sharpes]

        var_trials = float(np.var(periodic_trials, ddof=1)) if n_trials > 1 else 0.0

        # Expected maximum periodic Sharpe among N trials
        exp_max_periodic = self.expected_max_sharpe(n_trials, var_trials, mean_sharpe=0.0)
        exp_max_annualized = exp_max_periodic * np.sqrt(annualization_factor)

        # Standard error under non-normality
        se_periodic = self.compute_mertens_standard_error(
            periodic_sharpe, n_observations, calc_skew, calc_kurt
        )

        # Standardized Z-score
        z = (periodic_sharpe - exp_max_periodic) / se_periodic
        dsr = float(stats.norm.cdf(z))

        # Baseline Probabilistic Sharpe Ratio vs 0
        z_psr = periodic_sharpe / se_periodic
        psr_zero = float(stats.norm.cdf(z_psr))

        return {
            "observed_annualized_sharpe": observed_sharpe,
            "observed_periodic_sharpe": periodic_sharpe,
            "deflated_sharpe_ratio": dsr,
            "probabilistic_sharpe_ratio": psr_zero,
            "expected_max_annualized_sharpe": exp_max_annualized,
            "expected_max_periodic_sharpe": exp_max_periodic,
            "n_observations": n_observations,
            "n_trials": n_trials,
            "variance_of_trials": var_trials,
            "skewness": calc_skew,
            "kurtosis": calc_kurt,
            "mertens_standard_error": se_periodic,
            "is_statistically_significant_95": bool(dsr >= 0.95),
            "is_statistically_significant_90": bool(dsr >= 0.90),
            "interpretation": (
                f"Observed Sharpe = {observed_sharpe:.2f}. "
                f"Expected Max Sharpe under {n_trials} trials = {exp_max_annualized:.2f}. "
                f"DSR = {dsr:.1%}. "
                + ("Statistically significant (> 95%). Strategy edge is unlikely due to data mining."
                   if dsr >= 0.95 else
                   "Not statistically significant at 95% level. High probability of selection bias.")
            )
        }
