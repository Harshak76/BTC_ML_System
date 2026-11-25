# BTC-ML SYSTEM V2 — PHASE 3C.2.2 TARGETED AUDIT REPORT
# OUT-OF-SAMPLE RETURN DEFINITIONS AND ACCOUNTING AUDIT

**Document ID:** `OOS_RETURN_DEFINITION_AUDIT.md`  
**Phase:** 3C.2.2 Targeted DSR Unit Reconciliation & Final Phase 3 Closure Audit  
**Repository:** `BTC_ML_System`  
**Working Branch:** `fix/phase-3c-2-research-integrity`  
**Base Commit:** `93e7121`  
**Date:** 2026-11-25  
**Auditor:** Independent Quantitative Research Auditor  
**Audit Mode:** Strictly Read-Only  

---

## 1. Executive Summary & Objective

In quantitative research reports, performance percentages can easily be conflated when multiple evaluation streams are cited side-by-side. In Phase 3C.2, two primary return figures were reported for each candidate:
- **Full-Period Return:** $-15.83\%$ (Control), $-6.19\%$ (ADX25), $-15.04\%$ (4H EMA).
- **Stitched Out-of-Sample (OOS) Return:** $-9.35\%$ (Control), $-3.18\%$ (ADX25), $-9.76\%$ (4H EMA).

This audit rigorously establishes the mathematical definitions, denominators, compounding assumptions, and evaluation horizons of both metrics, confirming that they are **not directly interchangeable**.

```
========================================================================================
                                 CORE DISTINCTION:
  1. FULL-PERIOD RETURN measures 24-MONTH CONTINUOUSLY COMPOUNDED EQUITY PERFORMANCE.
     Denominator: Initial capital $100,000. Compounding: Dynamic, continuous.
     Horizon: 17,520 hours (September 2024 to September 2026).
  2. STITCHED OOS RETURN measures 18-MONTH NORMALIZED NOMINAL PnL ACCROSS DISJOINT FOLDS.
     Denominator: Static base capital $100,000. Compounding: Uncompounded additive sum.
     Horizon: 13,140 hours (March 2025 to September 2026; excludes initial 6m IS1).
========================================================================================
```

---

## 2. Mathematical Formalization of the Two Performance Metrics

### Definition A: Full-Period Continuously Compounded Return
Let $E_t$ denote total portfolio equity (cash balance plus unrealized mark-to-market position values) at hourly discrete timestep $t \in [0, T]$, where $T = 17,520$ hours:
$$\text{Return}_{\text{Full}} = \frac{E_T - E_0}{E_0} \times 100\%$$
- **Starting Equity ($E_0$):** Exactly $\$100,000.00$ at $t = 0$ (`2024-09-22 17:00:00 UTC`).
- **Terminal Equity ($E_T$):** Total liquidated portfolio value at $t = 17,520$ (`2026-09-22 16:00:00 UTC`).
- **Compounding Dynamic:** Geometric, dynamic, path-dependent.
  - Position sizing is dynamically scaled to $0.5\%$ risk of current equity:
    $$\text{Position Value}_t = f(E_t)$$
  - As capital shrinks during drawdowns, subsequent trade position sizes shrink proportionally in dollar terms.
  - Periodic hourly returns are:
    $$r_t = \frac{E_t - E_{t-1}}{E_{t-1}}$$
  - The compounded product satisfies:
    $$\frac{E_T}{E_0} = \prod_{t=1}^T (1 + r_t)$$
- **Scope:** Evaluates the entire 24-month lifespan of the strategy, including the first 6 months where severe losses were incurred.

---

### Definition B: Stitched Out-of-Sample Normalized Nominal PnL Return
In walk-forward cross-validation, the evaluation horizon is partitioned into $K = 4$ non-overlapping out-of-sample folds. Each fold $k \in \{1, 2, 3, 4\}$ is evaluated as an isolated simulation. Let $\text{PnL}_{k, i}$ be the net realized dollar PnL of trade $i$ executed within fold $k$'s OOS window:
$$\text{Return}_{\text{Stitched\_OOS}} = \frac{\sum_{k=1}^K \sum_{i=1}^{M_k} \text{PnL}_{k, i}}{\text{Base Capital}} \times 100\%$$
- **Base Capital Denominator:** Static constant $\$100,000.00$.
- **Numerator:** Total dollar profit/loss generated strictly by out-of-sample trades across all 4 folds:
  $$\text{Total OOS PnL} = \sum_{k=1}^4 \text{PnL}_{\text{OOS}, k}$$
- **Compounding Dynamic:** Strictly additive, uncompounded across folds.
  - Each fold $k$ starts afresh with $\$100,000.00$ initial capital.
  - Losses in Fold 1 do not reduce the starting capital of Fold 2.
  - Dollar PnLs are simply aggregated and normalized to the $\$100,000$ base.
- **Scope:** Evaluates strictly the 18-month out-of-sample period (`2025-03-24 05:00:00` to `2026-09-22 16:00:00` UTC). It **completely excludes** the initial 4,380 hours (~182 days) that served as the training baseline (IS1) for Fold 1.

---

## 3. Side-by-Side Accounting Breakdown

The exact numerical components entering each metric are detailed below:

| Metric Component | Dimension / Formula | `RS_MOM_DONCHIAN_40_CONTROL` | `RS_MOM_DONCHIAN_40_ADX25` | `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE` |
| :--- | :--- | :--- | :--- | :--- |
| **Full-Period Start Date** | UTC timestamp | `2024-09-22 17:00:00` | `2024-09-22 17:00:00` | `2024-09-22 17:00:00` |
| **Full-Period End Date** | UTC timestamp | `2026-09-22 16:00:00` | `2026-09-22 16:00:00` | `2026-09-22 16:00:00` |
| **Full-Period Duration** | Hourly observations | $17,520$ hours (24 months) | $17,520$ hours (24 months) | $17,520$ hours (24 months) |
| **Initial Starting Capital ($E_0$)** | USD | $\$100,000.00$ | $\$100,000.00$ | $\$100,000.00$ |
| **Final Portfolio Equity ($E_T$)** | USD | $\$84,174.66$ | $\$93,809.48$ | $\$84,959.70$ |
| **Full-Period Total Net PnL** | USD | **$-\$15,825.34$** | **$-\$6,190.52$** | **$-\$15,040.30$** |
| **Full-Period Net Return** | Percentage | **$-15.8253\%$** | **$-6.1905\%$** | **$-15.0403\%$** |
| | | | | |
| **Initial Training Window (IS1)** | Hours (Bars 0 to 4,379) | $4,380$ hours (6 months) | $4,380$ hours (6 months) | $4,380$ hours (6 months) |
| **IS1 Excluded PnL** | USD | **$-\$7,296.78$** | **$-\$3,113.71$** | **$-\$6,091.93$** |
| **IS1 Excluded Trades** | Trade count | 221 trades | 88 trades | 197 trades |
| | | | | |
| **Stitched OOS Start Date** | UTC timestamp | `2025-03-24 05:00:00` | `2025-03-24 05:00:00` | `2025-03-24 05:00:00` |
| **Stitched OOS End Date** | UTC timestamp | `2026-09-22 16:00:00` | `2026-09-22 16:00:00` | `2026-09-22 16:00:00` |
| **Stitched OOS Duration** | Hourly observations | $13,140$ hours (18 months) | $13,140$ hours (18 months) | $13,140$ hours (18 months) |
| **Stitched OOS Trade Count** | Trade count | 691 trades | 293 trades | 607 trades |
| **Fold 1 OOS PnL** | USD | $-\$5,420.08$ (193 tr) | $-\$2,488.45$ (63 tr) | $-\$4,148.94$ (173 tr) |
| **Fold 2 OOS PnL** | USD | $-\$4,140.42$ (166 tr) | $-\$1,986.72$ (72 tr) | $-\$3,071.87$ (144 tr) |
| **Fold 3 OOS PnL** | USD | $-\$518.83$ (162 tr) | $+\$489.43$ (84 tr) | $-\$609.97$ (148 tr) |
| **Fold 4 OOS PnL** | USD | $+\$734.36$ (170 tr) | $+\$812.40$ (74 tr) | $-\$1,930.74$ (142 tr) |
| **Stitched OOS Total Net PnL**| USD | **$-\$9,344.96$** | **$-\$3,173.34$** | **$-\$9,761.51$** |
| **Stitched OOS Base Capital** | USD (Denominator) | $\$100,000.00$ | $\$100,000.00$ | $\$100,000.00$ |
| **Stitched OOS Return** | Percentage | **$-9.3450\%$** | **$-3.1733\%$** | **$-9.7615\%$** |

---

## 4. Key Accounting Reconciliations

### 1. Why Is Stitched OOS Return Less Negative Than Full-Period Return?
For Control, Stitched OOS is $-9.35\%$ while Full-Period is $-15.83\%$. This occurs primarily because **$-\$7,296.78$ of losses occurred during the first 6 months** (`2024-09-22` to `2025-03-24`).
- Full-period includes these losses: $-\$7,296.78 + (-\$8,528.56) = -\$15,825.34$.
- Walk-forward starts evaluating OOS performance only on `2025-03-24`, so the first 6 months of drawdown are excluded from the OOS sum.

### 2. Why Does Post-Warmup PnL ($-\$8,528.56$) Differ from Stitched OOS PnL ($-\$9,344.96$)?
Even within the identical 18-month window (`2025-03-24` to `2026-09-22`), the continuous run lost $-\$8,528.56$ while the walk-forward folds lost $-\$9,344.96$. This difference ($\Delta = \$816.40$) is driven by two factors:
1. **Capital Base Reset:** In walk-forward, each fold starts with a fresh $\$100,000$ capital base. In the continuous simulation, the portfolio entered March 2025 with depleted capital ($\approx \$92,700$). Because position sizing is $0.5\%$ of current capital, the continuous simulation took smaller dollar positions during Folds 1 and 2, losing fewer absolute dollars during losing runs.
2. **Boundary Trade Exclusion:** Trade `AAPL_20250324_1400` ($-\$59.58$) was suppressed in Fold 1 due to the weekend lookback pad issue.

---

## 5. Reporting Governance Standard

To maintain institutional quantitative transparency, the following standards are mandatory:

1. **Explicit Horizon Labeling:** Never report the walk-forward return as simply "Out-of-Sample Return". It must always be labeled:
   $$\mathbf{\text{“18-Month Stitched OOS Normalized Return (ex-IS1 training window)}”}$$
2. **Prohibition of Direct Interchangeability:** Research deliverables must not present full-period continuously compounded return ($-15.83\%$) and stitched OOS normalized return ($-9.35\%$) as directly interchangeable numbers.
3. **Disclosure of Denominator:** When presenting stitched OOS return, reports must explicitly disclose that the denominator is the normalized $\$100,000$ base capital, not the terminal compounded equity of prior folds.
