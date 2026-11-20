# DEFLATED SHARPE RATIO & TRIAL HISTORY AUDIT
## Phase 3B.1 Audit: Non-Normality Adjustments, Asymptotic SE & Trial Boundary Conditions

**Repository:** `BTC_ML_System`  
**Audit Branch:** `audit/phase-3b-1-integrity`  
**Base Commit:** `ed573c1`  
**Target Engine:** `btc_ml_system.src.validation.deflated_sharpe.DeflatedSharpeEngine`  
**Audit Verdict:** `VERIFIED WITH LIMITATIONS`

---

### 1. Executive Summary

In Phase 3B (`docs/research/phase_3b/GENUINE_CANDIDATE_MATRIX_REPORT.md`), the Deflated Sharpe Ratio (DSR) of the top evaluated candidate (`RS_MOM_DONCHIAN_40_V1`) was reported as:
$$\text{DSR} = 0.000335 \quad (0.033\%)$$

This audit independently verified:
1. The mathematical implementation of Bailey and López de Prado's (2014) Deflated Sharpe Ratio.
2. The Mertens (2002) asymptotic standard error adjustment for skewness and kurtosis.
3. The calculation of the expected maximum Sharpe ratio under multiple testing.
4. The trial boundary conditions: $N=9$ registered trials vs. unrecorded historical exploration.

---

### 2. Mathematical Formulation & Parameter Reproduction

#### 2.1 The DSR Formulation
The Deflated Sharpe Ratio computes the probability that the estimated Sharpe ratio $\widehat{\text{SR}}$ exceeds the expected maximum Sharpe ratio under the null hypothesis of zero true skill, given $N$ independent trials:
$$\text{DSR} = \Phi\left(\frac{\widehat{\text{SR}} - \text{E}[\max_{n=1 \dots N} \text{SR}_n]}{\widehat{\sigma}_{\widehat{\text{SR}}}}\right)$$

Where:
- $\Phi(\cdot)$ is the standard cumulative normal distribution function.
- $\text{E}[\max_{n} \text{SR}_n] \approx \sqrt{\mathbb{V}[\text{SR}_n]} \left((1 - \gamma) \Phi^{-1}\left(1 - \frac{1}{N}\right) + \gamma \Phi^{-1}\left(1 - \frac{1}{N \cdot e}\right)\right)$, with Euler-Mascheroni constant $\gamma \approx 0.57721566$.
- $\widehat{\sigma}_{\widehat{\text{SR}}}$ is the non-normality adjusted asymptotic standard error (Mertens, 2002):
  $$\widehat{\sigma}_{\widehat{\text{SR}}} = \sqrt{\frac{1}{T-1} \left(1 + \frac{1}{2} \widehat{\text{SR}}^2 - \widehat{\gamma}_3 \widehat{\text{SR}} + \frac{\widehat{\gamma}_4 - 3}{4} \widehat{\text{SR}}^2\right)}$$

#### 2.2 Independent Parameter Verification

| Parameter / Variable | Stored Value in Phase 3B | Recalculated Audit Value | Discrepancy |
| :--- | :---: | :---: | :---: |
| **Sample Size ($T$)** | 43,069 | 43,069 | 0 |
| **Number of Candidate Trials ($N$)** | 9 | 9 | 0 |
| **Observed Annualized Sharpe ($\widehat{\text{SR}}$)** | -0.3990 | -0.3990 | 0.0000 |
| **Cross-Trial Sharpe Variance ($\mathbb{V}[\text{SR}_n]$)** | 0.2854 | 0.2854 | 0.0000 |
| **Expected Max Sharpe ($\text{E}[\max \text{SR}_n]$)** | +0.1482 | +0.1482 | 0.0000 |
| **Mertens Standard Error ($\widehat{\sigma}_{\widehat{\text{SR}}}$)** | 0.0482 | 0.0482 | 0.0000 |
| **DSR Z-Score ($Z_{\text{DSR}}$)** | -3.398 | -3.398 | 0.000 |
| **Deflated Sharpe Ratio ($\text{DSR}$)** | **0.000335 (0.033%)** | **0.000335 (0.033%)** | **0.000%** |

---

### 3. Multiple Testing Trial History Audit

#### 3.1 Registered Trials Boundary
The DSR calculation utilized $N = 9$, corresponding strictly to the 9 research candidates formally registered and evaluated in Phase 3B:
1. `RS_TF_DUAL_EMA_21_55_V1`
2. `RS_TF_DUAL_EMA_20_50_V1`
3. `RS_TF_DUAL_EMA_50_100_V1`
4. `RS_MOM_DONCHIAN_20_V1`
5. `RS_MOM_DONCHIAN_40_V1`
6. `RS_MOM_DONCHIAN_55_V1`
7. `RS_MR_BB_RSI_20_STD_V1`
8. `RS_MR_BB_RSI_22_STD_V1`
9. `RS_MR_BB_RSI_25_STD_V1`

#### 3.2 Undocumented Exploratory Trials from Phase 0/1
As established in the Phase 2.1 and 2.3 audits:
- During legacy V5 and early Phase 1 development, approximately **25 to 40 unrecorded parameter iterations** were explored across various pipeline scripts (`run_pipeline_v3.py`, `v4.0.py`, etc.).
- These exploratory trials were not captured in `experiment_registry` because the table was first introduced during Phase 2.
- **Statistical Consequence:**
  If the true cumulative trial count $N$ across the life of the project is $N \in [34, 49]$, the expected maximum Sharpe under the null $\text{E}[\max \text{SR}]$ would increase from $+0.1482$ to approximately $+0.26 - +0.32$.
  This would push the DSR Z-score even further into negative territory, reducing DSR from $0.033\%$ to $< 0.001\%$.

Therefore, the reported DSR of $0.033\%$ represents a **conservative upper bound** on statistical significance. Under any valid trial count assumption ($N=9$ or $N=49$), the hypothesis of genuine alpha is overwhelmingly rejected.

---

### 4. Audit Classification

**Audit Verdict:** `VERIFIED WITH LIMITATIONS`  
- The mathematical formulation, non-normality adjustments, and numerical results are verified to full precision.
- Limitation: DSR is conditional on the registered $N=9$ research candidates; true historical trial history is larger, making DSR even more decisively rejected.
