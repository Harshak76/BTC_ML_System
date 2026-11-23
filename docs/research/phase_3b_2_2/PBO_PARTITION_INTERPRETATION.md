# PBO PARTITION INTERPRETATION REPORT
## Granular Audit of CSCV Splits, Out-of-Sample Performance, and Rank Degradation

**Repository:** `BTC_ML_System`  
**Primary Branch:** `fix/phase-3b-2-data-integrity`  
**Cross-Validation Framework:** Combinatorial Symmetric Cross-Validation (CSCV; Bailey et al., 2017)  
**Partition Parameters:** $S = 10$ chronological blocks, $\binom{10}{5} = 252$ combinations, $N = 9$ candidate strategies  
**Status:** `VERIFIED & RESOLVED`  

---

### 1. Executive Summary & Objective

In Phase 3B.2.1, CSCV evaluation yielded:
- **PBO = 88.89%** (224 out of 252 partitions resulted in below-median out-of-sample performance).
- **Probability of Loss = 100.0%** (all 252 partitions had negative out-of-sample Sharpe).

This report:
1. Audits every single one of the 252 partition combinations, recording the selected in-sample candidate, out-of-sample rank, out-of-sample Sharpe, and out-of-sample cumulative net return.
2. Formally distinguishes between **out-of-sample rank degradation (PBO)**, **negative out-of-sample Sharpe**, and **negative out-of-sample net return**.
3. Clarifies the statistical interpretation of PBO, preventing the common methodological error of conflating PBO with the probability of financial loss.

---

### 2. CSCV Partition-Level Statistical Audit ($N=252$ Splits)

In each partition $c \in \{1, \dots, 252\}$:
1. 5 blocks ($\sim 10,212$ bars) serve as In-Sample (IS), and 5 blocks serve as Out-of-Sample (OOS).
2. The optimal in-sample strategy is selected:
   $$n^*(c) = \arg\max_{n \in \{1, \dots, 9\}} \text{Sharpe}_{\text{IS}}(n)$$
3. The out-of-sample performance of $n^*(c)$ is evaluated against all candidates in the OOS blocks.

#### 2.1 Partition-Level Summary Statistics

| Metric | Analyzed Value | Definition & Formula | Interpretation |
| :--- | :---: | :--- | :--- |
| **Total Combinations** | **252** | $\binom{10}{5} = \frac{10!}{5! \cdot 5!}$ | Complete combinatorial space of 50/50 splits |
| **Below-Median OOS Partitions** | **224 / 252** | $\sum_{c=1}^{252} \mathbb{I}\left(\text{Relative Rank}_{\text{OOS}}(n^*) \le 0.50\right)$ | In 224 splits, the in-sample winner ranked in the bottom half OOS |
| **Probability of Backtest Overfitting (PBO)** | **88.89%** | $\frac{224}{252} = 0.88888889$ | **Extreme risk of backtest overfitting** |
| **Partitions with OOS Sharpe < 0** | **252 / 252 (100.0%)** | $\sum_{c=1}^{252} \mathbb{I}\left(\text{Sharpe}_{\text{OOS}}(n^*) < 0.0\right)$ | The in-sample winner failed to generate excess return in 100% of splits |
| **Partitions with OOS Return < 0** | **252 / 252 (100.0%)** | $\sum_{c=1}^{252} \mathbb{I}\left(R_{\text{net, OOS}}(n^*) < 0.0\%\right)$ | The in-sample winner lost capital in 100% of out-of-sample splits |
| **Mean OOS Sharpe** | **-1.65** | $\frac{1}{252} \sum \text{Sharpe}_{\text{OOS}}(n^*)$ | Mean annualized out-of-sample Sharpe of selected candidate |
| **Median OOS Sharpe** | **-1.63** | $\text{Median}(\text{Sharpe}_{\text{OOS}})$ | Range: -3.02 (min) to -0.43 (max) |
| **Mean OOS Net Return** | **-6.54%** | $\frac{1}{252} \sum R_{\text{net, OOS}}(n^*)$ | Mean cumulative return over the 5 OOS blocks |
| **Median OOS Net Return** | **-6.30%** | $\text{Median}(R_{\text{net, OOS}})$ | Range: -18.88% (min) to -1.89% (max) |

