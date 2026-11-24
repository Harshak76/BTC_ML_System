# BTC-ML SYSTEM V2 — PHASE 3C PBO STATUS REPORT
## Probability of Backtest Overfitting (PBO) & CSCV Evaluation Status

- **Date:** 2026-11-24
- **Auditor:** Senior Quantitative Researcher & Backtesting Auditor
- **Repository Branch:** `feat/phase-3c-controlled-filter-experiment`
- **Starting Commit:** `097952a`
- **Methodology:** Combinatorially Symmetric Cross-Validation (CSCV) / López de Prado (2013)
- **Status:** **`PBO: INCOMPLETE — INSUFFICIENT GENUINE CANDIDATE POOL`**

---

## 1. FORMAL STATUS & GOVERNANCE COMPLIANCE

In strict accordance with the non-negotiable governance rules established in Phase 3B.2.2 and reiterated in the Phase 3C Pre-Registration:
- Combinatorially Symmetric Cross-Validation (CSCV) requires a minimum candidate pool size of $N \ge 4$ genuinely distinct strategies to partition candidate subsets $C(S, S/2)$ and evaluate the empirical rank correlation between In-Sample (IS) and Out-of-Sample (OOS) performance.
- Phase 3C is a controlled 2-filter experiment testing exactly 3 pre-registered candidates:
  1. `RS_MOM_DONCHIAN_40_CONTROL`
  2. `RS_MOM_DONCHIAN_40_ADX25`
  3. `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE`
- With $N = 3$, the candidate pool is mathematically insufficient to construct meaningful combinatorial splits without degenerating into trivial rankings.
- **Strict Prohibition on Synthetic Inflation:** In Phase 3B.1, an integrity violation occurred when synthetic Gaussian perturbation was used to fabricate candidate matrix columns. Phase 3B.2 and 3C strictly prohibit synthetic perturbation.
- Therefore, the official PBO status for Phase 3C is recorded as:
  > **`PBO: INCOMPLETE — INSUFFICIENT GENUINE CANDIDATE POOL (N=3 < 4)`**

---

## 2. MATHEMATICAL PREREQUISITES FOR VALID CSCV

For future research phases seeking formal PBO calculation, the following structural conditions must be satisfied:
1. **Candidate Pool Size:** $N \ge 4$ (preferably $N \ge 16$ or $N \ge 32$) genuinely implemented, pre-registered quantitative strategies with distinct economic hypotheses.
2. **Matrix Shape:** Return matrix $M \in \mathbb{R}^{T \times N}$, where all $N$ return vectors are aligned on identical discrete timestamps across the multi-asset portfolio.
3. **Number of Partitions:** An even number of equal chronological blocks $S$ (e.g., $S = 10$ blocks), yielding:
   $$\binom{S}{S/2} = \binom{10}{5} = 252 \text{ combinatorial train/test combinations}$$
4. **Logit Distribution & Degradation Slope:** PBO is defined as the empirical probability that the in-sample optimal candidate produces below-median out-of-sample performance:
   $$\text{PBO} = \int_{-\infty}^{0} f(\lambda) \, d\lambda$$

---

## 3. AUDIT CONCLUSION

The PBO metric cannot be reliably computed for Phase 3C due to the small candidate pool ($N = 3$). Recording `PBO: INCOMPLETE` preserves complete scientific and mathematical honesty, avoids synthetic inflation violations, and satisfies Gate 8.
