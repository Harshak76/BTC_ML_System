# BTC-ML SYSTEM V2 — PHASE 3C.2.2 TARGETED AUDIT REPORT
# DEFLATED SHARPE RATIO STANDARD-ERROR UNIT RECONCILIATION

**Document ID:** `DSR_UNIT_CONSISTENCY_AUDIT.md`  
**Phase:** 3C.2.2 Targeted DSR Unit Reconciliation & Final Phase 3 Closure Audit  
**Repository:** `BTC_ML_System`  
**Working Branch:** `fix/phase-3c-2-research-integrity`  
**Base Commit:** `93e7121`  
**Date:** 2026-11-25  
**Auditor:** Independent Quantitative Research Auditor  
**Audit Mode:** Strictly Read-Only  

---

## 1. Executive Summary & Audit Query

In the Phase 3C.2.1 audit report (`DSR_TRIAL_ACCOUNTING_AUDIT.md`), the summary table for `RS_MOM_DONCHIAN_40_ADX25` presented:
- Observed Annualized Sharpe ($SR$): **$-1.1778$**
- Expected Maximum Annualized Sharpe ($SR^*$): **$+0.9580$**
- Reported Mertens Standard Error ($\sigma$): **$0.00762$**
- Reported Standardized Z-Score ($Z$): **$-2.9962$**
- Deflated Sharpe Ratio ($\text{DSR}$): **$0.0013687$ ($0.14\%$)**
- Upper-Tail $p$-value: **$0.99863$ ($99.86\%$)**

### The Apparent Dimensional Contradiction:
If an auditor calculates the Z-score directly from the annualized Sharpe values and the reported standard error:
$$\Delta SR = SR - SR^* = -1.177790 - (+0.957967) = -2.135757$$
$$\frac{\Delta SR}{\text{Reported SE}} = \frac{-2.135757}{0.007616} = \mathbf{-280.43} \neq \mathbf{-2.9962}$$
This apparent discrepancy of two orders of magnitude requires forensic mathematical investigation.

```
========================================================================================
                                 FORENSIC RESOLUTION:
  1. The reported standard error (0.007616) is the PERIODIC (HOURLY) standard error.
  2. The implied ANNUALIZED standard error is: 0.007616 * sqrt(8760) = 0.712818.
  3. The underlying Python engine calculated Z strictly using dimensionally consistent 
     PERIODIC quantities: Z = (-0.012584 - 0.010235) / 0.007616 = -2.9962.
  4. In annualized terms: Z = -2.135757 / 0.712818 = -2.9962 (IDENTICAL).
  5. The Z-score and DSR probability are 100% mathematically correct. The issue was 
     purely a reporting label omission: the table omitted the "Periodic" unit label.
========================================================================================
```

---

## 2. Source Code Forensic Inspection

The calculation is implemented in `btc_ml_system/src/validation/deflated_sharpe.py` within the `DeflatedSharpeEngine.calculate_dsr` method (lines 125–163):

```python
# Lines 125-128: De-annualize Sharpe to periodic (hourly) terms
periodic_sharpe = observed_sharpe / np.sqrt(annualization_factor) if annualization_factor > 1.0 else observed_sharpe
periodic_trials = [s / np.sqrt(annualization_factor) if annualization_factor > 1.0 else s for s in all_trial_sharpes]

# Line 130: Variance of periodic trials
var_trials = float(np.var(periodic_trials, ddof=1)) if n_trials > 1 else 0.0

# Lines 133-134: Expected max periodic and annualized Sharpe under extreme value theory
exp_max_periodic = self.expected_max_sharpe(n_trials, var_trials, mean_sharpe=0.0)
exp_max_annualized = exp_max_periodic * np.sqrt(annualization_factor)

# Lines 137-139: Mertens standard error computed ON PERIODIC SHARPE
se_periodic = self.compute_mertens_standard_error(
    periodic_sharpe, n_observations, calc_skew, calc_kurt
)

# Line 142: Standardized Z-score computed STRICTLY in periodic units
z = (periodic_sharpe - exp_max_periodic) / se_periodic
dsr = float(stats.norm.cdf(z))

# Line 161: Return dictionary mapping
return {
    "observed_annualized_sharpe": observed_sharpe,
    "observed_periodic_sharpe": periodic_sharpe,
    "deflated_sharpe_ratio": dsr,
    "probabilistic_sharpe_ratio": psr_zero,
    "expected_max_annualized_sharpe": exp_max_annualized,
    "expected_max_periodic_sharpe": exp_max_periodic,
    "mertens_standard_error": se_periodic,   # <--- RETURNED AS PERIODIC SE
    ...
}
```

