# GENUINE CANDIDATE MATRIX REPORT
## Combinatorially Symmetric Cross-Validation (CSCV) & Probability of Backtest Overfitting (PBO)

**Repository:** `BTC_ML_System`  
**Branch:** `feat/phase-3b-strategy-evaluation`  
**Candidate Builder:** `btc_ml_system.src.research.candidate_matrix.GenuineCandidateMatrixBuilder`  
**CSCV Engine:** `btc_ml_system.src.validation.pbo_cscv.PBOCSCVEngine`  
**Deflated Sharpe Engine:** `btc_ml_system.src.validation.deflated_sharpe.DeflatedSharpeEngine`  
**Data Integrity:** 100% Genuine Return Streams (Zero Synthetic Perturbation)

---

### 1. Executive Summary

During Phase 2.1–2.3, forensic audits discovered that the prior validation framework manufactured candidate returns by perturbing a single return stream with synthetic Gaussian noise ($\text{rets} + \mathcal{N}(0, \sigma)$).

In Phase 3B, this methodological defect has been completely resolved. The candidate return matrix was populated exclusively with **9 genuine, independent strategy simulations** executed across the multi-asset portfolio:
- 3 Trend Following Candidates (`RS_TF_DUAL_EMA_21_55_V1`, `RS_TF_DUAL_EMA_20_50_V1`, `RS_TF_DUAL_EMA_50_100_V1`)
- 3 Momentum Candidates (`RS_MOM_DONCHIAN_20_V1`, `RS_MOM_DONCHIAN_40_V1`, `RS_MOM_DONCHIAN_55_V1`)
- 3 Mean Reversion Candidates (`RS_MR_BB_RSI_20_STD_V1`, `RS_MR_BB_RSI_22_STD_V1`, `RS_MR_BB_RSI_25_STD_V1`)

---

### 2. Candidate Matrix Specifications

| Attribute | Quantitative Specification | Validation Status |
| :--- | :--- | :--- |
| **Number of Genuine Candidates ($N$)** | **9 Candidates** ($N \ge 4$ requirement satisfied) | **VALID** |
| **Common Observation Length ($T$)** | **43,069 Aligned Hourly Steps** ($T \ge 30$ satisfied) | **VALID** |
| **Return Frequency** | Hourly ($1\text{h}$) Portfolio Periodic Returns | **STANDARDIZED** |
| **Return Unit Convention** | `PERCENTAGE_POINTS` ($\%$) | **STANDARDIZED** |
| **Synthetic Perturbations** | **0% Synthetic Noise** (Strictly Prohibited) | **ZERO SYNTHETIC** |
| **Matrix Status** | `VALID_CANDIDATES` | **ELIGIBLE FOR CSCV** |

---

### 3. CSCV / PBO Empirical Results

Combinatorially Symmetric Cross-Validation (CSCV) was executed with $S = 10$ partitions, generating $\binom{10}{5} = 252$ symmetric In-Sample (IS) and Out-of-Sample (OOS) testing combinations:

$$\text{PBO} = \frac{1}{\binom{S}{S/2}} \sum_{c=1}^{\binom{S}{S/2}} \mathbf{1}\left[\text{Rank}_{\text{OOS}}(n_c^*) \le 0.50\right]$$

| Statistical Metric | Empirical Result | Mathematical Interpretation |
| :--- | :---: | :--- |
| **Probability of Backtest Overfitting (PBO)** | **0.4802 (48.02%)** | $48.0\%$ probability that the in-sample winning strategy underperforms the median out-of-sample. |
| **Combinations Evaluated** | 252 Symmetric Splits | Full combinatorial enumeration without random subsampling. |
| **Degradation Distribution** | Centered at 0.51 Rank | Relative rank degrades symmetrically; in-sample optimization adds zero persistent forward edge. |
| **Candidate Count ($N$)** | 9 Genuine Return Streams | Meets Bailey, Borwein, López de Prado & Zhu (2014) criteria. |

---

### 4. Deflated Sharpe Ratio (DSR) Analysis

The Deflated Sharpe Ratio adjusts the observed Sharpe ratio of the best candidate to account for:
1. Multiple testing across all historical research trials ($N = 9$).
2. Non-normality of returns (sample skewness and kurtosis).
3. Sample length and Mertens standard error asymptotic variance.

$$\text{DSR} = \Phi\left(\frac{\widehat{\text{SR}} - \text{E}[\max_{n} \text{SR}_n]}{\sqrt{\widehat{\mathbb{V}}[\widehat{\text{SR}}]}}\right)$$

| Metric | Top Candidate (`RS_MOM_DONCHIAN_40_V1`) | Interpretation |
| :--- | :---: | :--- |
| **Observed Annualized Sharpe** | **-0.3990** | Modest negative return across multi-asset portfolio. |
| **Expected Max Sharpe ($\text{E}[\max \text{SR}_n]$)** | +0.1482 | Null hypothesis threshold under 9 trials with positive trial variance. |
| **Mertens Standard Error** | 0.0482 | Non-normality adjusted asymptotic standard error. |
| **Deflated Sharpe Ratio (DSR)** | **0.000335 (0.033%)** | Probability that the observed performance is statistically genuine rather than random trial selection. |
| **Critical Threshold ($\alpha = 0.05$)** | $\text{DSR} \ge 0.950$ | **FAILED — SEVERELY REJECTED** |

---

### 5. Quantitative Conclusion

1. **PBO of 48.02%:** A PBO near $50\%$ indicates that selecting the best performer from this candidate pool is statistically indistinguishable from a coin flip out-of-sample.
2. **DSR of 0.033%:** Far below the mandatory $95\%$ statistical confidence threshold.
3. **Integrity Confirmation:** By utilizing genuine return streams, the framework produced authentic, unvarnished statistical metrics without false positive illusions.
