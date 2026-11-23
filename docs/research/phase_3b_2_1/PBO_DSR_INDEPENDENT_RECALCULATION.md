# INDEPENDENT AUDIT 7: PBO & DSR INDEPENDENT RECALCULATION
## Verification of Combinatorial Symmetric Cross-Validation and Deflated Sharpe Ratio

**Repository:** `BTC_ML_System`  
**Starting Commit:** `2a5ef45`  
**Audit Branch:** `audit/phase-3b-2-1-verification`  
**Audit Verdict:** `VERIFIED`  

---

### 1. Executive Summary & Objective

In algorithmic finance, the Probability of Backtest Overfitting (PBO; Bailey, Borwein, López de Prado, Zhu, 2017) and the Deflated Sharpe Ratio (DSR; López de Prado, 2014) are mandatory statistical guards against selection bias and data snooping.

In Phase 3B.1, Audit 3 revealed that PBO on the legacy matrix was reported as 48.02% (121/252 splits). In Phase 3B.2, evaluation on the synchronized authentic dataset yielded an updated PBO of **88.89%** and a DSR of **0.0101%**.

This independent audit:
1. Re-executes the Combinatorial Symmetric Cross-Validation (CSCV) engine with $S=10$ blocks.
2. Independently extracts the out-of-sample rank distribution across all 252 splits.
3. Recalculates the exact PBO and Deflated Sharpe Ratio.
4. Analyzes the conditional classification of DSR in light of historical unrecorded trials.

---

### 2. CSCV PBO Independent Recalculation

#### 2.1 Combinatorial Framework
- **Number of Candidates ($N$):** 9 genuine strategy return series.
- **Number of Blocks ($S$):** 10 equal-sized chronological blocks ($T / 10 \approx 2,042$ bars per block).
- **Sub-Matrix Partitions:** Combinations choosing $S/2 = 5$ blocks for in-sample (IS) and the remaining 5 blocks for out-of-sample (OOS):
  $$\binom{S}{S/2} = \binom{10}{5} = \frac{10!}{5! \cdot 5!} = \mathbf{252 \text{ unique splits}}$$

#### 2.2 Independent Calculation Output

| Metric | Phase 3B.2 Reported | Independently Recalculated | Discrepancy | Evaluation |
| :--- | :---: | :---: | :---: | :---: |
| **Evaluated Partitions** | 252 splits | **252 splits** | 0 | **EXACT MATCH** |
| **Splits with OOS Rank $\le 0.50$** | 224 splits | **224 splits** | 0 | **EXACT MATCH** |
| **Probability of Backtest Overfitting (PBO)** | 88.89% | **88.888889% (88.89%)** | 0.00% | **EXACT MATCH** |
| **Probability of Loss ($P(\text{OOS Sharpe} < 0)$)** | 100.0% | **100.0% (252/252)** | 0.00% | **EXACT MATCH** |
| **Median Relative OOS Rank** | 0.40 | **0.40** | 0.00 | **EXACT MATCH** |
| **P10 Relative OOS Rank** | 0.20 | **0.20** | 0.00 | **EXACT MATCH** |
| **P90 Relative OOS Rank** | 0.60 | **0.60** | 0.00 | **EXACT MATCH** |
| **Mean In-Sample Sharpe** | -0.4854 | **-0.485428** | $< 10^{-6}$ | **EXACT MATCH** |
| **Mean Out-of-Sample Sharpe** | -1.6470 | **-1.647004** | $< 10^{-6}$ | **EXACT MATCH** |
| **Performance Degradation** | 1.1616 | **1.161576** | $< 10^{-6}$ | **EXACT MATCH** |
| **Overfitting Verdict** | OVERFITTED | **OVERFITTED** | None | **HIGH RISK OF OVERFITTING** |

#### 2.3 Mathematical PBO Formula
$$\text{PBO} = \frac{1}{\binom{S}{S/2}} \sum_{c=1}^{\binom{S}{S/2}} \mathbb{I}\left(\text{Rank}_{\text{OOS}}(n^*(c)) \le \frac{N}{2}\right) = \frac{224}{252} = \mathbf{0.88888889 \implies 88.89\%}$$
In 88.89% of market partitions, whichever strategy appeared best in-sample performed below median out-of-sample.

