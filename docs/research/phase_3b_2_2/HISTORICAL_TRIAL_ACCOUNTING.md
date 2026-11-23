# HISTORICAL TRIAL ACCOUNTING REPORT
## Disclosure of Pre-Registration Candidate Pools, Historical Experiment Records, and Conditional DSR

**Repository:** `BTC_ML_System`  
**Primary Branch:** `fix/phase-3b-2-data-integrity`  
**Database:** `data/btc_ml_system.duckdb`  
**Status:** `VERIFIED & DISCLOSED`  

---

### 1. Executive Summary & Objective

In quantitative risk governance (López de Prado, 2014; Harvey & Liu, 2015), the Deflated Sharpe Ratio (DSR) and Family-Wise Error Rate (FWER) depend directly on the total number of candidate trials ($N$) evaluated throughout the research process.

When backtest trials are conducted without being logged to an immutable experiment registry, the system suffers from **unrecorded trial selection bias** (the "file-drawer problem"), causing the observed Sharpe ratio to appear more statistically significant than it genuinely is.

This report:
1. Conducts a forensic census of all known, recorded, and estimated historical experiments across the entire lifecycle of BTC-ML System V2.
2. Formally discloses the gap between recorded trials and early un-instrumented trials.
3. Evaluates the Deflated Sharpe Ratio (DSR) under the registered trial pool and demonstrates why DSR must remain explicitly classified as **conditional**.

---

### 2. Historical Experiment & Trial Census

#### 2.1 Complete Lifecycle Experiment Accounting Table

| Phase / Milestone | Period | Registry Status | Formally Recorded Trials ($N_{\text{rec}}$) | Identifiable Historical Trials ($N_{\text{ident}}$) | Description of Evaluated Configurations |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Phase 0 & 1** | Early 2026 | **UN-INSTRUMENTED** | 0 | $\ge 25$ | Initial bot development, RSI thresholds (30/70, 25/75), EMA parameters (20/50, 21/55), stop multipliers. Produced 1,334 trades in DuckDB. No `experiment_registry` existed. |
| **Phase 2.0 – 2.3** | Sep–Nov 2026 | Partial / File-based | 0 | $\ge 50$ | Quantitative Validation Lab: Walk-forward splits (12), Parameter sensitivity grid searches (~50), Monte Carlo permutations (1,000), Bootstrap resamples (1,000). |
| **Phase 3B** | Nov 20, 2026 | **REGISTERED** | **10** | 10 | First automated experiment tracker integration. 9 candidate strategies + 1 baseline run logged in `experiment_registry`. (Evaluated on legacy clone data). |
| **Phase 3B.2** | Nov 23, 2026 | **REGISTERED** | **9** | 9 | Revalidation of all 9 genuine candidate strategies across authentic multi-asset universe. Logged in `experiment_registry`. |
| **Total Registered** | - | **DuckDB Verified** | **19 Experiments** | - | Exact row count in `experiment_registry` table in `btc_ml_system.duckdb`. |
| **Estimated True Universe** | - | - | - | **$\mathbf{75 - 150}$ Trials** | Conservative estimate of all historical parameter iterations, feature checks, and backtest evaluations. |

---

### 3. Deflated Sharpe Ratio (DSR) Sensitivity to Trial Count

The Deflated Sharpe Ratio computes the probability that the observed Sharpe ratio exceeds the expected maximum Sharpe ratio under the null hypothesis of zero true alpha across $N$ independent trials:
$$\widehat{\text{SR}}_0 \approx \sqrt{V} \cdot \left((1 - \gamma) \Phi^{-1}\left(1 - \frac{1}{N}\right) + \gamma \Phi^{-1}\left(1 - \frac{1}{N \cdot e}\right)\right)$$

#### 3.1 DSR Recalculation Across Trial Pool Assumptions
Evaluated on top candidate: `RS_MOM_DONCHIAN_40_V1` (Observed Sharpe $\widehat{\text{SR}} = -1.11$, $T = 20,424$ hourly bars):

| Trial Count Assumption | Candidate Pool ($N$) | Expected Max Annualized Sharpe ($\widehat{\text{SR}}_{0, \text{ann}}$) | Deflated Sharpe Ratio (DSR) | Statistical Significance ($\alpha = 0.05$) |
| :--- | :---: | :---: | :---: | :---: |
| **Phase 3B Registered Candidates** | **$N = 9$** | **+0.93** | **0.0101% ($1.01 \times 10^{-4}$)** | **NOT SIGNIFICANT** |
| **Total DuckDB Experiments** | **$N = 19$** | **+1.32** | **0.0004% ($4.21 \times 10^{-6}$)** | **NOT SIGNIFICANT** |
| **Conservative Historical Census** | **$N = 50$** | **+1.64** | **$3.12 \times 10^{-8}$** | **NOT SIGNIFICANT** |
| **Full Estimated Research Lifecycle**| **$N = 100$** | **+1.85** | **$4.87 \times 10^{-10}$** | **NOT SIGNIFICANT** |

#### 3.2 Key Statistical Observations
1. **Even under the narrowest assumption ($N=9$):**  
   The Deflated Sharpe Ratio is **0.0101%**, failing the 95.0% threshold by a factor of 9,400x.
2. **Under full historical census ($N \ge 50$):**  
   The expected maximum Sharpe under pure noise rises to $+1.64$. DSR effectively reaches floating-point zero ($< 10^{-7}$).
3. **Manufacture Prohibition:**  
   Per Phase 3B.2.2 governance, we strictly refuse to manufacture a synthetic total trial number to plug into reports. Instead, we transparently disclose the recorded pool ($N=9$ and $N=19$) and state that the true historical trial pool is larger.

---

### 4. Mandatory Conditional Classification

Because trials conducted in Phase 0 and Phase 1 were not logged to an immutable cryptographic registry:
1. All DSR figures published in BTC-ML System V2 reports are explicitly designated as **CONDITIONAL DSR** ($\text{DSR} \mid N_{\text{registered}} = 9$).
2. The presence of unrecorded historical trials guarantees that the true unconditional DSR is strictly lower than the reported conditional DSR.
3. Because the conditional DSR is already 0.0101% (overwhelming rejection of alpha), the missing historical records do not alter the final verdict: the strategies fail statistical validation under any trial assumption.

---

### 5. Conclusion & Governance Remediation

1. **Trial Preservation Confirmed:** Exactly 19 experiment records are preserved in DuckDB.
2. **Missing Trial Disclosure:** Phase 0 and Phase 1 trial un-instrumentation is fully documented and disclosed.
3. **Zero Falsification:** No complete trial count was manufactured from guesses.
4. **Conditional Status Enforced:** DSR is formally classified as conditional on the 9 pre-registered candidates.
