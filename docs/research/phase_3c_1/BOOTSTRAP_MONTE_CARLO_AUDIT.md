# Phase 3C.1 Technical Integrity Audit: Bootstrap and Monte Carlo Verification

**Document ID:** `BOOTSTRAP_MONTE_CARLO_AUDIT.md`  
**Phase:** 3C.1 Independent Technical Integrity Audit  
**Starting Commit:** `76f7be8748ce69663148615099a51497da4883f6`  
**Base Commit:** `097952a`  
**Audit Target:** `docs/research/phase_3c/BOOTSTRAP_REPORT.md`, `MONTE_CARLO_REPORT.md`, `audit_evidence/DRAWDOWN_DISCREPANCY_ANALYSIS.md`, `btc_ml_system/src/validation/bootstrap.py`, `btc_ml_system/src/validation/monte_carlo.py`.

---

## 1. Executive Summary

This independent technical audit examined the resampling and stress-testing methodologies employed in Phase 3C, specifically auditing:
1. The non-parametric IID trade bootstrap and Politis-Romano (1994) stationary block bootstrap.
2. The Monte Carlo stress testing framework across 9 adverse execution scenarios.
3. The discrepancy between the $10\%$ institutional production risk limit and the $20\%$ Phase 3C research gate.
4. Capital ruin calculations and compounding methodology.

### Audit Verdict: METHODOLOGICALLY SOUND & VERIFIED
- Resampling techniques appropriately preserved return serial correlation via geometric block bootstrapping ($L = 24$ hours).
- Compounding of multi-period returns was implemented correctly.
- Capital ruin definitions ($50\%$ equity depletion) were strictly enforced and verified.
- The reported distributions confirm that all three strategy candidates fail Acceptance Gate 5 (Stationary Bootstrap 95% CI lower bound $> 0$) and exhibit failure probabilities exceeding $86\%$ to $99\%$.

---

## 2. Bootstrap Resampling Engine Verification

Phase 3C evaluated two distinct resampling engines across 1,000 synthetic iterations (Seed: 42):

### 1. Non-Parametric Trade-Level Bootstrap (IID)
- **Mechanism:** Resamples completed trade PnL dollars with replacement.
- **Statistical Property:** Breaks temporal sequence; tests path-independence, trade-level win rate stability, and payoff skewness.
- **Verification:** Implementation in `btc_ml_system/src/validation/bootstrap.py` correctly resamples the empirical discrete trade vector of length $M$ (where $M = 913$ for Control, $395$ for ADX25, $813$ for 4H EMA).

### 2. Stationary Block Bootstrap (Politis & Romano 1994)
- **Mechanism:** Resamples blocks of hourly periodic returns where block length $K$ follows a geometric distribution with mean $L$:
  $$P(K = k) = (1 - p)^{k-1} p, \quad p = \frac{1}{L}, \quad L = 24 \text{ bars}$$
- **Statistical Property:** Strictly preserves short-term autocorrelation, intraday cyclicality (24-hour cycle), and volatility clustering without introducing edge artifacts (unlike circular block bootstrap).
- **Verification:** Confirmed appropriate for hourly financial series where return autocorrelation decays within 24 hours.

---

## 3. Independent Distribution & Confidence Interval Reconciliation

The empirical distributions reported in `BOOTSTRAP_REPORT.md` were independently verified:

| Candidate Strategy | Historical Total Return | Trade BS Mean Return | Trade BS 95% CI | Prob. Negative Return | Stationary BS 95% CI | Gate 5 Status ($CI_{lower} > 0$) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Control** (`DONCHIAN_40`) | $-9.57\%$ | $-9.56\%$ | $[-19.35\%, +0.75\%]$ | **$96.60\%$** | $[-19.82\%, +0.83\%]$ | **FAILED** |
| **ADX25 Filter** | $-4.30\%$ | $-4.25\%$ | $[-11.50\%, +3.26\%]$ | **$86.50\%$** | $[-11.48\%, +4.66\%]$ | **FAILED** |
| **4H EMA Slope Filter** | $-11.36\%$ | $-11.36\%$ | $[-20.41\%, -2.25\%]$ | **$99.40\%$** | $[-21.41\%, -1.20\%]$ | **FAILED** |

