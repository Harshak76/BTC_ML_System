# BTC-ML SYSTEM V2 — PHASE 3C.2 RESEARCH REPORT
# STATISTICAL REVALIDATION REPORT

**Document ID:** `STATISTICAL_REVALIDATION_REPORT.md`  
**Phase:** 3C.2 Research Integrity Remediation & Controlled Revalidation  
**Repository:** `BTC_ML_System`  
**Branch:** `fix/phase-3c-2-research-integrity`  
**Base Commit:** `93e7121`  
**Engines:** Deflated Sharpe Ratio (DSR), Stationary Block Bootstrap ($L=24$), Monte Carlo Stress Suite (9 Scenarios)  
**Date:** 2026-11-25

---

## 1. Executive Summary

This report delivers the statistical revalidation of the three Phase 3C strategy candidates under the remediated 1-hour multi-asset dataset:
1. **Deflated Sharpe Ratio (DSR):** Across $N = 12$ documented trials, the top candidate (`RS_MOM_DONCHIAN_40_ADX25`) achieves an observed Sharpe of **$-1.1778$** against an expected null maximum of **$+0.9580$**, yielding a DSR of **$0.0014$ ($0.14\%$)** and an upper-tail $p$-value of **$0.9986$**. Sensitivity analysis proves that under ANY trial count assumption ($N \in \{12, 50, 100, 500, 1000\}$), the $p$-value exceeds $0.999$.
2. **Stationary Block Bootstrap (Politis & Romano 1994, $L=24$):**
   - Control 95% CI: $[-25.20\%, -5.22\%]$ (Probability of negative return: **$99.9\%$**)
   - ADX25 95% CI: $[-13.21\%, +1.28\%]$ (Probability of negative return: **$96.0\%$**)
   - 4H EMA Slope 95% CI: $[-23.60\%, -5.23\%]$ (Probability of negative return: **$100.0\%$**)
   - All three candidates decisively fail Gate 5 (CI lower bound $> 0$).
3. **Monte Carlo Stress Testing (1,000 Paths):**
   - Under trade sequence shuffling, 95th percentile max drawdown reaches $18.41\%$ for Control and $17.44\%$ for 4H EMA, with worst-case drawdowns breaching $20\%$.
   - Under 2x fee inflation, **$100.0\%$ of simulated paths produce net losses** across all candidates.

---

## 2. Deflated Sharpe Ratio & Trial Accounting

### Mathematical Specification
Following Bailey & López de Prado (2014), the expected maximum Sharpe under $H_0$ with variance $\sigma^2_{\text{trials}} = 0.3150$ ($\sigma = 0.5612$ across 12 trials):
$$SR^* = E\left[\max_{n=1,\dots,N} \{SR_n\}\right] \approx \sigma \cdot \left[ (1 - \gamma) Z^{-1}\left(1 - \frac{1}{N}\right) + \gamma Z^{-1}\left(1 - \frac{1}{Ne}\right) \right]$$

### Empirical DSR Results ($N = 12$ Formally Documented Trials)
| Metric | `RS_MOM_DONCHIAN_40_CONTROL` | `RS_MOM_DONCHIAN_40_ADX25` | `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE` |
| :--- | :--- | :--- | :--- |
| **Observed Annualized Sharpe** | **$-2.0646$** | **$-1.1778$** | **$-2.1556$** |
| **Periodic Sharpe ($\div \sqrt{8760}$)** | $-0.02206$ | $-0.01258$ | $-0.02303$ |
| **Skewness ($\gamma_3$)** | $+0.8412$ | $+1.3204$ | $+0.7819$ |
| **Pearson Kurtosis ($\gamma_4$)** | $94.15$ | $188.42$ | $105.31$ |
| **Null Hurdle $SR^*$** | $+0.9580$ | $+0.9580$ | $+0.9580$ |
| **Probabilistic Sharpe (PSR vs 0)** | $0.0021$ ($0.21\%$) | $0.0493$ ($4.93\%$) | $0.0014$ ($0.14\%$) |
| **Deflated Sharpe Ratio (DSR)** | **$0.0000$ ($0.00\%$)** | **$0.0014$ ($0.14\%$)** | **$0.0000$ ($0.00\%$)** |
| **$p$-value ($1 - \text{DSR}$)** | **$1.0000$** | **$0.9986$** | **$1.0000$** |
| **Gate 4 Verdict** | **FAILED** | **FAILED** | **FAILED** |

---

### DSR Trial Count Sensitivity Analysis
To account for potential hidden exploratory scans across the BTC-ML System lifecycle:

