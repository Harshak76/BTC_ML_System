# PHASE 2.3 — PARAMETER STABILITY INDEPENDENT AUDIT REVIEW

**Audit Date:** November 19, 2026  
**Auditor:** Quantitative Risk Engineer & Senior Algorithmic Verification Engine  
**Repository:** `BTC_ML_System`  
**Base Commit Audited:** `82f061b`  
**Audited Module:** `btc_ml_system/src/validation/sensitivity.py`  
**Verification Script / Test:** `btc_ml_system/tests/test_validation_corrections_phase2_2.py`  
**Status:** `VERIFIED WITH LIMITATIONS`

---

## 1. Scope & Objective

This report independently verifies the mathematical correctness, numerical stability, unit invariance, and boundary behaviors of the parameter stability scoring implementation in `src/validation/sensitivity.py` following the Phase 2.2 remediation.

The audit evaluates:
1. Independent reproduction of stability calculations across canonical surface topologies.
2. The role of dispersion estimation: sample standard deviation ($\sigma$) vs. normalized interquartile range ($\text{IQR}/1.349$).
3. Normalization and transformation formulas for dispersion, plateau, and smoothness.
4. Scale and unit invariance (percentages vs. decimals, return vs. Sharpe ratio).
5. Separation of parameter stability from strategy profitability.
6. Mathematical interpretation of a $1.000$ stability score on a uniformly negative parameter surface.

---

## 2. Independent Code & Formula Audit

### 2.1. Inspected Implementation (`sensitivity.py`, lines 124–228)
```python
def calculate_stability_score(
    self,
    df_grid: pd.DataFrame,
    param_x: str,
    param_y: Optional[str] = None,
    target_metric: str = "sharpe_ratio"
) -> float:
```
The implementation evaluates three components:
1. **Flat Surface Guard (lines 177–178):**
   $$\text{Range}(V) = \max(V) - \min(V) < 10^{-12} \implies S = 1.0$$
2. **Reference Scale Assignment (lines 181–186):**
   $$\sigma_0 = \begin{cases} 
   5.0 & \text{if } \text{"return" in } \text{target\_metric.lower()} \\
   0.25 & \text{if } \text{target\_metric} \in (\text{"sharpe\_ratio"}, \text{"sortino\_ratio"}, \text{"profit\_factor"}) \\
   0.25 & \text{otherwise}
   \end{cases}$$
3. **Normalized Dispersion ($S_{\text{disp}}$, lines 189–190):**
   $$S_{\text{disp}} = \frac{1.0}{1.0 + \frac{\text{std}(V)}{\sigma_0}}$$
4. **Plateau Prominence & Penalty ($S_{\text{plateau}}$, lines 193–198):**
   $$\text{prominence} = \frac{\max(V) - Q_{75}(V)}{\text{Range}(V)}$$
   $$\text{scale\_weight} = \min\left(1.0, \frac{\text{Range}(V)}{\text{Range}(V) + \sigma_0}\right)$$
   $$S_{\text{plateau}} = \max(0.0, 1.0 - \text{scale\_weight} \cdot \text{prominence})$$
5. **Local Roughness / Smoothness ($S_{\text{smooth}}$, lines 201–224):**
   $$\text{roughness} = \text{scale\_weight} \cdot \min\left(1.0, \frac{\overline{|\Delta G|}}{\text{Range}(V) + 10^{-12}}\right)$$
   $$S_{\text{smooth}} = 1.0 - 0.5 \cdot \text{roughness}$$
6. **Composite Multiplicative Score (line 227):**
   $$S = \text{clip}\left(S_{\text{disp}} \cdot S_{\text{plateau}} \cdot S_{\text{smooth}}, 0.0, 1.0\right)$$

---

## 3. Findings & Mathematical Analysis

### 3.1. Examination of Dispersion: $\sigma$ vs. $\min(\sigma, \text{IQR}/1.349)$
- **Reported Claim in Phase 2.2 Documentation:** The documentation report `docs/audit/phase_2_2/PARAMETER_STABILITY_CORRECTION.md` claimed the code used:
  $$\sigma_{\text{robust}} = \min\left(\text{std}(V), \frac{\text{IQR}(V)}{1.349}\right)$$
- **Independently Verified Fact in Source Code:** Line 189 of `sensitivity.py` executes:
  `std_val = float(np.std(vals))`
  The code directly uses the sample standard deviation $\sigma$ and **does not** compute $\min(\sigma, \text{IQR}/1.349)$.
- **Mathematical Evaluation:**
  If an implementation evaluates $\min(\sigma, \text{IQR}/1.349)$, selecting the *smaller* dispersion estimate systematically understates variability in the presence of heavy tails or outlier spikes. For an isolated spike (24 values at $0.1$, 1 value at $3.0$), $\text{IQR} = 0.0$, while $\sigma = 0.569$. Taking the minimum would set dispersion to $0.0$, yielding $S_{\text{disp}} = 1.0$ and completely masking the outlier fragility!
  **Conclusion:** The actual source code's decision to use `std_val` is mathematically superior and safer than the formula claimed in the Phase 2.2 markdown documentation. However, this constitutes an unresolved documentation discrepancy that must be recognized.

