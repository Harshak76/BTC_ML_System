# Phase 3C.1 Technical Integrity Audit: Walk-Forward Split Methodology

**Document ID:** `WALK_FORWARD_METHODOLOGY_AUDIT.md`  
**Phase:** 3C.1 Independent Technical Integrity Audit  
**Starting Commit:** `76f7be8748ce69663148615099a51497da4883f6`  
**Base Commit:** `097952a`  
**Audit Target:** `docs/research/phase_3c/WALK_FORWARD_REPORT.md`, `btc_ml_system/src/validation/walk_forward.py`, and walk-forward execution scripts.

---

## 1. Executive Summary

This independent technical audit examined the 5-fold walk-forward cross-validation engine and empirical results reported in Phase 3C. 

### Audit Verdict: TECHNICAL DEFECTS IDENTIFIED — RESEARCH REJECTION CONFIRMED
1. **Defect D-02 (Overlapping OOS Folds):** The walk-forward test windows were generated with a step size of $50\%$ of the window length rather than $100\%$. Consequently, adjacent Out-of-Sample (OOS) testing partitions share a $50\%$ data overlap (~71 calendar days of identical data between consecutive folds). The folds were incorrectly treated as statistically independent.
2. **Defect D-03 (Cold Indicator Warm-Up):** OOS partitions were sliced without lookback padding. For all strategies, the first 40 bars of every OOS test window generated `NaN` indicator values, creating a 40-bar dead-zone at the start of each testing fold.
3. **Defect D-04 (2026 Data Truncation):** Fold 5 testing terminated on `2025-12-12`, omitting the final 9+ months of the authentic dataset (which extends through `2026-09-22`).
4. **Impact on Research Conclusion:** **Zero impact on verdict.** Across all 15 evaluated candidate-fold combinations, **not a single fold produced a positive net return or positive Sharpe ratio**. In-Sample and Out-of-Sample returns were negative across every fold. Correcting the overlaps and warm-up padding cannot manufacture positive alpha out of consistently negative performance.

---

## 2. Partition Boundary & Slicing Analysis

The reported fold schedule in `WALK_FORWARD_REPORT.md` was verified against the script implementation:

| Fold | In-Sample Training Window | Out-of-Sample Testing Window | Test Window Duration | Overlap with Prior Fold Test |
| :--- | :--- | :--- | :--- | :--- |
| **Fold 1** | 2024-09-22 to 2024-10-13 | 2024-10-13 to 2025-03-04 | 142 days | None (Initial) |
| **Fold 2** | 2024-10-13 to 2024-12-23 | **2024-12-23** to 2025-05-14 | 142 days | **71 days (50.0%)** with Fold 1 |
| **Fold 3** | 2024-12-23 to 2025-03-04 | **2025-03-04** to 2025-07-24 | 142 days | **71 days (50.0%)** with Fold 2 |
| **Fold 4** | 2025-03-04 to 2025-05-14 | **2025-05-14** to 2025-10-03 | 142 days | **71 days (50.0%)** with Fold 3 |
| **Fold 5** | 2025-05-14 to 2025-07-24 | **2025-07-24** to 2025-12-12 | 142 days | **71 days (50.0%)** with Fold 4 |

### Slicing Defect Identification (Defect D-02)
Inspection of the split generation logic revealed that the partition generator stepped forward by:
$$\text{step\_size} = \frac{\text{test\_window}}{2}$$
This sliding-window scheme is appropriate for generating rolling continuous estimates, but it violates the statistical independence assumption required when reporting fold-level cross-validation metrics. 

Specific consequences:
- Trade results occurring between `2024-12-23` and `2025-03-04` were counted twice: once in Fold 1 OOS, and once in Fold 2 OOS.
- Trade results between `2025-03-04` and `2025-05-14` were counted twice: once in Fold 2 OOS, and once in Fold 3 OOS.
- The reported "Mean OOS Return" and "Mean OOS Sharpe" are weighted averages over an over-sampled middle partition, rather than a true stitched contiguous equity curve.

---

## 3. Indicator Warm-Up and Signal Dead-Zone (Defect D-03)

In rigorous quantitative walk-forward testing, technical indicators on out-of-sample slices must be initialized with historical lookback data (warm-up padding) so that the first out-of-sample bar has valid indicator values.

### The Defect
When `df_oos = df.iloc[test_start:test_end]` was passed into `strategy.generate_signals(df_oos)`:
- `high.rolling(window=40, closed='left').max()` evaluated to `NaN` for bars $0$ through $39$.
- `ADX(window=14)` evaluated to `NaN` for bars $0$ through $27$.
- `HTF EMA Slope` evaluated to `NaN` for the first several 4H intervals.

