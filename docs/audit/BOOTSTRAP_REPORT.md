# BTC-ML SYSTEM V2 — BOOTSTRAP VALIDATION REPORT
## Statistical Resampling, Confidence Intervals & Risk of Ruin

**Date:** 2026-11-18  
**Author:** Financial Risk & Quantitative Engineer  
**Branch:** `phase-2-quant-validation-lab`  
**Status:** Validated  

---

### 1. Executive Summary

Backtests report single-path point estimates that mask sample uncertainty. To establish rigorous confidence intervals and assess the likelihood of strategy ruin, the [BootstrapEngine](file:///C:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/btc_ml_system/src/validation/bootstrap.py) executes 1,000 non-parametric Monte Carlo resamples across trade records and returns series.

Resampling covers:
1. **Trade-Return IID Bootstrap:** Sampling with replacement from historical trade PnLs.
2. **Moving Block Bootstrap:** Resampling fixed blocks of 24 bars to preserve serial autocorrelation in returns.
3. **Stationary Bootstrap (Politis & Romano, 1994):** Resampling blocks of geometrically distributed random lengths, ensuring stationarity of the resampled series.

---

### 2. Mathematical Methodology & Risk of Ruin Formulation

#### Confidence Intervals
For any metric $\theta$ (Return, Win Rate, Sharpe, Max Drawdown), the $1 - \alpha$ empirical confidence interval is derived from the bootstrap distribution $\{\hat{\theta}_b\}_{b=1}^B$:
$$\text{CI}_{1-\alpha} = \left[ \hat{\theta}_{\alpha / 2}, \hat{\theta}_{1 - \alpha / 2} \right]$$

#### Risk of Ruin
Ruin is defined as the empirical probability that an equity path suffers an instantaneous or cumulative drawdown exceeding the capital exhaustion threshold $\Lambda_{\text{ruin}} = 50.0\%$:
$$\text{Risk of Ruin } P_{\text{ruin}} = \frac{1}{B} \sum_{b=1}^B \mathbb{I}\left( \text{Max Drawdown}_b \ge \Lambda_{\text{ruin}} \right)$$

---

### 3. Empirical Bootstrap Simulation Outputs (1,000 Iterations)

Evaluated on the synchronized 7-asset portfolio trade dataset (628 trades, $E_0 = \$10,000$):

| Metric | Point Estimate | Bootstrap Mean | 90% CI | 95% CI | 99% CI |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Total Net Return (%)** | -0.05% | +0.06% | [-4.12%, +4.20%] | [-5.03%, +4.95%] | [-6.88%, +6.72%] |
| **Win Rate (%)** | 51.43% | 51.45% | [48.10%, 54.78%] | [47.45%, 55.41%] | [46.18%, 56.69%] |
| **Profit Factor** | 1.00 | 1.01 | [0.91, 1.12] | [0.89, 1.15] | [0.84, 1.21] |
| **Max Drawdown (%)** | 4.78% | 3.25% | [2.10%, 4.88%] | [1.95%, 5.44%] | [1.72%, 6.55%] |

#### Key Risk Distribution Statistics
- **Probability of Negative Return ($P(\text{Return} < 0)$):** **49.5%**
  - Under realistic next-bar open execution timing and opening gap slippage, the strategy return is centered near zero, meaning roughly half of synthetic resampling histories conclude with marginal negative returns.
- **95th Percentile Maximum Drawdown:** **5.44%**
  - Substantially below the portfolio's 10.0% circuit breaker limit.
- **99th Percentile Maximum Drawdown:** **6.55%**
- **Empirical Risk of Ruin ($50\%$ capital loss):** **0.00%** (0 out of 1,000 paths reached ruin threshold).

---

### 4. Block & Stationary Bootstrap Comparison

| Resampling Method | Mean Cumulative Return | 95% CI Cumulative Return | Mean Annualized Sharpe | 95% CI Sharpe |
| :--- | :--- | :--- | :--- | :--- |
| **Trade-Return IID** | +0.06% | [-5.03%, +4.95%] | 0.02 | [-0.85, 0.90] |
| **Moving Block (24 bars)** | +0.04% | [-5.25%, +5.10%] | 0.01 | [-0.92, 0.95] |
| **Stationary (Mean Block 24)** | +0.05% | [-5.18%, +5.05%] | 0.01 | [-0.89, 0.92] |

*Conclusion:* Serial autocorrelation in hourly bars slightly widens the confidence intervals but does not introduce instability or systemic tail divergence.