---

### 3. Deflated Sharpe Ratio (DSR) Independent Recalculation

The Deflated Sharpe Ratio adjusts the estimated Sharpe ratio for:
1. Multiple testing / selection bias ($N$ candidate trials).
2. Non-normality of returns (skewness $\gamma_3$ and kurtosis $\gamma_4$).
3. Length of observation sample ($T$).

#### 3.1 DSR Input Parameters & Calculation

$$\text{DSR} = \text{PSR}\left(\widehat{\text{SR}}_0\right) = \Phi\left(\frac{(\widehat{\text{SR}} - \widehat{\text{SR}}_0) \sqrt{T - 1}}{\sqrt{1 - \widehat{\gamma}_3 \widehat{\text{SR}} + \frac{\widehat{\gamma}_4 - 1}{4} \widehat{\text{SR}}^2}}\right)$$

Where the expected maximum Sharpe under the null hypothesis of zero alpha across $N$ trials is:
$$\widehat{\text{SR}}_0 \approx \sqrt{V} \cdot \left((1 - \gamma) \Phi^{-1}\left(1 - \frac{1}{N}\right) + \gamma \Phi^{-1}\left(1 - \frac{1}{N \cdot e}\right)\right)$$

| Parameter | Symbol | Independently Verified Value |
| :--- | :---: | :---: |
| Top Strategy ID | - | `RS_MOM_DONCHIAN_40_V1` |
| Observed Periodic Sharpe | $\widehat{\text{SR}}_{\text{periodic}}$ | -0.01424176 |
| Observed Annualized Sharpe ($252 \times 24$) | $\widehat{\text{SR}}_{\text{ann}}$ | -1.10756550 |
| Observation Count | $T$ | 20,424 bars |
| Recorded Candidate Trials | $N$ | 9 strategies |
| Variance of Candidate Sharpes | $V$ | $6.241175 \times 10^{-5}$ |
| Return Series Skewness | $\widehat{\gamma}_3$ | 0.9749438 |
| Return Series Kurtosis | $\widehat{\gamma}_4$ | 112.06254 |
| Mertens Standard Error | $\sigma_{\text{Mertens}}$ | 0.00706541 |
| Expected Max Annualized Sharpe | $\widehat{\text{SR}}_{0, \text{ann}}$ | +0.9343400 |
| **Deflated Sharpe Ratio (DSR)** | $\text{DSR}$ | **0.00010114 (0.0101%)** |
| Probabilistic Sharpe Ratio (PSR vs 0.0) | $\text{PSR}$ | 0.02191561 (2.19%) |
| Statistical Significance ($\alpha = 0.05$) | - | **NOT SIGNIFICANT** |

**Forensic Finding:**  
The Deflated Sharpe Ratio is **0.0101%**, vastly below the 95.0% threshold required for statistical credibility.

---

### 4. Conditional Classification: Unrecorded Historical Trials

The DSR calculation above is computed **conditional on $N = 9$ registered candidates**.

#### 4.1 Unrecorded Trials Context
As established in the Phase 2.1, 2.2, 2.3, and 3B.1 audits:
- In Phase 0 and Phase 1, multiple strategy iterations, indicator parameters, and threshold searches were conducted without logging to `experiment_registry`.
- If the true number of historical trials is $N_{\text{true}} \ge 50$ or $100$:
  $$\lim_{N \to \infty} \widehat{\text{SR}}_0(N) \propto \sqrt{2 \ln N} \uparrow$$
  As $N$ increases, $\widehat{\text{SR}}_0$ rises above 1.50, driving the theoretical DSR even closer to absolute zero.

**Audit Conclusion:**  
Even under the most optimistic, conservative assumption of only $N=9$ trials, the system exhibits zero statistical significance ($\text{DSR} = 0.01\%$). Accounting for unrecorded historical trials further reinforces the definitive rejection of all candidate strategies.

---

### 5. Audit 7 Verdict & Status

**Verdict:** `VERIFIED`

1. CSCV PBO is independently reproduced at exactly **88.89%** (224/252 splits).
2. Deflated Sharpe Ratio is independently reproduced at **0.0101%**.
3. Overfitting risk is extreme; zero strategy alpha is present.
