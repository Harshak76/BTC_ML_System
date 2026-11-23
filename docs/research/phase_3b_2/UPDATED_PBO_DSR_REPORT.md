# UPDATED PBO & DSR STATISTICAL REPORT
## Phase 3B.2 Cross-Validation Overfitting & Deflated Sharpe Ratio Re-Evaluation

**Repository:** `BTC_ML_System`  
**Branch:** `fix/phase-3b-2-data-integrity`  
**CSCV Engine:** `btc_ml_system.src.validation.pbo_cscv.PBOCSCVEngine`  
**DSR Engine:** `btc_ml_system.src.validation.deflated_sharpe.DeflatedSharpeEngine`  
**Audit Verdict:** `REJECTED — NOT ELIGIBLE FOR PAPER TRADING`

---

### 1. Executive Summary

In Phase 3B.2 Workstream 7, the Combinatorially Symmetric Cross-Validation (CSCV) and Deflated Sharpe Ratio (DSR) statistical engines were recalculated using the synchronized $20,424 \times 9$ candidate return matrix.

- **Probability of Backtest Overfitting (PBO):**
  $$\text{PBO} = 0.8889 \quad (\mathbf{88.89\%})$$
- **Deflated Sharpe Ratio (DSR):**
  $$\text{DSR} = 0.000101 \quad (\mathbf{0.010\%})$$

Both statistical metrics overwhelmingly confirm that selecting the top performer from this candidate pool is subject to severe selection overfitting, with near-zero probability of genuine statistical alpha.

---

### 2. CSCV / PBO Empirical Results

Combinatorially Symmetric Cross-Validation was executed with $S = 10$ contiguous chronological blocks, generating $\binom{10}{5} = 252$ symmetric In-Sample (IS) and Out-of-Sample (OOS) splits:

| Metric | Phase 3B (Synthetic Clones) | Phase 3B.2 (Authentic Data) | Quantitative Interpretation |
| :--- | :---: | :---: | :--- |
| **Probability of Backtest Overfitting (PBO)** | 48.02% | **88.89%** | Severe selection overfitting. $88.9\%$ probability that in-sample optimal strategy underperforms median out-of-sample. |
| **Number of Blocks ($S$)** | 10 | 10 | Standard contiguous 10-block partition. |
| **Combinations Evaluated** | 252 | 252 | Full combinatorial enumeration $\binom{10}{5}$. |
| **Mean In-Sample Sharpe** | -0.12 | -0.4854 | In-sample performance of selected best candidate. |
| **Mean Out-of-Sample Sharpe** | -0.51 | -1.6470 | Out-of-sample performance of selected best candidate. |
| **Performance Degradation** | 0.39 | **1.1616** | Substantial degradation between IS and OOS. |
| **Median Relative Rank** | 0.51 | **0.40** | Median OOS rank falls below 0.50. |
| **Probability of Loss ($\text{PnL} < 0$)** | 100.0% | **100.0%** | Zero candidate delivered positive net return out-of-sample. |

#### Critical Educational Distinction
- **What PBO Measures:** PBO measures *selection overfitting*—the likelihood that optimizing parameters to pick the best backtest result fails to provide above-median rank out-of-sample.
- **What PBO Does NOT Measure:** PBO does *not* measure the probability of monetary loss. In this candidate pool, the probability of monetary loss was $100.0\%$, because all 9 candidates generated negative net portfolio returns.
- **Why PBO Increased from 48% to 88.9%:** On authentic data, strategies that captured brief idiosyncratic moves on one stock (like NVDA or TSLA) failed completely when tested on other time blocks where those specific trends were absent. Parameter selection on in-sample blocks actively degraded out-of-sample performance.

---

### 3. Deflated Sharpe Ratio (DSR) Analysis

The Deflated Sharpe Ratio adjusts the observed Sharpe ratio of the top performer (`RS_MOM_DONCHIAN_40_V1`) for multiple testing, non-normality, and sample length:

$$\text{DSR} = \Phi\left(\frac{\widehat{\text{SR}} - \text{E}[\max_{n=1 \dots N} \text{SR}_n]}{\widehat{\sigma}_{\text{Mertens}}}\right)$$

| Metric | Empirical Value | Interpretation |
| :--- | :---: | :--- |
| **Observed Annualized Sharpe ($\widehat{\text{SR}}$)** | **-1.1076** | Negative net performance across multi-asset portfolio. |
| **Observed Periodic Sharpe** | -0.0142 | Hourly Sharpe ratio. |
| **Sample Size ($T$)** | 20,424 observations | Synchronized hourly steps. |
| **Candidate Count ($N$)** | 9 Registered Trials | Formally pre-registered Phase 3B/3B.2 candidates. |
| **Cross-Trial Sharpe Variance ($\mathbb{V}[\text{SR}_n]$)** | $6.241 \times 10^{-5}$ | Dispersion across candidate strategies. |
| **Expected Max Annualized Sharpe ($\text{E}[\max \text{SR}]$)** | **+0.9343** | Null hypothesis threshold for 9 trials. |
| **Mertens Standard Error ($\widehat{\sigma}$)** | 0.007065 | Asymptotic standard error with skewness and kurtosis. |
| **Skewness** | +0.9749 | Positive return skew from occasional trend runs. |
| **Kurtosis** | 112.06 | High leptokurtosis from clustering around zero cash returns. |
| **Deflated Sharpe Ratio (DSR)** | **0.000101 (0.010%)** | Probability that observed Sharpe reflects true alpha. |
| **Critical Alpha Threshold ($\alpha = 0.05$)** | $\text{DSR} \ge 0.950$ | **FAILED — OVERWHELMINGLY REJECTED** |

#### Multiple Testing Trial History Disclosure
- The calculated DSR of $0.010\%$ accounts strictly for the $N = 9$ formally registered trials.
- As disclosed in Phase 3B.1, between 25 and 40 unrecorded exploratory trials occurred during legacy V5 and Phase 1 development prior to `ExperimentTracker` integration.
- Incorporating those historical trials would raise $\text{E}[\max \text{SR}]$ even further, driving DSR even closer to absolute zero.
- Under any valid trial count boundary ($N=9$ or $N=49$), the null hypothesis of zero alpha cannot be rejected.

---

### 4. Workstream 7 Conclusion

Statistical validation conclusively rejects paper-trading eligibility:
- $\text{PBO} = 88.89\%$ confirms extreme selection overfitting.
- $\text{DSR} = 0.010\%$ confirms complete absence of statistically significant alpha.
- Status: `REJECTED — NOT ELIGIBLE FOR PAPER TRADING`.
