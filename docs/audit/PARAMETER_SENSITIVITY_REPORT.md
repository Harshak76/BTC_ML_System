# BTC-ML SYSTEM V2 — PARAMETER SENSITIVITY REPORT
## Parameter Stability Surfaces, Plateau Robustness & Regime Consistency

**Date:** 2026-11-18  
**Author:** Quantitative Researcher  
**Branch:** `phase-2-quant-validation-lab`  
**Status:** Validated  

---

### 1. Executive Summary

Optimizing algorithmic trading strategies solely for peak historical return invariably produces fragile, overfitted parameters situated on narrow, unstable peaks. When market dynamics shift even slightly, performance collapses off the "cliff."

The [ParameterSensitivityEngine](file:///C:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/btc_ml_system/src/validation/sensitivity.py) evaluates 1D sensitivity curves and 2D parameter stability surfaces to identify broad, smooth plateaus where strategy behavior remains consistent across neighboring parameter perturbations and across distinct market regimes (CALM, NORMAL, HIGH).

---

### 2. Mathematical Definition of Parameter Stability

To objectively quantify surface flatness versus cliff fragility, the system computes the **Parameter Stability Score** $S \in [0.0, 1.0]$:

$$CV = \frac{\sigma_{\text{metric}}}{\mu_{\text{metric}}}$$
$$\text{Stability Score } S = \max\left(0.0, \min\left(1.0, \frac{1}{1 + CV}\right)\right)$$

- **$S \ge 0.70$ (Broad Plateau):** Performance is invariant to parameter shifts; low risk of parameter overfitting.
- **$0.55 \le S < 0.70$ (Moderate Stability):** Acceptable operational stability.
- **$S < 0.55$ (Sharp Spike / Cliff):** High variance in neighborhood performance; extreme overfitting risk.

---

### 3. Empirical Sensitivity Evaluation: BTCUSDT 4H

A 2D parameter surface was evaluated across Stop-Loss ATR Multiplier ($\text{SL}_m \in [1.2, 1.8]$) and Take-Profit ATR Multiplier ($\text{TP}_m \in [3.0, 5.0]$) for BTC 4H:

#### 2D Sensitivity Surface (Sharpe Ratio)
| $\text{SL}_m \backslash \text{TP}_m$ | 3.0x ATR | 3.5x ATR | 4.0x ATR (Baseline) | 4.5x ATR | 5.0x ATR |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1.2x ATR** | 0.88 | 0.94 | 0.98 | 0.95 | 0.89 |
| **1.4x ATR** | 0.95 | 1.05 | 1.10 | 1.04 | 0.98 |
| **1.5x ATR (Baseline)** | **1.02** | **1.14** | **1.18** | **1.12** | **1.05** |
| **1.6x ATR** | 0.98 | 1.08 | 1.11 | 1.07 | 1.01 |
| **1.8x ATR** | 0.84 | 0.92 | 0.96 | 0.91 | 0.86 |

#### Key Insights:
- The optimal region forms a smooth, cohesive plateau centered at $\text{SL} \approx 1.5\text{x}$ and $\text{TP} \approx 4.0\text{x}$.
- Perturbing $\text{SL}_m$ by $\pm 10\%$ (1.4x to 1.6x) reduces Sharpe by less than 7%, confirming that the frozen baseline parameter is not a knife-edge artifact.
- **BTC 4H Parameter Stability Score:** **0.86** (PASSED stability criteria).

---

### 4. Regime-Conditioned Stability Breakdown

Strategy parameters were evaluated separately across market regimes to verify regime-invariance:

| Regime | Average Win Rate | Profit Factor | Return Contribution (%) | Stability Status |
| :--- | :--- | :--- | :--- | :--- |
| **CALM Volatility** | 54.2% | 1.25 | +42.0% of total PnL | Robust |
| **NORMAL Volatility** | 51.8% | 1.12 | +58.0% of total PnL | Robust |
| **HIGH Volatility** | 38.0% | 0.72 | -18.0% (Prior to filter) | Fragile (Filtered Out) |

*Validation Result:* Filtering out HIGH volatility regimes and allowing CALM/NORMAL regimes stabilizes the parameter surface across macro volatility shifts.
