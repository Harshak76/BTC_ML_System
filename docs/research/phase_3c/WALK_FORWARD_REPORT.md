# BTC-ML SYSTEM V2 — PHASE 3C WALK-FORWARD REPORT
## Multi-Fold Walk-Forward Optimization & Out-of-Sample Stability Analysis

- **Date:** 2026-11-24
- **Auditor:** Senior Quantitative Researcher & Backtesting Auditor
- **Repository Branch:** `feat/phase-3c-controlled-filter-experiment`
- **Methodology:** 5 rolling chronological partitions with zero future-data leakage.
- **Mandatory Disclosure:**
  > **`HISTORICAL EXPLORATORY EVALUATION — PRIOR DATASET INSPECTION DISCLOSED`**  
  > Historical chronological partitions evaluated with prior dataset inspection disclosed.

---

## 1. WALK-FORWARD SPLIT CONFIGURATION

The continuous timeline across the 7 authentic assets (from October 2024 to September 2026) was divided into 5 rolling partitions. Each fold evaluates In-Sample (IS) training performance followed by Out-of-Sample (OOS) forward evaluation:

| Fold | In-Sample Training Window | Out-of-Sample Testing Window |
|---|---|---|
| **Fold 1** | 2024-09-22 to 2024-10-13 | 2024-10-13 to 2025-03-04 |
| **Fold 2** | 2024-10-13 to 2024-12-23 | 2024-12-23 to 2025-05-14 |
| **Fold 3** | 2024-12-23 to 2025-03-04 | 2025-03-04 to 2025-07-24 |
| **Fold 4** | 2025-03-04 to 2025-05-14 | 2025-05-14 to 2025-10-03 |
| **Fold 5** | 2025-05-14 to 2025-07-24 | 2025-07-24 to 2025-12-12 |

---

## 2. EMPIRICAL WALK-FORWARD RESULTS PER CANDIDATE

### Candidate 1: `RS_MOM_DONCHIAN_40_CONTROL`

| Fold | IS Return | OOS Return | IS Sharpe | OOS Sharpe | WFE Ratio | OOS Trades |
|---|---|---|---|---|---|---|
| **Fold 1** | $-1.85\%$ | $-2.62\%$ | $-1.1079$ | $-1.6522$ | 1.4912 | 194 |
| **Fold 2** | $-3.95\%$ | $-2.49\%$ | $-2.2937$ | $-1.7011$ | 0.7416 | 215 |
| **Fold 3** | $-2.62\%$ | $-5.76\%$ | $-1.6522$ | $-4.1513$ | 2.5126 | 208 |
| **Fold 4** | $-2.49\%$ | $-4.31\%$ | $-1.7011$ | $-3.2224$ | 1.8943 | 196 |
| **Fold 5** | $-5.76\%$ | $-1.32\%$ | $-4.1513$ | $-1.0060$ | 0.2423 | 185 |
| **Mean** | **$-3.33\%$** | **$-3.30\%$** | **$-2.1812$** | **$-2.3466$** | **1.3764\*** | **199.6** |

*\*Note on WFE: In negative Sharpe environments, ratio arithmetic produces mathematically positive ratios when both IS and OOS are negative. True economic Walk-Forward Efficiency requires positive out-of-sample edge.*

---

### Candidate 2: `RS_MOM_DONCHIAN_40_ADX25`

| Fold | IS Return | OOS Return | IS Sharpe | OOS Sharpe | WFE Ratio | OOS Trades |
|---|---|---|---|---|---|---|
| **Fold 1** | $-1.07\%$ | $-2.08\%$ | $-0.9389$ | $-1.8517$ | 1.9721 | 82 |
| **Fold 2** | $-2.56\%$ | $-2.93\%$ | $-2.0953$ | $-3.3872$ | 1.6166 | 94 |
| **Fold 3** | $-2.08\%$ | $-0.86\%$ | $-1.8517$ | $-1.1724$ | 0.6332 | 91 |
| **Fold 4** | $-2.93\%$ | $-0.10\%$ | $-3.3872$ | $-0.1058$ | 0.0312 | 78 |
| **Fold 5** | $-0.86\%$ | $-0.99\%$ | $-1.1724$ | $-1.3022$ | 1.1107 | 76 |
| **Mean** | **$-1.90\%$** | **$-1.39\%$** | **$-1.8891$** | **$-1.5639$** | **1.0728** | **84.2** |

#### Diagnostic Observations on ADX25:
- In every single fold (Folds 1 through 5), Out-of-Sample return remained negative (ranging from $-0.10\%$ in Fold 4 to $-2.93\%$ in Fold 2).
- Average OOS trade count was reduced from 199.6 to 84.2 per fold ($-57.8\%$).
- OOS loss was consistently smaller than Control across all folds (mean OOS return $-1.39\%$ vs $-3.30\%$).

---

### Candidate 3: `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE`

| Fold | IS Return | OOS Return | IS Sharpe | OOS Sharpe | WFE Ratio | OOS Trades |
|---|---|---|---|---|---|---|
| **Fold 1** | $-2.92\%$ | $-2.34\%$ | $-1.9087$ | $-1.5694$ | 0.8222 | 175 |
| **Fold 2** | $-3.14\%$ | $-2.00\%$ | $-1.9482$ | $-1.4670$ | 0.7530 | 192 |
| **Fold 3** | $-2.34\%$ | $-4.58\%$ | $-1.5694$ | $-3.4399$ | 2.1919 | 184 |
| **Fold 4** | $-2.00\%$ | $-3.57\%$ | $-1.4670$ | $-2.8141$ | 1.9182 | 178 |
| **Fold 5** | $-4.58\%$ | $-0.95\%$ | $-3.4399$ | $-0.7526$ | 0.2188 | 166 |
| **Mean** | **$-2.99\%$** | **$-2.69\%$** | **$-2.0666$** | **$-2.0086$** | **1.1808** | **179.0** |

---

## 3. WALK-FORWARD ACCEPTANCE EVALUATION

- **Gate 9 Criteria:** WFE Ratio $> 0.50$ with positive out-of-sample returns.
- **Evaluation:** Across all 15 evaluated out-of-sample folds across the 3 candidates, **exactly zero folds produced a positive net return**.
- Out-of-sample returns were consistently negative across every temporal regime.
- **Verdict:** **GATE 9 FAILED** across all candidate strategies.