Consequently:
- During the first **40 bars** of each OOS test window ($40 \text{ hours} \approx 1.67 \text{ days}$ for crypto; $40 \text{ market hours} \approx 6.15 \text{ days}$ for equities), no trade entry signals could fire.
- While this did not introduce lookahead bias (it actually blinded the strategy temporarily), it represents a technical modeling flaw that distorts trading cadence at fold boundaries.

---

## 4. Dataset Truncation Audit (Defect D-04)

The authentic dataset used across Phase 3B and Phase 3C extends from:
- **Start:** `2024-10-07 00:00:00 UTC`
- **End:** `2026-09-22 23:00:00 UTC` (Total span: 715 days / ~24 months)

However, the walk-forward evaluation ended at Fold 5 OOS on:
- **Fold 5 Test End:** `2025-12-12`

### Findings
- **284 calendar days (9.3 months)** of authentic data (from `2025-12-12` to `2026-09-22`) were entirely excluded from the walk-forward validation.
- The full continuous backtest (`runner.py`) correctly utilized all 17,520 hours through `2026-09-22`. The walk-forward partitioner arbitrarily stopped early due to hardcoded fold counts and window lengths.

---

## 5. Position State & Capital Isolation Audit

We inspected whether trading state leaked across folds:
- **Capital Reset:** Confirmed. Each fold initialized with $\$10,000.00$ cash and an empty portfolio.
- **Position Carry-Over:** Confirmed clean. Open positions from In-Sample training were not carried into the Out-of-Sample test window.
- **Cash Drag:** Because initial capital was reset to $\$10,000.00$ without open positions, each fold began with zero drawdown.

---

## 6. Empirical Robustness: Does Remediating the Defects Alter the Verdict?

To establish whether these three defects (D-02, D-03, D-04) could have falsely caused the rejection of the strategy candidates, we examine the sign and magnitude of the returns across all folds:

```
Candidate 1 (Control):
  Fold 1 OOS Return: -2.62%, Sharpe: -1.65
  Fold 2 OOS Return: -2.49%, Sharpe: -1.70
  Fold 3 OOS Return: -5.76%, Sharpe: -4.15
  Fold 4 OOS Return: -4.31%, Sharpe: -3.22
  Fold 5 OOS Return: -1.32%, Sharpe: -1.01

Candidate 2 (ADX25 Filter):
  Fold 1 OOS Return: -2.08%, Sharpe: -1.85
  Fold 2 OOS Return: -2.93%, Sharpe: -3.39
  Fold 3 OOS Return: -0.86%, Sharpe: -1.17
  Fold 4 OOS Return: -0.10%, Sharpe: -0.11
  Fold 5 OOS Return: -0.99%, Sharpe: -1.30

Candidate 3 (4H EMA Slope Filter):
  Fold 1 OOS Return: -2.34%, Sharpe: -1.57
  Fold 2 OOS Return: -2.00%, Sharpe: -1.47
  Fold 3 OOS Return: -4.58%, Sharpe: -3.44
  Fold 4 OOS Return: -3.57%, Sharpe: -2.81
  Fold 5 OOS Return: -0.95%, Sharpe: -0.75
```

### Analytical Deduction
1. **$100\%$ Negative Rate:** 15 out of 15 OOS folds produced negative net returns. Not a single fold achieved even a $+0.01\%$ return.
2. **Deeply Sub-Zero Sharpes:** The mean OOS Sharpe across all candidates ranged from $-1.56$ to $-2.35$. The acceptance gate required $SR_{OOS} \ge +1.00$.
3. **Independent Full Backtest Corroboration:** The full 24-month backtest (which had zero partition overlap, proper indicator warm-up, and utilized the entire dataset through September 2026) confirmed identical negative outcomes:
   - Control Annualized Sharpe: $-1.11$
   - ADX25 Annualized Sharpe: $-0.72$
   - 4H EMA Slope Annualized Sharpe: $-1.44$

**Conclusion:** The walk-forward methodology defects are genuine technical flaws in the research script, but they **did NOT cause a false negative**. The underlying strategies possess zero structural alpha on these assets during the 2024–2026 market regime.

---

## 7. Defect Inventory

| Defect ID | Title | Severity | Impact on Phase 3C Verdict |
| :--- | :--- | :--- | :--- |
| `DEFECT-3C1-02` | Overlapping Out-of-Sample Walk-Forward Partitions (50% Shared Data) | Moderate | Nil (All partitions strictly negative) |
| `DEFECT-3C1-03` | Unpadded Out-of-Sample Slicing (40-Bar Cold Indicator Dead-Zone) | Minor | Nil (Signal suppression did not alter loss trend) |
| `DEFECT-3C1-04` | Walk-Forward Horizon Truncation (Omitting 2026 Data Past Dec 2025) | Minor | Nil (Full 24-month backtest confirmed negative edge) |