### Mathematical Verification Notes
1. **Unbiased Mean:** For all three candidates, the bootstrap distribution mean matches the empirical historical return to within $0.05\%$, confirming unbiased sampling with replacement.
2. **Negative Return Probabilities:**
   - Control: $96.6\%$ probability of losing money over 2 years.
   - ADX25: $86.5\%$ probability of losing money over 2 years.
   - 4H EMA: $99.4\%$ probability of losing money over 2 years (95% CI upper bound is $-2.25\%$, strictly below zero).
3. **Compounding Mechanics:** Returns were compounded multiplicatively:
   $$E_T = E_0 \prod_{t=1}^T (1 + r_t)$$
   rather than summed linearly, correctly reflecting portfolio equity dynamics.

---

## 4. Monte Carlo Stress Testing and Ruin Analysis

The Monte Carlo engine in `btc_ml_system/src/validation/monte_carlo.py` evaluated the strategies across 9 parameter stress dimensions:

### Ruin Probability Definition
- **Ruin Threshold:** Portfolio equity $E_t < 0.50 \cdot E_0$ ($\ge 50\%$ capital loss).
- **Observation:** In both historical backtests and 1,000 reshuffled Monte Carlo paths, equity never fell below $\$5,000$ (initial capital $\$10,000$).
- **Reported Survival Rate:** $100\%$ survival above the $50\%$ ruin threshold (Gate 6 Passed).
- **Audit Assessment:** While surviving $50\%$ ruin satisfies Gate 6, surviving catastrophic destruction is an insufficient hurdle for production trading. All candidates experienced chronic negative drift.

### Drawdown Distributions: Historical vs. Reshuffled vs. Bootstrap
An essential check is the comparison of maximum drawdowns across different simulation frameworks:

| Strategy | Historical Backtest MaxDD | Monte Carlo Shuffle 95th MaxDD | Monte Carlo Shuffle Worst MaxDD | Trade BS 95th MaxDD |
| :--- | :--- | :--- | :--- | :--- |
| **Control** | $13.22\%$ | $13.83\%$ | $16.86\%$ | $19.19\%$ |
| **ADX25 Filter** | **$7.18\%$** | **$8.38\%$** | **$10.25\%$** | **$11.46\%$** |
| **4H EMA Slope** | $12.50\%$ | $14.50\%$ | $17.27\%$ | $20.20\%$ |

### Audit Findings
1. **Sequence Fragility:** Reshuffling the order of trades increases the 95th percentile drawdown by $0.6\%$ to $2.0\%$ above historical levels. This occurs because losing trades cluster under certain permutations, exposing sequence risk.
2. **Trade-Level Bootstrap Drawdown:** Reaching up to $19.19\%$ (Control) and $20.20\%$ (4H EMA), confirming that under unfavorable resampling, unhedged Donchian trend following approaches a $20\%$ drawdown.
3. **ADX Filter Risk Compression:** Under every simulation regime, the ADX filter substantially mitigated tail risk, holding the 95th percentile drawdown to $8.38\%$ (MC) and $11.46\%$ (Bootstrap).

---

## 5. Drawdown Threshold Reconciliation: 10% Production Limit vs. 20% Gate

The audit confirmed the presence of a governance dichotomy:
- **Production Limit:** $10.0\%$ MaxDD circuit breaker (`portfolio_paper_v5.yaml`, `risk.py`).
- **Research Pre-Registration Gate (Gate 2):** $20.0\%$ MaxDD limit (`PHASE_3C_PREREGISTRATION.md`).

### Audit Reconciliation
- In research exploration, wide gates ($20\%$) are sometimes adopted to study unconstrained momentum behavior across multi-year cycles.
- However, from an operational perspective:
  - **Control ($13.22\%$ MaxDD)** and **4H EMA Slope ($12.50\%$ MaxDD)** breached the $10\%$ production ceiling and would have triggered emergency portfolio liquidation in production.
  - **ADX25 ($7.18\%$ MaxDD)** was the only candidate to pass both the $20\%$ research hurdle and the $10\%$ production cap.
- **Verdict Impact:** This discrepancy does not alter the final rejection. ADX25 failed Gates 1, 3, 4, 5, 8, and 9 due to persistent negative net returns.

---

## 6. Audit Conclusion

The bootstrap and Monte Carlo validation engines in Phase 3C are **technically sound, mathematically correct, and properly implemented**:
- Block bootstrapping appropriately preserved temporal dependence ($L = 24$).
- Multi-period returns were properly compounded.
- The reported distributions accurately reflect the reality that all three candidates have zero statistical edge and carry an $86\%$ to $99\%$ probability of net loss.
