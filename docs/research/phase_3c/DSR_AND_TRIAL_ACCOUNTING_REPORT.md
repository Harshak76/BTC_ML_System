# BTC-ML SYSTEM V2 — PHASE 3C DSR AND TRIAL ACCOUNTING REPORT
## Deflated Sharpe Ratio (DSR) & Multiple-Testing Selection Bias Audit

- **Date:** 2026-11-24
- **Auditor:** Senior Quantitative Researcher & Backtesting Auditor
- **Framework:** Bailey & López de Prado (2014) Deflated Sharpe Ratio
- **Cumulative Trial Count:** $N = 12$ trials (Phase 3B: 9, Phase 3C: 3)
- **Annualization Factor:** $\sqrt{8760} \approx 93.596$ (Hourly calendar timeline)
- **Mandatory Disclosure:**
  > **`HISTORICAL EXPLORATORY EVALUATION — PRIOR DATASET INSPECTION DISCLOSED`**  
  > Evaluated on historical data with prior inspection disclosed.

---

## 1. DSR MATHEMATICAL SPECIFICATION & TRIAL ACCOUNTING

The Deflated Sharpe Ratio (DSR) computes the probability that an observed Sharpe ratio $\widehat{SR}$ exceeds the expected maximum Sharpe ratio under the null hypothesis ($SR^* = E[\max_N \{SR_n\}]$), adjusting for:
1. Number of historical trials ($N = 12$).
2. Variance of trial Sharpe ratios ($\sigma^2_{trials}$).
3. Non-normality of returns (sample skewness $\gamma_3$ and Pearson kurtosis $\gamma_4$).
4. Asymptotic variance of the Sharpe estimator (Mertens 2002):
   $$\sigma^2_{\widehat{SR}} = \frac{1}{T-1} \left[ 1 - \gamma_3 \widehat{SR} + \frac{\gamma_4 - 1}{4} \widehat{SR}^2 \right]$$
5. Extreme Value Theory approximation (Euler-Mascheroni constant $\gamma \approx 0.5772$):
   $$E[\max_N] \approx \sqrt{\sigma^2_{trials}} \cdot \left[ (1 - \gamma) Z\left(1 - \frac{1}{N}\right) + \gamma Z\left(1 - \frac{1}{N e}\right) \right]$$

---

## 2. CUMULATIVE TRIAL REGISTRY ($N = 12$)

Across the BTC-ML System research lifecycle, 12 unique strategy candidates have been evaluated under identical portfolio mechanics:

| Trial # | Phase | Candidate Strategy ID | Annualized Portfolio Sharpe Ratio |
|---|---|---|---|
| **Trial 1** | Phase 3B | `RS_TF_DUAL_EMA_21_55_V1` | $-1.3484$ |
| **Trial 2** | Phase 3B | `RS_TF_DUAL_EMA_20_50_V1` | $-1.4450$ |
| **Trial 3** | Phase 3B | `RS_TF_DUAL_EMA_50_100_V1` | $-1.3359$ |
| **Trial 4** | Phase 3B | `RS_MOM_DONCHIAN_20_V1` | $-1.6404$ |
| **Trial 5** | Phase 3B | `RS_MOM_DONCHIAN_40_V1` | $-1.1076$ |
| **Trial 6** | Phase 3B | `RS_MOM_DONCHIAN_55_V1` | $-1.1190$ |
| **Trial 7** | Phase 3B | `RS_MR_BB_RSI_20_STD_V1` | $-2.9005$ |
| **Trial 8** | Phase 3B | `RS_MR_BB_RSI_22_STD_V1` | $-2.4568$ |
| **Trial 9** | Phase 3B | `RS_MR_BB_RSI_25_STD_V1` | $-1.6569$ |
| **Trial 10** | Phase 3C | `RS_MOM_DONCHIAN_40_CONTROL` | $-1.1076$ |
| **Trial 11** | Phase 3C | `RS_MOM_DONCHIAN_40_ADX25` | **$-0.7198$** |
| **Trial 12** | Phase 3C | `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE` | $-1.4398$ |

- **Sample Mean Sharpe across 12 trials:** $-1.5231$
- **Variance of trial Sharpes ($\sigma^2_{trials}$):** $0.3475$ ($\sigma_{trials} = 0.5895$)
- **Expected Maximum Annualized Sharpe under Null ($E[\max_{12}]$):** **$+1.0081$**

---

## 3. EMPIRICAL DSR RESULTS

| Metric | `RS_MOM_DONCHIAN_40_CONTROL` | `RS_MOM_DONCHIAN_40_ADX25` | `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE` |
|---|---|---|---|
| **Observed Annualized Sharpe** | $-1.1076$ | **$-0.7198$** | $-1.4398$ |
| **Observations ($T$)** | 17,519 | 17,519 | 17,519 |
| **Return Skewness ($\gamma_3$)** | $+0.9749$ | $+1.4811$ | $+0.6162$ |
| **Pearson Kurtosis ($\gamma_4$)** | $112.06$ | $227.36$ | $128.77$ |
| **Mertens Standard Error** | $0.00760$ | $0.00764$ | $0.00761$ |
| **Expected Max Sharpe** | $+1.0081$ | $+1.0081$ | $+1.0081$ |
| **Probabilistic Sharpe (PSR vs 0)** | $0.0467$ ($4.67\%$) | $0.1376$ ($13.76\%$) | $0.0146$ ($1.46\%$) |
| **Deflated Sharpe Ratio (DSR)** | **$0.0007$ ($0.07\%$)** | **$0.0044$ ($0.44\%$)** | **$0.0001$ ($0.01\%$)** |
| **DSR $p$-value ($1 - \text{DSR}$)** | **$0.9993$** | **$0.9956$** | **$0.9999$** |
| **Statistical Significance (95%)** | **NOT SIGNIFICANT** | **NOT SIGNIFICANT** | **NOT SIGNIFICANT** |

---

## 4. DSR STATISTICAL CONCLUSION

1. **Selection Bias Penalty:** When testing $N=12$ strategy variations on the same historical dataset, pure random noise is expected to produce a maximum annualized Sharpe ratio of $+1.0081$ simply due to selection bias.
2. **Deflated Significance:**
   - The top candidate (`RS_MOM_DONCHIAN_40_ADX25`) achieves an observed Sharpe of $-0.7198$.
   - Its Deflated Sharpe Ratio is **$0.0044$ ($0.44\%$)**, yielding an astronomical $p$-value of **$0.9956$** (far above the $0.05$ significance threshold).
3. **Gate 4 Verdict:** **FAILED**. Zero candidates demonstrate statistical significance over random noise after correcting for multiple testing.
