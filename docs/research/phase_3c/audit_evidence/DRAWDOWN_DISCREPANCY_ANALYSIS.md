# BTC-ML SYSTEM V2 — PHASE 3C DRAWDOWN DISCREPANCY AUDIT
## Investigation into the 10% Production Risk Limit vs. 20% Phase 3C Acceptance Gate

- **Date:** 2026-11-24
- **Auditor:** Quantitative Risk & Backtesting Auditor
- **Repository Branch:** `feat/phase-3c-controlled-filter-experiment`
- **Scope:** Reconciling the divergence between the institutional 10% portfolio drawdown limit and the 20% Phase 3C research gate.

---

## 1. NATURE OF THE DISCREPANCY

An explicit discrepancy exists between two risk thresholds within the BTC-ML System V2 codebase and governance documentation:

1. **The 10% Operational / Production Limit:**
   - Defined in production risk management configurations (`btc_ml_system/configs/portfolio_paper_v5.yaml`), execution harnesses (`btc_ml_system/src/risk.py`), and stress engines (`btc_ml_system/src/validation/monte_carlo.py` line 43):
     ```python
     self.max_drawdown_limit_pct = float(
         self.config.get("portfolio", {}).get("risk_limits", {}).get("max_drawdown_limit_pct", 10.0)
     )
     ```
   - In live and paper trading, breaching $10.0\%$ drawdown triggers an immediate mandatory circuit-breaker liquidation and trading halt.

2. **The 20% Phase 3C Pre-Registered Acceptance Gate (Gate 2):**
   - Defined in `PHASE_3C_PREREGISTRATION.md` and subsequent reports as:
     `Gate 2: Maximum Drawdown < 20.0%`
   - Formally designed as a broad research exploratory hurdle for unoptimized multi-asset trend strategies evaluated over multi-year horizons (2024–2026).

---

## 2. ORIGIN & RATIONALE OF THE DIVERGENCE

1. **Research Exploration vs. Deployment Mandate:**
   - In quantitative research, early-stage unoptimized baseline strategies are often allowed a wider drawdown corridor ($20\%$) to observe factor dynamics without prematurely terminating the backtest.
   - However, in production execution, investor capital preservation dictates a non-negotiable $10.0\%$ drawdown cap.
2. **Governance Failure in Harmonization:**
   - When the Phase 3A, 3B, and 3C pre-registrations were drafted, Gate 2 adopted the $20\%$ exploratory threshold without explicitly reconciling or noting the divergence from the existing $10.0\%$ production limit in `portfolio_paper_v5.yaml`.

---

## 3. QUANTITATIVE IMPACT ON PHASE 3C CANDIDATES

Evaluating all three Phase 3C strategies against BOTH thresholds reveals critical risk insights:

```
+----------------------------------------------------------------------------------------------------+
| MAXIMUM DRAWDOWN COMPARISON: RESEARCH GATE (20%) VS. PRODUCTION LIMIT (10%)                       |
+----------------------------------+------------------+-----------------------+---------------------+
| Strategy Candidate               | Empirical MaxDD  | Gate 2 Status (< 20%) | Prod Limit (< 10%)  |
+----------------------------------+------------------+-----------------------+---------------------+
| RS_MOM_DONCHIAN_40_CONTROL       | 13.22%           | PASSED                | BREACHED (+3.22%)   |
| RS_MOM_DONCHIAN_40_ADX25         | 7.18%            | PASSED                | PASSED (-2.82%)     |
| RS_MOM_DONCHIAN_40_4H_EMA_SLOPE  | 12.50%           | PASSED                | BREACHED (+2.50%)   |
+----------------------------------+------------------+-----------------------+---------------------+
```

### Empirical Implications:
1. **Control Strategy (`DONCHIAN_40`):**
   - At **$13.22\%$ MaxDD**, the Control candidate passed the $20\%$ research gate, but would have suffered an emergency shutdown and liquidation in production when breaching $10\%$.
   - In Monte Carlo trade shuffling, 95th percentile MaxDD reached **$13.83\%$**, and worst-case MaxDD reached **$16.86\%$**, breaching the 10% limit in $100\%$ of simulated paths.
2. **4H EMA Slope Strategy:**
   - At **$12.50\%$ MaxDD**, this candidate also passed the $20\%$ research gate, but breached the $10\%$ operational risk limit.
   - Monte Carlo worst-case MaxDD reached **$17.27\%$**.
3. **ADX Treatment Strategy (`ADX25`):**
   - At **$7.18\%$ MaxDD**, `RS_MOM_DONCHIAN_40_ADX25` was the **ONLY** candidate that satisfied BOTH the $20\%$ research gate AND the strict $10\%$ institutional production limit.
   - Its Monte Carlo 95th percentile MaxDD was $8.38\%$, with worst-case reaching $10.25\%$.

---

## 4. AUDIT VERDICT & GOVERNANCE RESOLUTION

1. **Did the 20% Threshold Mask Operational Failure?**
   - **YES for Control and 4H EMA Slope.** Both strategies experienced drawdowns that exceed production risk tolerances ($13.22\%$ and $12.50\%$).
   - **NO for ADX25.** The ADX filter successfully contained maximum drawdown to $7.18\%$, proving that $ADX \ge 25$ is genuinely effective at risk compression.
2. **Does the Discrepancy Change the Final Verdict?**
   - **NO.** Even though `RS_MOM_DONCHIAN_40_ADX25` successfully met the strict $10\%$ production limit ($7.18\% < 10.0\%$), it decisively failed Gate 1 (Net Return $-4.30\%$, Sharpe $-0.7198$) and Gate 4 (DSR $p=0.9956$).
   - All three candidates remain correctly and unambiguously classified as:
     > **`REJECTED — NOT ELIGIBLE FOR PAPER TRADING`**
3. **Mandatory Recommendation for Future Phases:**
   - Future pre-registrations must explicitly bind Gate 2 to the production limit: $\text{MaxDD} < 10.0\%$, eliminating dual-standard confusion.
