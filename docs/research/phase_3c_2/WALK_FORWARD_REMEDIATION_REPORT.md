# BTC-ML SYSTEM V2 — PHASE 3C.2 RESEARCH REPORT
# WALK-FORWARD REMEDIATION REPORT

**Document ID:** `WALK_FORWARD_REMEDIATION_REPORT.md`  
**Phase:** 3C.2 Research Integrity Remediation & Controlled Revalidation  
**Repository:** `BTC_ML_System`  
**Branch:** `fix/phase-3c-2-research-integrity`  
**Base Commit:** `93e7121`  
**Remediation Targets:** Defect D-02 (50% Overlapping OOS Folds), Defect D-03 (Cold Indicator Warm-Up Dead-Zone), Defect D-04 (Horizon Truncation Past Dec 2025)  
**Date:** 2026-11-25

---

## 1. Executive Summary

In Phase 3C.1, independent audit identified three critical methodological defects in the walk-forward validation framework:
1. **Defect D-02:** Out-of-sample (OOS) testing windows stepped forward by $50\%$ of the window length, creating a $50\%$ (~71-day) shared data overlap between adjacent OOS folds, violating the statistical independence assumption.
2. **Defect D-03:** OOS partitions were sliced without historical lookback padding, causing the first 40 bars of each OOS test window to evaluate to `NaN` indicators, creating an artificial 40-bar signal dead-zone.
3. **Defect D-04:** Walk-forward evaluation stopped at `2025-12-12`, omitting the final 9+ months of the authentic dataset through `2026-09-22`.

In Phase 3C.2, the walk-forward evaluation methodology was completely overhauled:
- **Primary Architecture:** 4 strictly disjoint, non-overlapping chronological partitions covering the entire timeline from `2024-09-22` through `2026-09-22` with **0.0% data overlap**.
- **Lookback Warm-Up Buffer:** Each OOS testing partition includes a 100-bar historical warm-up buffer prior to test start, eliminating `NaN` dead-zones while strictly excluding pre-OOS trades from metrics.
- **Secondary Robustness Analysis:** The legacy 5-fold overlapping scheme was re-evaluated and explicitly labeled as **`SECONDARY_ROBUSTNESS_DEPENDENT_OVERLAPPING_FOLDS`** to quantify cross-window dependency.
- **Conclusion:** Both primary disjoint folds and secondary overlapping folds demonstrate persistent negative edge across all three candidates. The research rejection under Gate 9 is definitively confirmed.

---

## 2. Partition Architecture Comparison

### A. Defective Phase 3C Configuration vs. Remediated Phase 3C.2 Configuration

| Dimension | Phase 3C (Defective) | Phase 3C.2 (Remediated Primary) | Phase 3C.2 (Secondary Robustness) |
| :--- | :--- | :--- | :--- |
| **Partition Overlap** | **50.0% Shared Data** (Defect D-02) | **0.0% (Strictly Disjoint)** | 50.0% (Explicitly Dependent) |
| **Indicator Padding** | **0 bars (40-bar NaN Dead-Zone)** (Defect D-03) | **100-bar Warm-Up Buffer** | 0 bars (Legacy Reproduction) |
| **Timeline Coverage** | Truncated at `2025-12-12` (Defect D-04) | **Full Span to `2026-09-22`** | Full Span to `2026-09-22` |
| **Number of Folds** | 5 overlapping folds | **4 disjoint folds** | 5 overlapping folds |
| **Independence Status** | Falsely reported as independent | **Statistically Disjoint & Independent** | Disclosed as Dependent |

---

## 3. Primary Non-Overlapping Walk-Forward Partitions (Disjoint)

The 17,520 hours of authentic 1H market data across all 7 assets was partitioned into an initial 180-day training buffer followed by 4 contiguous, non-overlapping out-of-sample testing windows of approximately 137 days each:

| Fold # | In-Sample Training Window | Out-of-Sample Testing Window | OOS Duration | Overlap with Prior Fold | Warm-Up Buffer |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Fold 1** | 2024-09-22 to 2025-03-24 | **2025-03-24 to 2025-08-08** | 137 days | **0.0%** | 100 bars |
| **Fold 2** | 2025-02-06 to 2025-08-08 | **2025-08-08 to 2025-12-22** | 136 days | **0.0%** | 100 bars |
| **Fold 3** | 2025-06-23 to 2025-12-22 | **2025-12-22 to 2026-05-08** | 137 days | **0.0%** | 100 bars |
| **Fold 4** | 2025-11-07 to 2026-05-08 | **2026-05-08 to 2026-09-22** | 137 days | **0.0%** | 100 bars |

---

## 4. Empirical Primary Walk-Forward Results (Non-Overlapping)

### Candidate 1: `RS_MOM_DONCHIAN_40_CONTROL`
| Fold # | Train Window | OOS Window | IS Return | OOS Return | OOS Trades | OOS Win Rate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fold 1** | 2024-09-22 to 2025-03-24 | 2025-03-24 to 2025-08-08 | $-7.30\%$ | **$-5.42\%$** | 193 | $38.3\%$ | FAILED |
| **Fold 2** | 2025-02-06 to 2025-08-08 | 2025-08-08 to 2025-12-22 | $-7.25\%$ | **$-4.14\%$** | 166 | $39.2\%$ | FAILED |
| **Fold 3** | 2025-06-23 to 2025-12-22 | 2025-12-22 to 2026-05-08 | $-6.08\%$ | **$-0.52\%$** | 162 | $43.8\%$ | FAILED |
| **Fold 4** | 2025-11-07 to 2026-05-08 | 2026-05-08 to 2026-09-22 | $-1.52\%$ | **$+0.73\%$** | 170 | $45.9\%$ | MARGINAL |
| **Aggregated OOS** | **Full 18-Month OOS Span** | **Contiguous Stitched** | **N/A** | **$-9.35\%$** | **691** | **$41.7\%$** | **REJECTED** |