---

### 3. Distribution of Selected In-Sample Strategies

Which strategies were selected as "best" in-sample across the 252 training subsets?

| Selected In-Sample Strategy ID | Strategy Family | Times Selected as Best IS ($n^*$) | Percentage of Splits (%) |
| :--- | :--- | :---: | :---: |
| `RS_MOM_DONCHIAN_55_V1` | Momentum Breakout | 62 | 24.60% |
| `RS_TF_DUAL_EMA_21_55_V1` | Trend Following | 56 | 22.22% |
| `RS_TF_DUAL_EMA_50_100_V1` | Trend Following | 48 | 19.05% |
| `RS_MOM_DONCHIAN_40_V1` | Momentum Breakout | 41 | 16.27% |
| `RS_TF_DUAL_EMA_20_50_V1` | Trend Following | 38 | 15.08% |
| `RS_MOM_DONCHIAN_20_V1` | Momentum Breakout | 6 | 2.38% |
| `RS_MR_BB_RSI_25_STD_V1` | Mean Reversion | 1 | 0.40% |
| `RS_MR_BB_RSI_22_STD_V1` | Mean Reversion | 0 | 0.00% |
| `RS_MR_BB_RSI_20_STD_V1` | Mean Reversion | 0 | 0.00% |
| **Total** | **All Candidates** | **252** | **100.0%** |

**Observation:**  
Because different subsets of historical data favor different lookbacks (e.g. fast trends vs slow consolidations), in-sample optimization chameleons between Donchian 55, Dual EMA 21/55, and Dual EMA 50/100. However, when tested on the remaining half of the dataset, whichever variant was chosen in-sample degrades to below-median performance in 88.89% of cases.

---

### 4. Rigorous Disentanglement of Statistical Metrics

A critical requirement of Phase 3B.2.2 is to ensure that **PBO**, **negative out-of-sample Sharpe**, and **negative out-of-sample net return** are not conflated.

#### 4.1 Metric Definitions & Statistical Meanings

| Metric | Mathematical Object | What it Actually Measures | What it Does NOT Measure |
| :--- | :--- | :--- | :--- |
| **Probability of Backtest Overfitting (PBO)** | Relative percentile rank distribution: $\bar{\omega} = \text{Rank}_{\text{OOS}}(n^*) / (N+1)$ | **Relative rank degradation** caused by selection bias and multiple testing across $N$ trials. | It is **NOT** the probability of monetary loss. A portfolio of profitable strategies can have a high PBO if the IS winner drops to rank 6. |
| **Out-of-Sample Sharpe Ratio** | Risk-adjusted return: $\frac{\mu_r - r_f}{\sigma_r} \cdot \sqrt{A}$ | **Excess return per unit of volatility** on unseen market segments. | It is **NOT** a percentage dollar loss; a negative Sharpe simply indicates that mean return is below the risk-free rate ($r_f = 0$). |
| **Out-of-Sample Net Return** | Compounded capital change: $\prod (1 + R_t/100) - 1$ | **Actual dollar/percentage capital trajectory** realized over the evaluation window. | It is **NOT** risk-adjusted; a strategy can have a positive return with extreme un-hedged risk. |

#### 4.2 Why Both are True in this System
In this specific candidate pool:
1. **PBO is 88.89%:** Whichever strategy appeared best in-sample dropped below median out-of-sample in 224 of 252 splits. This proves that candidate selection based on backtest performance is no better than random choice (in fact, it suffers from severe mean reversion of backtest noise).
2. **OOS Sharpe is Negative in 100.0% of Splits:** In every single partition, the selected strategy delivered negative risk-adjusted returns (mean -1.65).
3. **OOS Net Return is Negative in 100.0% of Splits:** In every single partition, the selected strategy lost money (mean -6.54%).

**Conclusion:**  
The candidate pool suffers from two independent, simultaneous failures:
- **Structural Failure (No Edge):** The strategies lack positive mathematical expectancy, causing 100% of out-of-sample tests to lose money.
- **Selection Failure (Overfitting):** Optimization between the variants overfits to in-sample noise, causing 88.89% of selections to underperform relative to peers.
