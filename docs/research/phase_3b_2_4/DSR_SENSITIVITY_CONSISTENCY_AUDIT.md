# DEFLATED SHARPE RATIO SENSITIVITY & MONOTONICITY CONSISTENCY AUDIT
## Mathematical Verification of Extreme Value Theory Bounds, Trial Pool Variances, and Multi-Testing Penalization

**Repository:** `BTC_ML_System`  
**Primary Branch:** `fix/phase-3b-2-data-integrity`  
**Evaluation Subject:** `DeflatedSharpeEngine` (`src/validation/deflated_sharpe.py`)  
**Top Observed Candidate:** `RS_MOM_DONCHIAN_40_V1`  
**Status:** `AUDITED & FULLY RECONCILED`  

---

### 1. Executive Summary & Objective

In Phase 3B.2.3, the DSR sensitivity table exhibited an apparent mathematical anomaly:
- At $N = 10$, the reported Expected Maximum Annualized Sharpe was **+1.2325**.
- At $N = 19$, the reported Expected Maximum Annualized Sharpe decreased to **+1.1538**.

According to Extreme Value Theory (Bailey & López de Prado, 2014), under a **fixed null distribution with constant trial variance $V$**, the expected maximum of $N$ independent Gaussian trials is strictly monotonically increasing in $N$:
$$\frac{\partial \mathbb{E}[\max_{N} \text{SR}]}{\partial N} > 0 \quad \forall N \ge 2, V > 0$$

This audit:
1. Identifies the exact mathematical root cause of the apparent non-monotonic decrease from $N=10$ to $N=19$.
2. Formally documents all input parameters, moment estimators, standard errors, and candidate pools across $N \in \{9, 10, 19, 25, 75, 150\}$.
3. Verifies strict mathematical monotonicity under a fixed, standardized null distribution.
4. Distinguishes verified database trial records from estimated undocumented historical exploratory trials.

---

### 2. Root Cause Analysis of the N=10 to N=19 Anomaly

The Deflated Sharpe Engine approximates the expected maximum Sharpe ratio using the Euler-Mascheroni extreme value formulation:
$$\mathbb{E}[\max_{N} \text{SR}_{\text{per}}] \approx \sqrt{V_{\text{per}}} \cdot \left((1 - \gamma) \Phi^{-1}\left(1 - \frac{1}{N}\right) + \gamma \Phi^{-1}\left(1 - \frac{1}{N \cdot e}\right)\right)$$
where:
- $\gamma \approx 0.57721566$ is the Euler-Mascheroni constant.
- $V_{\text{per}}$ is the variance of periodic Sharpe ratios across the trial pool.
- $\mathbb{E}[\max_{N} \text{SR}_{\text{ann}}] = \mathbb{E}[\max_{N} \text{SR}_{\text{per}}] \times \sqrt{A}$.

#### 2.1 Why Expected Maximum Sharpe Dropped from N=10 to N=19
The discrepancy occurred because the Phase 3B.2.3 sensitivity script **did not hold trial variance $V$ constant**, nor did it consistently apply the empirical variance of the 19-experiment registry:

1. **For $N = 10$ (Baseline + 9 Candidates):**  
   The script evaluated the empirical variance of the 10-trial pool:
   $$\text{Trial Sharpes} = [-0.0030, -1.3484, -1.4450, -1.3359, -1.6404, -1.1076, -1.1190, -2.9005, -2.4568, -1.6569]$$
   Because the original baseline ($\text{SR} = -0.0030$) is an outlier compared to the 9 research candidates ($\text{SR} \in [-1.11, -2.90]$), the sample variance inflated significantly:
   $$V_{\text{per}, 10} = 6.9942 \times 10^{-5} \quad (\sigma_{\text{ann}, 10} = \mathbf{0.7827})$$
   Evaluating $N=10$ with this inflated variance yielded $\mathbb{E}[\max_{10} \text{SR}_{\text{ann}}] = \mathbf{+1.2325}$.