### Forensic Proof of Code Execution:
1. `annualization_factor` $= 8,760.0$ hours/year ($\sqrt{8760} = 93.59487165438183$).
2. `observed_sharpe` $= -1.17778963$.
3. `periodic_sharpe` $= -1.17778963 / 93.59487165 = \mathbf{-0.01258391}$.
4. `exp_max_periodic` $= +0.95796695 / 93.59487165 = \mathbf{+0.01023525}$.
5. `se_periodic` is computed via Mertens formula on periodic Sharpe:
   $$\sigma_{\widehat{SR}_{\text{periodic}}} = \sqrt{\frac{1}{n-1} \left[ 1 - \gamma_3 \cdot SR_{\text{periodic}} + \frac{\gamma_4 - 1}{4} \cdot SR_{\text{periodic}}^2 \right]}$$
   With $n = 17,519$, $\gamma_3 = 0.402904$, $\gamma_4 = 287.0586$, $SR_{\text{periodic}} = -0.012584$:
   $$\sigma_{\widehat{SR}_{\text{periodic}}} = \mathbf{0.00761608}$$
6. **Z-Score Calculation:**
   $$Z = \frac{SR_{\text{periodic}} - E[\max SR_{\text{periodic}}]}{\sigma_{\widehat{SR}_{\text{periodic}}}} = \frac{-0.01258391 - (+0.01023525)}{0.00761608} = \frac{-0.02281916}{0.00761608} = \mathbf{-2.996180} \approx \mathbf{-2.9962}$$
7. **DSR Probability:**
   $$\Phi(-2.996180) = \mathbf{0.0013686936859108746} \approx \mathbf{0.0014} \quad (\mathbf{0.14\%})$$
8. **Complementary $p$-value:**
   $$1 - \Phi(-2.996180) = \mathbf{0.9986313063140891} \approx \mathbf{0.9986} \quad (\mathbf{99.86\%})$$

---

## 3. Dimensional Scaling Proof (Periodic vs. Annualized Equivalence)

The Z-score is a dimensionless test statistic. It is invariant to time scale if and only if numerator and denominator use identical annualization conventions:

### Mathematical Derivation:
Let $A$ be the annualization factor ($A = 8,760$).
$$SR_{\text{ann}} = SR_{\text{per}} \cdot \sqrt{A}$$
$$SR^*_{\text{ann}} = SR^*_{\text{per}} \cdot \sqrt{A}$$
$$\sigma_{\text{ann}} = \sigma_{\text{per}} \cdot \sqrt{A}$$

Substituting into the annualized Z-score formula:
$$Z_{\text{ann}} = \frac{SR_{\text{ann}} - SR^*_{\text{ann}}}{\sigma_{\text{ann}}} = \frac{\left(SR_{\text{per}} \cdot \sqrt{A}\right) - \left(SR^*_{\text{per}} \cdot \sqrt{A}\right)}{\sigma_{\text{per}} \cdot \sqrt{A}} = \frac{\sqrt{A} \cdot \left(SR_{\text{per}} - SR^*_{\text{per}}\right)}{\sqrt{A} \cdot \sigma_{\text{per}}} = \frac{SR_{\text{per}} - SR^*_{\text{per}}}{\sigma_{\text{per}}} = Z_{\text{per}}$$

The scale factor $\sqrt{A}$ cancels out identically in the numerator and denominator:

| Convention | Numerator ($\Delta SR$) | Denominator ($\sigma_{\widehat{SR}}$) | Ratio ($Z$-score) | DSR Probability ($\Phi(Z)$) |
| :--- | :--- | :--- | :--- | :--- |
| **Purely Periodic (Hourly)** | $-0.02281916$ | $0.00761608$ | $\mathbf{-2.9962}$ | $\mathbf{0.0013687}$ ($0.14\%$) |
| **Purely Annualized** | $-2.13575658$ | $0.71281804$ | $\mathbf{-2.9962}$ | $\mathbf{0.0013687}$ ($0.14\%$) |
| **Mixed (Erroneous Cross-Division)**| $-2.13575658$ (Annual) | $0.00761608$ (Periodic) | **$-280.43$** | **$0.0000000$** |

### Definitive Conclusion:
The calculation executed by `DeflatedSharpeEngine` is **100% mathematically correct and dimensionally pure**. The engine operates in the Purely Periodic convention (Row 1).  
The apparent error only occurs if a human reader divides the annualized numerator by the periodic denominator (Row 3).

---

## 4. Parameter and Dimension Inventory Across All Three Candidates

The table below provides the complete, dimensionally segregated parameter inventory for all three candidates:

| Quantity | Dimensional Unit | `RS_MOM_DONCHIAN_40_CONTROL` | `RS_MOM_DONCHIAN_40_ADX25` | `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE` |
| :--- | :--- | :--- | :--- | :--- |
| **Return Frequency** | Time resolution | Hourly (1H) | Hourly (1H) | Hourly (1H) |
| **Sample Size ($n$)** | Number of observations | $17,519$ | $17,519$ | $17,519$ |
| **Annualization Factor ($A$)** | Periods per year | $8,760$ | $8,760$ | $8,760$ |
| **$\sqrt{A}$ Scale Factor** | Ratio | $93.59487$ | $93.59487$ | $93.59487$ |
| **Observed Periodic Sharpe** | Periodic unit ($h^{-0.5}$) | **$-0.022059$** | **$-0.012584$** | **$-0.023031$** |
| **Observed Annualized Sharpe**| Annualized unit ($y^{-0.5}$) | **$-2.064562$** | **$-1.177790$** | **$-2.155574$** |
| **Expected Max Periodic Sharpe**| Periodic unit ($h^{-0.5}$) | **$+0.010235$** | **$+0.010235$** | **$+0.010235$** |
| **Expected Max Annualized Sharpe**| Annualized unit ($y^{-0.5}$) | **$+0.957967$** | **$+0.957967$** | **$+0.957967$** |
| **Return Skewness ($\gamma_3$)** | Standardized 3rd moment | $0.953313$ | $0.402904$ | $1.046946$ |
| **Return Kurtosis ($\gamma_4$)** | Pearson uncentered 4th | $129.6795$ | $287.0586$ | $143.6601$ |
| **Periodic Mertens SE ($\sigma_{\text{per}}$)** | Periodic unit ($h^{-0.5}$) | **$0.007559$** | **$0.007616$** | **$0.007889$** |
| **Annualized Mertens SE ($\sigma_{\text{ann}}$)**| Annualized unit ($y^{-0.5}$) | **$0.707483$** | **$0.712818$** | **$0.738370$** |
| **Standardized Z-Score ($Z_{\text{DSR}}$)** | Dimensionless ($z$) | **$-4.2721$** | **$-2.9962$** | **$-4.2166$** |
| **Deflated Sharpe Ratio ($\Phi(Z)$)** | Probability in $[0, 1]$ | **$9.68 \times 10^{-6}$** | **$0.0013687$** | **$1.24 \times 10^{-5}$** |
| **DSR Percentage Format** | Percentage | **$0.0010\%$** | **$0.14\%$** ($0.1369\%$) | **$0.0012\%$** |
| **Complementary $p$-value** | Upper-tail probability | **$0.99999$** | **$0.99863$** | **$0.99999$** |

---

## 5. Auditor Recommendations for Reporting Governance

1. **Unit Label Correction:** In all future research templates and documentation, the table row for Mertens standard error must be explicitly labeled as:
   - `Mertens Standard Error (Periodic): 0.00762`
   - `Mertens Standard Error (Annualized): 0.71282`
2. **Explicit Formula Display:** Documentation must display both the periodic and annualized Z-score ratios side-by-side to prevent readers from mistakenly performing cross-dimensional division.