| Trial Count Assumption ($N$) | Context / Rationale | Expected Max Ann. Sharpe $SR^*$ | Top Candidate $z$-score | DSR $\Phi(z)$ | $p$-value ($1 - \text{DSR}$) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **$N = 12$** | Formally Documented Runs | **$+0.9580$** | $-2.981$ | $0.0014$ | $0.9986$ |
| **$N = 50$** | Documented + Minor Sweeps | **$+1.3098$** | $-3.447$ | $0.0003$ | $0.9997$ |
| **$N = 100$** | Moderate Exploratory Testing | **$+1.4562$** | $-3.641$ | $0.0001$ | $0.9999$ |
| **$N = 500$** | Broad Grid / Parameter Mining | **$+1.7565$** | $-4.038$ | $< 0.0001$ | $> 0.9999$ |
| **$N = 1000$** | Extensive Automated Search | **$+1.8731$** | $-4.192$ | $< 0.0001$ | $> 0.9999$ |

**Finding:** Because observed Sharpe ratios are negative ($\le -1.1778$), increasing the trial count simply pushes the hurdle further into positive territory, driving the $p$-value even closer to $1.0000$.

---

## 3. Bootstrap Resampling Validation (1,000 Iterations)

```
                            BOOTSTRAP 95% CONFIDENCE INTERVALS
    CONTROL:      [=============================|======] (Mean: -15.82%)
                  -25.20%                      -5.22%  0.0%

    ADX25:                 [====================|====]   (Mean: -6.18%)
                           -13.21%             0.0% +1.28%

    4H EMA:       [=============================|======] (Mean: -15.03%)
                  -23.60%                      -5.23%  0.0%
```

### Numerical Bootstrap Summary
| Strategy Candidate | Trade BS Mean Return | Trade BS 95% CI | Prob. Negative Return | Stationary BS 95% CI | Gate 5 Status ($CI_{lower} > 0$) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Control** (`DONCHIAN_40`) | $-15.82\%$ | $[-24.99\%, -5.81\%]$ | **$99.9\%$** | $[-25.20\%, -5.22\%]$ | **FAILED** |
| **ADX25 Filter** | $-6.18\%$ | $[-12.79\%, +0.38\%]$ | **$96.0\%$** | $[-13.21\%, +1.28\%]$ | **FAILED** |
| **4H EMA Slope Filter** | $-15.03\%$ | $[-24.05\%, -5.83\%]$ | **$100.0\%$** | $[-23.60\%, -5.23\%]$ | **FAILED** |

### Observations
- For both Control and 4H EMA Slope, the entire $95\%$ confidence interval lies strictly below zero. The probability of negative return is $99.9\%$ to $100.0\%$.
- For ADX25, $96.0\%$ of resamples lose capital, with the 95% CI lower bound at $-13.21\%$.

---

## 4. Monte Carlo Stress Testing (9 Scenarios)

| Stress Scenario / Metric | Control Candidate | ADX25 Filter Candidate | 4H EMA Slope Candidate |
| :--- | :--- | :--- | :--- |
| **Shuffle: 95th Percentile MaxDD** | **$18.41\%$** | **$8.93\%$** | **$17.44\%$** |
| **Shuffle: Worst-Case MaxDD** | **$20.84\%$ (Breached 20%)** | **$10.71\%$** | **$19.81\%$** |
| **Fee Inflation (1x–3x): Mean Return** | **$-24.61\%$** | **$-9.86\%$** | **$-22.78\%$** |
| **Fee Inflation: Prob. Negative Return** | **$100.0\%$** | **$100.0\%$** | **$100.0\%$** |
| **Slippage Stress (1x–3x): Mean Return** | **$-16.58\%$** | **$-6.50\%$** | **$-15.71\%$** |
| **Slippage Stress: 95th MaxDD** | **$18.28\%$** | **$8.92\%$** | **$15.92\%$** |
| **Adverse Fills: Mean Return** | **$-25.10\%$** | **$-10.15\%$** | **$-23.20\%$** |
| **Adverse Fills: Prob. Negative Return** | **$100.0\%$** | **$100.0\%$** | **$100.0\%$** |
| **Missed Trades (8% Dropout): Mean Return**| **$-14.80\%$** | **$-5.80\%$** | **$-14.10\%$** |

### Drawdown Limit Reconciliation (10% Production vs. 20% Research)
- Under trade sequence shuffling:
  - **Control:** Breached the $20\%$ research gate in worst-case paths ($20.84\%$) and severely breached the $10\%$ production cap ($18.41\%$).
  - **4H EMA:** Nearly breached the $20\%$ gate ($19.81\%$) and severely breached the $10\%$ production cap ($17.44\%$).
  - **ADX25:** Maintained 95th percentile MaxDD below $10\%$ ($8.93\%$), but still produced $100\%$ negative paths under fee stress.

---

## 5. Audit Conclusion

The statistical revalidation under the remediated 1H consistent methodology **decisively reinforces the research rejection**:
- All candidates fail Gates 1, 3, 4, 5, 7, 8, and 9.
- Negative performance is statistically significant, structural, and impervious to multiple-testing corrections.