2. **For $N = 19$ (All Registry Rows):**  
   Instead of using the empirical variance of all 19 DuckDB experiments ($V_{\text{per}, 19} = 5.5995 \times 10^{-5}$, which yields $\mathbb{E}[\max] = \mathbf{+1.3153}$), the script accidentally plugged in the lower variance of only the 9 candidates:
   $$V_{\text{per}, 9} = 4.3090 \times 10^{-5} \quad (\sigma_{\text{ann}, 9} = \mathbf{0.6144})$$
   Because $\sqrt{V_9} = 0.00656 < \sqrt{V_{10}} = 0.00836$, the $21.5\%$ decrease in standard deviation overwhelmed the increase in sample size from $10$ to $19$, producing the artificial drop to $+1.1538$.

---

### 3. Rigorous DSR Sensitivity Evaluation Across Trial Scenarios

All evaluations below are performed on the top candidate `RS_MOM_DONCHIAN_40_V1`:
- **Observed Annualized Sharpe:** $\text{SR}_{\text{ann}} = \mathbf{-1.1075655}$
- **Observed Periodic Sharpe:** $\text{SR}_{\text{per}} = \mathbf{-0.0118339}$
- **Periodic Return Frequency:** Hourly ($1\text{h}$)
- **Annualization Factor:** $\sqrt{365 \times 24} = \sqrt{8760} \approx 93.59487$
- **Sample Size ($T$):** $20,424$ hourly return periods
- **Sample Skewness ($\gamma_3$):** $+0.97494$
- **Sample Kurtosis ($\gamma_4$):** $112.0625$ (uncentered Pearson kurtosis)
- **Mertens (2002) Standard Error ($\text{SE}_{\text{Mertens}}$):**
  $$\text{SE}_{\text{Mertens}} = \sqrt{\frac{1}{T-1} \left(1 - \gamma_3 \text{SR}_{\text{per}} + \frac{\gamma_4 - 1}{4} \text{SR}_{\text{per}}^2\right)} = \mathbf{0.006998}$$

---

#### 3.1 Case A: Controlled Monotonicity Under Constant Null Variance ($V_{\text{fixed}} = V_{9}$)
In pure statistical hypothesis testing, the null hypothesis assumes that all $N$ trials are drawn from the same underlying null distribution. Holding $V_{\text{per}}$ fixed at $4.3090 \times 10^{-5}$ ($\sigma_{\text{ann}} = 0.6144$) proves strict mathematical monotonicity:

| Trial Count ($N$) | Pool Description | Periodic Null Variance ($V_{\text{per}}$) | Expected Max Periodic Sharpe | Expected Max Annualized Sharpe | Z-Score vs Null Max | Deflated Sharpe Ratio (DSR) | $p$-value ($1 - \text{DSR}$) | Monotonicity Check |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **9** | Registered Phase 3B.2 Candidates | $4.3090 \times 10^{-5}$ | $0.009983$ | **+0.9343** | $-3.1176$ | **0.09115%** | $0.999089$ | Baseline |
| **10** | Documented Strategy Ideas | $4.3090 \times 10^{-5}$ | $0.010336$ | **+0.9674** | $-3.1681$ | **0.07671%** | $0.999233$ | $\mathbb{E}[\max] \uparrow, \text{DSR} \downarrow$ |
| **19** | Total DuckDB Registry Rows | $4.3090 \times 10^{-5}$ | $0.012328$ | **+1.1538** | $-3.4527$ | **0.02774%** | $0.999723$ | $\mathbb{E}[\max] \uparrow, \text{DSR} \downarrow$ |
| **25** | Documented + Sensitivity Grids | $4.3090 \times 10^{-5}$ | $0.013110$ | **+1.2270** | $-3.5645$ | **0.01823%** | $0.999818$ | $\mathbb{E}[\max] \uparrow, \text{DSR} \downarrow$ |
| **75** | Estimated Historical Exploratory | $4.3090 \times 10^{-5}$ | $0.015936$ | **+1.4915** | $-3.9684$ | **0.00362%** | $0.999964$ | $\mathbb{E}[\max] \uparrow, \text{DSR} \downarrow$ |
| **150**| Full Research Lifecycle Upper Bound | $4.3090 \times 10^{-5}$ | $0.017528$ | **+1.6405** | $-4.1958$ | **0.00136%** | $0.999986$ | $\mathbb{E}[\max] \uparrow, \text{DSR} \downarrow$ |

*Verification:* Under constant variance, $\mathbb{E}[\max]$ increases strictly monotonically from $+0.9343$ to $+1.6405$, and DSR decreases strictly monotonically from $0.091\%$ to $0.001\%$.

