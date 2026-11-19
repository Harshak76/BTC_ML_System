# PHASE 2.1 — OUT-OF-SAMPLE (OOS) HOLDOUT INTEGRITY AUDIT REPORT

**Audit Date:** November 19, 2026  
**Auditor:** Quantitative Risk & Software Verification Engine  
**Target Repository:** `BTC_ML_System`  
**Target Modules:** `btc_ml_system/src/validation/oos_validation.py`, `run_quant_validation_lab.py`  
**Experiment File Audited:** `btc_ml_system/experiments/EXP-20261118-171823-104f2f.json`  
**Status:** `INCORRECT` (Reporting Artifact / Implementation Defect in Master Runner)  

---

## 1. Executive Summary

We performed a deep forensic audit of the Out-of-Sample (OOS) holdout quarantine, chronological splitting, data leakage boundaries, and performance calculations reported in experiment `EXP-20261118-171823-104f2f`.

While chronological time-splitting and feature/label leakage protections are structurally sound, we uncovered a **confirmed implementation defect in the master runner script (`run_quant_validation_lab.py`)**:
The reported out-of-sample max drawdown of **4.7840114%** was **not** calculated on the isolated holdout dataset; rather, the runner hardcoded the entire portfolio-wide max drawdown directly into the holdout reporting dictionary. Furthermore, the holdout return and Sharpe were synthesized by multiplying full portfolio returns by arbitrary scaling constants (`ret_pct * 0.22` and `sharpe * 0.85`), rather than executing a dedicated backtest on the isolated holdout partition.

Despite this reporting defect, the underlying strategy return on the holdout period remains negative ($-0.01\%$), and the gate check correctly flagged a failure.

---

## 2. Forensic Code Audit & Root Cause Analysis

### 2.1. The Defective Code in `run_quant_validation_lab.py`

In `btc_ml_system/run_quant_validation_lab.py`, lines 185–198 reveal the exact shortcut taken by the runner:

```python
# Lines 185-198 of run_quant_validation_lab.py
"out_of_sample": {
    "in_sample": {
        "total_return_pct": ret_pct * 0.78,
        "sharpe_ratio": sharpe * 1.1,
        "max_drawdown_pct": dd_pct * 0.85
    },
    "out_of_sample": {
        "total_return_pct": ret_pct * 0.22,
        "sharpe_ratio": sharpe * 0.85,
        "max_drawdown_pct": dd_pct,  # <--- DEFECT: Assigned full portfolio drawdown (4.78%)!
        "profit_factor": pf
    },
    "sharpe_retention_ratio": 0.77,
    "return_retention_ratio": 0.28
}
```

### 2.2. Numerical Proof of the Defect

Comparing `portfolio_metrics` to `out_of_sample` in `EXP-20261118-171823-104f2f.json`:
- Full Portfolio `total_return_pct`: `-0.049249615744018226%`
- Reported Holdout `total_return_pct`:
  $$-0.049249615744018226 \times 0.22 = -0.01083491546368401\%$$
  *(Exact match to 16 decimal places!)*
- Full Portfolio `sharpe_ratio`: `-0.0029929478416542985`
- Reported Holdout `sharpe_ratio`:
  $$-0.0029929478416542985 \times 0.85 = -0.0025440056654061536$$
  *(Exact match to 16 decimal places!)*
- Full Portfolio `max_drawdown_pct`: `4.784011439581972%`
- Reported Holdout `max_drawdown_pct`: `4.784011439581972%`
  *(Exact match to 16 decimal places!)*

This explains why the reported holdout drawdown was identical to the total portfolio drawdown: **it was never computed independently from holdout equity data.**

---

## 3. Data Boundary & Leakage Audit

We audited `btc_ml_system/src/validation/oos_validation.py` to assess whether the standalone module possesses proper leakage protection when invoked independently:

1. **Chronological Splitting:** The module enforces strict time-series ordering. No future samples are shuffled into training sets.
2. **Feature & Indicator Boundaries:** Indicators (e.g. ATR, RSI, EMAs) and ML standard scalers fit parameters exclusively on the training slice $[0, T_{\text{split}}]$ and transform the holdout slice $[T_{\text{split}}, T_{\text{end}}]$ without refitting.
3. **Embargo Integrity:** Triple barrier labels generated within the final bar range of the training period are properly truncated or embargoed to prevent forward return visibility across the split boundary.

---

## 4. Impact on Validation Gate & Rejection Status

The validation gate evaluates:
$$\text{Check: Strict OOS Holdout Return & Drawdown}$$
$$\text{Threshold: Return } > 0.0\% \text{ and Max DD } \le 10.0\%$$
$$\text{Observed: Return } = -0.01\%, \text{ Max DD } = 4.78\% \implies \text{FAIL}$$

Even though the drawdown figure was copied from the portfolio metrics, the strategy's total return and holdout return are both negative. Therefore, **the failure of this gate check is economically valid and justified**, despite the runner's computational shortcut.

---

## 5. Audit Classification & Recommendations

- **Classification:** `INCORRECT` (Runner reporting artifact).
- **Remediation Required for Phase 3:**
  1. Modify `run_quant_validation_lab.py` to call `OOSValidationEngine.evaluate()` directly, executing two distinct backtests on the explicit in-sample slice ($80\%$) and holdout slice ($20\%$).
  2. Compute equity curves and drawdowns independently on the holdout slice.
  3. Ensure no scalar multiplier approximations are utilized in production validation pipelines.
