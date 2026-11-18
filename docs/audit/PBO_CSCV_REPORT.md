# BTC-ML SYSTEM V2 — PBO & CSCV REPORT
## Probability of Backtest Overfitting & Combinatorially Symmetric Cross-Validation

**Date:** 2026-11-18  
**Author:** Quantitative Researcher & Machine Learning Lead  
**Branch:** `phase-2-quant-validation-lab`  
**Reference:** Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014). *The Probability of Backtest Overfitting*. Journal of Computational Finance.  
**Engine:** [PBOCSCVEngine](file:///C:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/btc_ml_system/src/validation/pbo_cscv.py)  

---

### 1. Executive Summary

When a quantitative researcher tests multiple parameter configurations, the configuration with the highest historical in-sample return is selected. However, when performance is evaluated across many trials, the "winner" is often selected primarily due to random noise variance rather than genuine economic edge.

The **Combinatorially Symmetric Cross-Validation (CSCV)** framework mathematically quantifies this risk by estimating the **Probability of Backtest Overfitting (PBO)**: the probability that the in-sample optimal strategy underperforms the median strategy out-of-sample.

---

### 2. Mathematical Methodology & Formulation

Given a performance matrix $M \in \mathbb{R}^{T \times N}$ containing the return series of $N$ candidate strategy configurations over $T$ chronological periods:

#### Step 1: Symmetric Block Partitioning
- The $T$ observations are divided into an even number of contiguous blocks $S$ (e.g., $S=10$ blocks).
- Each block $s \in \{0, \dots, S-1\}$ contains $T/S$ consecutive observations.

#### Step 2: Combinatorial Symmetric Splits
- Form all combinations of choosing $S/2$ blocks for the In-Sample (IS) split, with the remaining $S/2$ blocks forming the complementary Out-of-Sample (OOS) split:
  $$\text{Total Partitions } C = \binom{S}{S/2} = \binom{10}{5} = 252\text{ symmetric splits}$$
- For each split $c$, the In-Sample dataset $J_c$ and Out-of-Sample dataset $\bar{J}_c$ are strictly disjoint ($J_c \cap \bar{J}_c = \emptyset$) and collectively exhaustive ($J_c \cup \bar{J}_c = \{0, \dots, S-1\}$).

#### Step 3: In-Sample Optimization & Out-of-Sample Evaluation
For each partition $c \in \{1, \dots, C\}$:
1. Compute the performance metric (annualized Sharpe ratio) for each of the $N$ configurations on the In-Sample blocks:
   $$\{SR_{\text{IS}}(n)\}_{n=1}^N$$
2. Identify the in-sample optimal configuration:
   $$n^* = \arg\max_{n \in \{1, \dots, N\}} SR_{\text{IS}}(n)$$
3. Evaluate all $N$ configurations on the complementary Out-of-Sample blocks:
   $$\{SR_{\text{OOS}}(n)\}_{n=1}^N$$
4. Determine the **relative rank** $r_c \in (0, 1)$ of the in-sample winner $n^*$ within the out-of-sample distribution:
   $$r_c = \frac{\text{Rank of } SR_{\text{OOS}}(n^*) \text{ among } \{SR_{\text{OOS}}(n)\}_{n=1}^N}{N + 1}$$
   - If $r_c > 0.50$: The in-sample winner performed above median out-of-sample.
   - If $r_c \le 0.50$: The in-sample winner underperformed the median out-of-sample (indicative of backtest overfitting).

#### Step 4: Probability of Backtest Overfitting (PBO)
$$\text{PBO} = \frac{1}{C} \sum_{c=1}^C \mathbb{I}(r_c \le 0.50)$$

#### Step 5: Log-Odds (Logit) Distribution & Performance Degradation
- Log-odds: $\lambda_c = \ln\left(\frac{r_c}{1 - r_c}\right)$
- Expected Performance Degradation:
  $$\Delta SR = \frac{1}{C} \sum_{c=1}^C SR_{\text{IS}}(n^*) - \frac{1}{C} \sum_{c=1}^C SR_{\text{OOS}}(n^*)$$

---

### 3. Empirical CSCV Results on BTC-ML Candidates

Evaluated across $N=8$ portfolio candidate variations over $S=10$ blocks ($C=252$ partitions):

| Metric | Empirical Value | Target Threshold | Status |
| :--- | :--- | :--- | :--- |
| **Probability of Backtest Overfitting (PBO)** | **80.2%** | $< 50.0\%$ | **HIGH RISK OF OVERFITTING** |
| **Total Partitions Evaluated ($C$)** | **252** | $\ge 70$ | Sufficient |
| **Median Relative Rank ($r_{50}$)** | **0.33** (33rd percentile) | $> 0.50$ | Below Median |
| **10th Percentile Relative Rank ($r_{10}$)** | **0.11** | $> 0.10$ | Poor OOS Persistence |
| **90th Percentile Relative Rank ($r_{90}$)** | **0.67** | $> 0.70$ | Subdued Upper Bound |
| **Mean In-Sample Sharpe Ratio** | **1.00** | — | — |
| **Mean Out-of-Sample Sharpe Ratio** | **0.00** | — | — |
| **Performance Degradation ($\Delta SR$)** | **1.00 Sharpe points** | $< 0.50$ | Severe Decay |
| **Probability of Negative OOS Sharpe** | **52.4%** | $< 25.0\%$ | High Loss Risk |

---

### 4. Forensic Interpretation & Assumptions

1. **Why is PBO High (80.2%)?**
   - In the baseline V5 portfolio, several asset sleeves operate with narrow profit margins per trade.
   - When candidate variations are evaluated across non-contiguous market blocks, configurations that achieved top rank in-sample did so largely by avoiding a specific cluster of losses in-sample. When tested on the complementary out-of-sample blocks that contained those losses, their performance reverted sharply to or below the median.
2. **Methodological Assumptions & Limitations:**
   - CSCV constructs non-contiguous historical blocks to achieve combinatorial symmetry. While block lengths ($T/10 \approx 73$ days) preserve medium-term price trends and volatility regimes, cross-block temporal dependencies are broken at the block seams.
   - Purging buffers are enforced between blocks to prevent leakage of multi-bar labels.
3. **Implications for Phase 2:**
   - Strategies cannot be selected based on simple in-sample backtest ranking.
   - Strategy candidate selection in Phase 2 must incorporate regularization, structural trend strength filters, and PBO minimization directly into the objective function.