---

#### 3.2 Case B: Empirical Pool Variances (Where Each Pool's Actual Variance is Used)
If each database pool is evaluated strictly using its own internal sample variance:

| Trial Count ($N$) | Candidate Pool Used | Specific Sharpe Set Evaluated | Periodic Pool Variance ($V_{\text{per}}$) | Annualized Pool Std Dev ($\sigma_{\text{ann}}$) | Expected Max Annualized Sharpe | Deflated Sharpe Ratio (DSR) | $p$-value |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **9** | **Phase 3B.2 Candidates** | 9 authentic candidate strategies | $4.3090 \times 10^{-5}$ | $0.6144$ | **+0.9343** | **0.09115%** | $0.999089$ |
| **10** | **Baseline + 9 Candidates** | Frozen baseline + 9 candidates | $6.9942 \times 10^{-5}$ | $0.7827$ | **+1.2325** | **0.01765%** | $0.999823$ |
| **19** | **All 19 DuckDB Rows** | All Phase 2, 3B, and 3B.2 entries | $5.5995 \times 10^{-5}$ | $0.7004$ | **+1.3153** | **0.01081%** | $0.999892$ |

*Verification:* When the true empirical variance of all 19 DuckDB entries is evaluated ($V_{\text{per}} = 5.5995 \times 10^{-5}$), $\mathbb{E}[\max_{19}]$ is **+1.3153**, which is **strictly greater than** $\mathbb{E}[\max_{10}] = \mathbf{+1.2325}$! The apparent decrease in Phase 3B.2.3 was purely an artifact of passing the wrong variance parameter.

---

### 4. Categorical Distinction of Trial Pools

To prevent multi-testing distortion, governance strictly classifies all research trials into five distinct categories:

1. **Independent Candidate Trials (9 Trials — VERIFIED):**  
   The nine distinct algorithmic formulations developed in Phase 3A/3B:
   - Trend Following: Dual EMA (21/55), Dual EMA (20/50), Dual EMA (50/100).
   - Time-Series Momentum: Donchian (20), Donchian (40), Donchian (55).
   - Mean Reversion: Bollinger Bands (2.0 std), Bollinger Bands (2.2 std), Bollinger Bands (2.5 std).
2. **Corrected-Data Reruns (9 Runs — VERIFIED, NOT INDEPENDENT):**  
   The nine Phase 3B.2 evaluations on authentic Alpaca data (`EXP-20261123-121614-7f1542` to `EXP-20261123-123043-dd670a`). These evaluate the exact same model logic and parameters on corrected data; they are **re-validations, not additional independent trials**.
3. **Baseline Experiments (1 Run — VERIFIED):**  
   `EXP-20261118-171823-104f2f` (`btc_ml_system_v5_portfolio` v5.1). Represents the rejected production anchor.
4. **Validation-Only Experiments (0 Rows in Registry):**  
   Walk-forward splits, Monte Carlo permutations, and bootstrap iterations in Phase 2 were executed as validation engine subroutines without creating separate strategy registry rows.
5. **Estimated Undocumented Historical Trials ($\ge 75$ Trials — ESTIMATED, NOT VERIFIED):**  
   Informal exploratory sweeps conducted during Phases 0 and 1 prior to registry instrumentation (reflected by 1,334 historical trade records in DuckDB). **Governance Rule:** These are explicitly classified as sensitivity scenarios and are never presented as verified database counts.

---

### 5. Audit Conclusion

1. **Monotonicity Restored & Proven:** Under constant null variance, Expected Maximum Sharpe increases strictly monotonically from $+0.9343$ ($N=9$) to $+1.6405$ ($N=150$). Under empirical pool variances, $E[\max]$ increases from $+0.9343$ ($N=9$) to $+1.2325$ ($N=10$) to $+1.3153$ ($N=19$).
2. **Discrepancy Explained:** The decrease in Phase 3B.2.3 occurred because the script inadvertently substituted $V_9$ into the calculation for $N=19$ while using $V_{10}$ for $N=10$.
3. **Statistical Significance Invariant:** Under every trial definition, DSR remains below $0.1\%$, confirming overwhelming statistical rejection of alpha.