### 3.2. Reproduction of Canonical Topologies
We executed an independent Python test matrix against `sensitivity.py`:

| Canonical Topology | Grid Configuration | Expected Behavior | Independently Reproduced Score | Assessment |
| :--- | :--- | :--- | :--- | :--- |
| **Flat Positive** | $3 \times 3$ grid, all values $= +1.50$ | Maximal stability ($1.0$) | **1.0000** | VERIFIED |
| **Flat Negative** | $3 \times 3$ grid, all values $= -0.80$ | Maximal stability ($1.0$) | **1.0000** | VERIFIED |
| **Near-Zero Mean** | $3 \times 3$ grid, $\mu = 0.0013, \sigma = 0.0005$ | High stability ($\ge 0.95$) | **0.9960** | VERIFIED |
| **Noisy Surface** | $5 \times 5$ Gaussian noise $\mathcal{N}(0.5, 1.0)$ | Low stability ($< 0.25$) | **0.1306** | VERIFIED |
| **Multimodal Surface**| 12 cells at $-1.0$, 13 cells at $+1.0$ | Low stability ($< 0.30$) | **0.1868** | VERIFIED |
| **Outlier-Heavy** | 24 cells at $0.5$, 1 cell at $-5.0$ | Low stability ($< 0.25$) | **0.1838** | VERIFIED |
| **Isolated Spike** | 24 cells at $0.1$, 1 cell at $3.0$ | Severe penalty ($< 0.10$) | **0.0237** | VERIFIED |

All calculations reproduced with 100% numerical consistency. The Phase 2.1 defect (returning 0.0 for any negative mean) is fully eradicated.

### 3.3. Unit and Scale Invariance (Limitation Identified)
We evaluated whether stability scoring is invariant to unit definitions:
- **Return in Percentage Points ($10.0 = 10\%$):**
  Inputs: $[10.0, 12.0, 11.0, 10.5, 11.5 \dots]$, target metric `"total_return"`.
  $\sigma = 0.707$, $\sigma_0 = 5.0 \implies S = \mathbf{0.7556}$.
- **Return in Decimals ($0.10 = 10\%$):**
  Inputs: $[0.10, 0.12, 0.11, 0.105, 0.115 \dots]$, target metric `"total_return"`.
  $\sigma = 0.00707$, $\sigma_0 = 5.0 \implies S = \mathbf{0.9966}$.

**Finding:** The stability engine is **not scale-invariant across unit representations**. Because $\sigma_0 = 5.0$ is hardcoded for return metrics, the engine assumes percentage points ($10.0$ for $10\%$). Passing decimal returns compresses dispersion by $100\times$, artificially inflating the stability score from $0.7556$ to $0.9966$.
**Constraint for Phase 3:** Strategy return metrics passed to `calculate_stability_score` must strictly be expressed in percentage points ($0$–$100$), never decimal fractions.

### 3.4. Separation of Stability from Profitability
A flat negative surface where all parameters yield a Sharpe ratio of $-0.80$ produces an observed score of **1.0000**.
- **What this score means:** It indicates that the response surface is 100% invariant to parameter perturbation. Changing parameters induces zero parameter fragility, zero cliff risk, and zero needle-spike overfitting. The system's behavior is completely predictable across the parameter space.
- **What this score does NOT mean:** It does **NOT** indicate that the strategy is profitable, viable, or ready for production. A strategy that reliably loses money everywhere is structurally stable, but commercially catastrophic.
- **Verification:** In `tests/test_validation_corrections_phase2_2.py::test_parameter_stability_separated_from_profitability`, a flat losing surface received $S = 1.0000$, passing the `Parameter Plateau Stability` gate check, but was decisively marked `REJECTED` by `ValidationGate` due to failing the return and cost stress checks. Profitability separation is verified.

---

## 4. Audit Conclusion & Recommendations

| Item | Finding | Status |
| :--- | :--- | :--- |
| **Negative Mean Defect** | Fixed; no division by mean or truncation at $\mu \le 0$ | PASS |
| **Plateau vs Spike Penalty** | Verified; isolated spikes penalized down to $0.0237$ | PASS |
| **Smoothness Metric** | Discrete gradient differences penalize noisy surfaces down to $0.1306$ | PASS |
| **Profitability Separation** | Confirmed; gate rejects unprofitable strategies regardless of stability | PASS |
| **Unit Invariance** | Not invariant between % and decimal returns ($\sigma_0 = 5.0$) | LIMITATION |
| **Code vs Doc Discrepancy**| Code uses `std_val`; doc claimed $\min(\sigma, \text{IQR}/1.349)$ | DISCLOSED |

**Verdict:** `VERIFIED WITH LIMITATIONS`. The parameter stability engine is mathematically sound for Sharpe and percentage return evaluations and is safe for Phase 3 research use, provided return metrics are consistently scaled in percentage points.
