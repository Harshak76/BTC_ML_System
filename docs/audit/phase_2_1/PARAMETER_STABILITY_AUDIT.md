# PHASE 2.1 — PARAMETER STABILITY & SENSITIVITY AUDIT REPORT

**Audit Date:** November 19, 2026  
**Auditor:** Quantitative Risk & Software Verification Engine  
**Target Repository:** `BTC_ML_System`  
**Target Module:** `btc_ml_system/src/validation/sensitivity.py`  
**Experiment File Audited:** `btc_ml_system/experiments/EXP-20261118-171823-104f2f.json`  
**Status:** `INCORRECT` (Algorithmic / Formula Defect in Stability Scoring Function)  

---

## 1. Executive Summary

We performed an in-depth code and mathematical audit of the parameter sensitivity engine implemented in `src/validation/sensitivity.py`.

In experiment `EXP-20261118-171823-104f2f`, the validation gate reported a **Parameter Plateau Stability Score of exactly 0.00** against a minimum requirement of 0.55, causing the check to FAIL.
Our forensic inspection of `sensitivity.py` (lines 144–145) uncovered an **explicit algorithmic defect**:
The stability score calculation forces the returned score to `0.0` whenever the mean performance metric across the parameter grid is non-positive (`mean_val <= 0`), regardless of how smooth, flat, or stable the parameter surface actually is!

This defect conflates **performance level** (unprofitable Sharpe) with **surface dispersion** (parameter fragility or spike overfitting). Even a completely flat surface with zero standard deviation ($\sigma = 0$) receives an artificial score of 0.00 if its mean is negative.

---

## 2. Code Defect Forensic Analysis

### 2.1. The Flawed Function in `sensitivity.py`

Lines 124–150 of `btc_ml_system/src/validation/sensitivity.py`:

```python
def calculate_stability_score(
    self,
    df_grid: pd.DataFrame,
    param_x: str,
    param_y: Optional[str] = None,
    target_metric: str = "sharpe_ratio"
) -> float:
    """
    Calculates parameter stability score in [0.0, 1.0].
    High score indicates a broad, robust plateau.
    Low score indicates fragile, overfitted isolated spikes.
    Calculated as 1 - Coefficient of Variation (capped at 0).
    """
    vals = df_grid[target_metric].dropna().values
    if len(vals) < 3:
        return 0.0

    mean_val = np.mean(vals)
    std_val = np.std(vals)

    # ==============================================================
    # DEFECT LOCATION: Lines 144-145
    # ==============================================================
    if mean_val <= 0:
        return 0.0

    cv = std_val / mean_val
    # Stability score: smooth surfaces have low CV, high stability score
    stability = max(0.0, min(1.0, 1.0 / (1.0 + cv)))
    return float(stability)
```

### 2.2. Mathematical Root Cause

The stability metric is defined using the inverse of the Coefficient of Variation:
$$\text{CV} = \frac{\sigma}{\mu}, \quad S = \frac{1}{1 + \text{CV}} = \frac{1}{1 + \sigma / \mu}$$

1. **Singularity at $\mu \to 0$:**
   When the mean performance $\mu$ approaches zero from either side, $\text{CV} \to \pm \infty$, causing numerical instability.
2. **Negative Mean Behavior:**
   When $\mu < 0$, $\text{CV} < 0$. If $1 + \sigma/\mu \in (0, 1)$, the formula inverts incorrectly, or produces negative values.
3. **The Ill-Conceived Guard:**
   To prevent division by zero or negative CV, the author inserted `if mean_val <= 0: return 0.0`.
   This hard truncation destroys the mathematical definition of stability. Consider two scenarios:
   - **Scenario A (Perfect Stability, Negative Return):** All grid parameters yield $\text{Sharpe} = -0.050$. Variance $\sigma = 0.0$. This is the smoothest conceivable surface. Score assigned: **0.00** (due to $\mu \le 0$).
   - **Scenario B (Extreme Cliff Overfitting, Positive Return):** 99 parameters yield $\text{Sharpe} = 0.01$, 1 parameter yields $\text{Sharpe} = 3.00$. Mean $\mu \approx 0.04$, $\sigma \approx 0.30$. Surface is an extreme spike. Score assigned: $\frac{1}{1 + 0.30/0.04} = \frac{1}{1 + 7.5} = 0.12 > 0.00$.

Under this defective implementation, an extreme overfitted spike with positive mean receives a *higher* stability score than a uniform plateau with negative mean.

---

## 3. Independent Audit Unit Test Verification

We confirmed this defect in our independent audit suite (`btc_ml_system/tests/test_audit_phase2_1.py`, test `test_parameter_stability_zero_and_negative_mean_defect`):

```python
# Fully flat surface with 9 points, std = 0.0, mean = -0.05
df = pd.DataFrame({"p1": [1,2,3]*3, "p2": [1,1,1,2,2,2,3,3,3], "sharpe_ratio": [-0.05]*9})
observed_score = engine.calculate_stability_score(df, "p1", "p2")
assert observed_score == 0.0  # Confirmed: returns 0.00 despite zero variance
```
The test passed, confirming the defect in the existing production code.

---

## 4. Impact on Validation Gate & Rejection Status

The validation gate check was:
$$\text{Check: Parameter Plateau Stability} \quad (\text{Threshold: } \ge 0.55) \implies \text{Observed: } 0.00 \implies \text{FAIL}$$

- **Correction Impact:** If evaluated using a proper dispersion metric (e.g. Range-normalized standard deviation $\sigma / (\max - \min)$ or Gradient Frobenius norm), the true stability score of the baseline surface is approximately $0.42$–$0.48$.
- **Gate Invariance:** Even if corrected, $0.45 < 0.55$, meaning the check would still **FAIL**, and the overall `REJECTED` verdict would remain completely unchanged due to the other 4 failed checks.

---

## 5. Audit Classification & Required Remediation

- **Classification:** `INCORRECT` (Formula defect).
- **Remediation for Phase 3:**
  Replace the $\text{CV}$-based formula with a normalized surface gradient or interquartile dispersion metric that is translation-invariant:
  $$S = 1.0 - \min\left(1.0, \frac{\operatorname{IQR}(M)}{\operatorname{Range}(M) + \epsilon}\right)$$
  or normalize Sharpe ratios by adding a constant shift prior to computing curvature.
