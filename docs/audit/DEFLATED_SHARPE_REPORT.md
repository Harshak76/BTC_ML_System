# BTC-ML SYSTEM V2 — DEFLATED SHARPE RATIO REPORT
## Multiple Testing Corrections, Non-Normality & Probabilistic Sharpe Ratios

**Date:** 2026-11-18  
**Author:** Quantitative Researcher & Risk Mathematician  
**Branch:** `phase-2-quant-validation-lab`  
**Reference:** Bailey, D. H., & López de Prado, M. (2014). *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality*. Journal of Portfolio Management.  
**Engine:** [DeflatedSharpeEngine](file:///C:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/btc_ml_system/src/validation/deflated_sharpe.py)  

---

### 1. Executive Summary

The ordinary annualized Sharpe ratio is the most commonly cited metric in quantitative research, yet it is also the most abused. When multiple strategy variations, parameter grids, or signal filters are evaluated, the maximum observed Sharpe ratio is guaranteed to increase simply as a function of the number of trials ($N$), even on pure white noise. Furthermore, the standard Sharpe ratio assumes independent, identically distributed (IID) normal returns, severely underestimating risk in presence of fat tails and skewness.

The **Deflated Sharpe Ratio (DSR)** corrects for:
1. **Selection Bias & Multiple Testing:** The number of candidate models evaluated ($N$).
2. **Variance Across Trials:** The dispersion of trial Sharpe ratios ($V[\{\widehat{SR}_n\}]$).
3. **Non-Normality of Returns:** Sample skewness ($\hat{\gamma}_3$) and uncentered kurtosis ($\hat{\gamma}_4$).
4. **Sample Length:** Number of observations ($T$).

---

### 2. Mathematical Formulation & Derivations

#### 2.1 Asymptotic Variance under Non-Normality (Mertens, 2002)
For an observed periodic Sharpe ratio $\widehat{SR}$, sample length $T$, sample skewness $\hat{\gamma}_3$, and uncentered Pearson kurtosis $\hat{\gamma}_4$:
$$\hat{\sigma}_{\widehat{SR}} = \sqrt{\frac{1}{T-1} \left(1 - \hat{\gamma}_3 \widehat{SR} + \frac{\hat{\gamma}_4 - 1}{4} \widehat{SR}^2\right)}$$

- Under standard normal returns ($\hat{\gamma}_3 = 0, \hat{\gamma}_4 = 3$), this simplifies to Lo's (2002) IID formula:
  $$\hat{\sigma}_{\widehat{SR}} = \sqrt{\frac{1 + 0.5 \widehat{SR}^2}{T-1}}$$
- If returns exhibit negative skewness ($\hat{\gamma}_3 < 0$) or fat tails ($\hat{\gamma}_4 > 3$), $\hat{\sigma}_{\widehat{SR}}$ increases, inflating standard error and deflating confidence.

#### 2.2 Probabilistic Sharpe Ratio (PSR)
The Probabilistic Sharpe Ratio tests whether an observed Sharpe ratio $\widehat{SR}$ statistically exceeds a benchmark $SR^*$:
$$\text{PSR}(SR^*) = \Phi\left(\frac{\widehat{SR} - SR^*}{\hat{\sigma}_{\widehat{SR}}}\right)$$
where $\Phi(\cdot)$ is the cumulative distribution function of the standard normal distribution.

#### 2.3 Expected Maximum Sharpe Ratio (Euler-Mascheroni Approximation)
Under the null hypothesis that true strategy performance across all $N$ trials has zero edge ($SR = 0$), the expected maximum Sharpe ratio among $N$ independent trials is derived from extreme value theory:
$$E\left[\max_{n=1,\dots,N} \widehat{SR}_n\right] \approx \sqrt{V[\{\widehat{SR}_n\}]} \left( (1 - \gamma) Z^{-1}\left(1 - \frac{1}{N}\right) + \gamma Z^{-1}\left(1 - \frac{1}{N e}\right) \right)$$
where:
- $\gamma \approx 0.5772156649$ is the Euler-Mascheroni constant.
- $Z^{-1}(\cdot)$ is the inverse standard normal quantile function.
- $e = \exp(1) \approx 2.71828$.
- $V[\{\widehat{SR}_n\}]$ is the variance of the trial Sharpe ratios.

#### 2.4 Deflated Sharpe Ratio (DSR)
DSR computes the probability that the observed Sharpe ratio exceeds the expected maximum Sharpe ratio that would be obtained purely through data mining:
$$\text{DSR} = \text{PSR}\left(E\left[\max_{n=1,\dots,N} \widehat{SR}_n\right]\right) = \Phi\left(\frac{\widehat{SR} - E[\max \widehat{SR}]}{\hat{\sigma}_{\widehat{SR}}}\right)$$

- $\text{DSR} \ge 0.95$: Statistically significant at the 5% level (less than 5% probability that the result is a false discovery).
- $0.80 \le \text{DSR} < 0.95$: Moderate statistical significance.
- $\text{DSR} < 0.80$: High probability of selection bias / backtest overfitting.

---

### 3. Empirical Results on BTC-ML System Portfolio

Evaluated on the synchronized 7-asset portfolio ($T = 17,520$ hourly periods, $N = 8$ candidate variations):

| Statistical Parameter | Value | Interpretation |
| :--- | :--- | :--- |
| **Observed Annualized Sharpe Ratio** | **-0.00** | Point estimate under next-bar open execution |
| **Observed Periodic Sharpe Ratio** | **-0.0000** | Unannualized periodic hourly Sharpe |
| **Number of Observations ($T$)** | **17,520** | 2 years of hourly bars |
| **Number of Candidate Trials ($N$)** | **8** | Model parameter variations evaluated |
| **Variance of Trials ($V[\{\widehat{SR}\}]$)** | **0.082** | Dispersion of performance across candidates |
| **Return Skewness ($\hat{\gamma}_3$)** | **-0.24** | Moderate negative skew (asymmetric downside) |
| **Return Kurtosis ($\hat{\gamma}_4$)** | **6.12** | Leptokurtic / Fat tails (extreme moves present) |
| **Mertens Standard Error ($\hat{\sigma}_{\widehat{SR}}$)** | **0.0076** | Periodic standard error accounting for moments |
| **Expected Max Annualized Sharpe ($E[\max SR]$)** | **0.51** | Expected lucky maximum under 8 trials |
| **Probabilistic Sharpe Ratio ($\text{PSR}(0)$)** | **49.7%** | 49.7% probability that true Sharpe $> 0$ |
| **Deflated Sharpe Ratio (DSR)** | **8.5%** | **NOT STATISTICALLY SIGNIFICANT (< 95%)** |

---

### 4. Forensic Insights & Key Takeaways

1. **Why is DSR 8.5%?**
   - The observed annualized Sharpe ratio under realistic execution is near 0.00.
   - However, when testing across 8 candidate variations, random variance naturally produces an expected lucky maximum Sharpe of **0.51** under the null hypothesis.
   - Because the observed Sharpe (0.00) is far below the expected maximum of lucky noise (0.51), the probability that this result represents genuine statistical alpha is only **8.5%**.
2. **Value of DSR in Quantitative Risk Control:**
   - Had the research team only looked at an in-sample unadjusted Sharpe ratio of 1.18 (observed earlier under same-bar close execution), they would have assumed the strategy was ready for deployment.
   - DSR prevents this critical error by proving mathematically that the apparent performance can be fully explained by multiple trial exploration and execution timing inflation.
3. **Requirement for Phase 2:**
   - To achieve $\text{DSR} \ge 95\%$, the strategy must achieve an annualized Sharpe ratio $> 1.40$ on large sample sizes, demonstrating genuine statistical robustness.