---

### Candidate 2: `RS_MOM_DONCHIAN_40_ADX25`
| Fold # | Train Window | OOS Window | IS Return | OOS Return | OOS Trades | OOS Win Rate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fold 1** | 2024-09-22 to 2025-03-24 | 2025-03-24 to 2025-08-08 | $-3.11\%$ | **$-2.49\%$** | 63 | $36.5\%$ | FAILED |
| **Fold 2** | 2025-02-06 to 2025-08-08 | 2025-08-08 to 2025-12-22 | $-2.12\%$ | **$-1.99\%$** | 72 | $37.5\%$ | FAILED |
| **Fold 3** | 2025-06-23 to 2025-12-22 | 2025-12-22 to 2026-05-08 | $-2.51\%$ | **$+0.49\%$** | 84 | $48.8\%$ | MARGINAL |
| **Fold 4** | 2025-11-07 to 2026-05-08 | 2026-05-08 to 2026-09-22 | $+0.30\%$ | **$+0.81\%$** | 74 | $51.4\%$ | MARGINAL |
| **Aggregated OOS** | **Full 18-Month OOS Span** | **Contiguous Stitched** | **N/A** | **$-3.18\%$** | **293** | **$44.0\%$** | **REJECTED** |

---

### Candidate 3: `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE`
| Fold # | Train Window | OOS Window | IS Return | OOS Return | OOS Trades | OOS Win Rate | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fold 1** | 2024-09-22 to 2025-03-24 | 2025-03-24 to 2025-08-08 | $-6.09\%$ | **$-4.15\%$** | 173 | $37.0\%$ | FAILED |
| **Fold 2** | 2025-02-06 to 2025-08-08 | 2025-08-08 to 2025-12-22 | $-5.82\%$ | **$-3.07\%$** | 144 | $38.9\%$ | FAILED |
| **Fold 3** | 2025-06-23 to 2025-12-22 | 2025-12-22 to 2026-05-08 | $-4.75\%$ | **$-0.61\%$** | 148 | $42.6\%$ | FAILED |
| **Fold 4** | 2025-11-07 to 2026-05-08 | 2026-05-08 to 2026-09-22 | $-0.55\%$ | **$-1.93\%$** | 142 | $39.4\%$ | FAILED |
| **Aggregated OOS** | **Full 18-Month OOS Span** | **Contiguous Stitched** | **N/A** | **$-9.76\%$** | **607** | **$39.4\%$** | **REJECTED** |

---

## 5. Secondary Overlapping Walk-Forward Results (Dependent Observations)

> **MANDATORY DISCLOSURE: DEPENDENT OBSERVATIONS**  
> The 5 partitions below step forward by $50\%$ of the fold size. Adjacent partitions share $\approx 50\%$ identical market data. These observations are statistically dependent and must NOT be aggregated into an independent metric.

| Candidate Strategy | Fold 1 OOS Ret | Fold 2 OOS Ret | Fold 3 OOS Ret | Fold 4 OOS Ret | Fold 5 OOS Ret | Mean OOS Sharpe |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Control** (`DONCHIAN_40`) | $-3.44\%$ | $-4.82\%$ | $-4.72\%$ | $-3.17\%$ | $-4.28\%$ | **$-3.3619$** |
| **ADX25 Filter** | $-2.85\%$ | $-1.75\%$ | $-0.72\%$ | $-2.05\%$ | $-1.67\%$ | **$-2.4668$** |
| **4H EMA Slope Filter** | $-2.36\%$ | $-3.78\%$ | $-3.86\%$ | $-2.65\%$ | $-2.59\%$ | **$-2.6964$** |

In the secondary overlapping framework, **15 out of 15 candidate-folds generated strictly negative net returns and negative Sharpe ratios**, corroborating the primary disjoint findings.

---

## 6. Key Findings & Diagnostic Observations

1. **Stitched Disjoint OOS Returns are Strictly Negative:**  
   When all 4 disjoint OOS windows are stitched together with zero double-counting:
   - Control cumulative OOS PnL is **$-\$9,350.00$ ($-9.35\%$)**.
   - ADX25 cumulative OOS PnL is **$-\$3,180.00$ ($-3.18\%$)**.
   - 4H EMA cumulative OOS PnL is **$-\$9,760.00$ ($-9.76\%$)**.
2. **Warm-Up Padding Restores Boundary Trades:**  
   With the 100-bar lookback padding restored, 691 disjoint OOS trades were captured across the 4 folds, compared to artificially suppressed trade counts in unpadded slicing.
3. **Late-Cycle Equity Drift in Folds 3 and 4:**  
   In Fold 4 (May 2026 to Sep 2026), tech equities experienced a strong upward drift that lifted Control ($+0.73\%$) and ADX25 ($+0.81\%$) into slight positive territory, while 4H EMA remained negative ($-1.93\%$). However, this marginal late-stage recovery was insufficient to offset the deep drawdowns of Folds 1 and 2.
4. **Gate 9 Decision:** Across all 3 candidates, aggregated out-of-sample return remains negative, failing Gate 9 ($\text{WFE} > 0.50$ and $\text{OOS Ret} > 0.00\%$).

---

## 7. Audit Verdict

Defects D-02, D-03, and D-04 are **FULLY REMEDIATED AND INDEPENDENTLY RESOLVED**:
- Strictly non-overlapping primary partitions established.
- 100-bar warm-up lookback buffers verified.
- Complete 24-month horizon evaluated.
- **Negative research conclusions confirmed without exception.**
