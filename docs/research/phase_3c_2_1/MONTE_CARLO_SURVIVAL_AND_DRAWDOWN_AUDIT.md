# BTC-ML SYSTEM V2 — PHASE 3C.2.1 AUDIT REPORT
# MONTE CARLO SURVIVAL AND DRAWDOWN AUDIT

**Document ID:** `MONTE_CARLO_SURVIVAL_AND_DRAWDOWN_AUDIT.md`  
**Phase:** 3C.2.1 Independent Final Statistical and Performance Reconciliation Audit  
**Repository:** `BTC_ML_System`  
**Working Branch:** `fix/phase-3c-2-research-integrity`  
**Base Commit:** `93e7121`  
**Date:** 2026-11-25  
**Auditor:** Independent Quantitative Research Auditor  
**Audit Mode:** Strictly Read-Only  

---

## 1. Executive Summary

In Phase 3C.2, the acceptance gate scorecard reported:
- **Gate 6 (Monte Carlo Survival Rate):** Reported as **`100.0% (PASSED)`** for all three candidates.
- **Gate 2 (Maximum Drawdown):** Reported as **`PASSED*`** with a footnote disclosing that Control reached a **$20.84\%$** worst-case drawdown and both Control and 4H EMA breached the **$10.0\%$** production limit in simulated paths.

This independent audit investigates the apparent contradiction between a reported "100% survival rate" and severe drawdown breaches.

```
========================================================================================
                                 KEY AUDIT FINDING:
     "100% SURVIVAL" REFERS STRICTLY TO AVOIDANCE OF A CATASTROPHIC 50% LOSS THRESHOLD.
     IT DOES NOT MEAN THE STRATEGY IS RISK-COMPLIANT OR FIT FOR PRODUCTION TRADING.
     BOTH CONTROL AND 4H EMA HAVE A 100.0% PROBABILITY OF VIOLATING PRODUCTION RISK LIMITS.
========================================================================================
```

---

## 2. Separation of Risk Boundaries & Threshold Definitions

To eliminate ambiguity, this audit explicitly decouples the four distinct risk concepts used in the repository:

| Risk Concept | Mathematical Threshold | Code Definition / Source | Purpose | Audit Status |
| :--- | :--- | :--- | :--- | :--- |
| **Total Ruin** | $\text{Drawdown} \ge 50.0\%$ | `BootstrapEngine.ruin_threshold_pct = 50.0` | Catastrophic capital destruction (Equity $\le \$50,000$) | 0 / 1,000 observed occurrences across all candidates |
| **Research Drawdown Limit** | $\text{Drawdown} \ge 20.0\%$ | Acceptance Gate 2 Criterion | Experimental disqualification boundary for backtesting | Breached by Control ($20.84\%$) and under Regime Stress ($26.50\%$, $25.36\%$) |
| **Production Drawdown Limit** | $\text{Drawdown} \ge 10.0\%$ | `MonteCarloEngine.max_drawdown_limit_pct = 10.0` | Live trading shutdown circuit breaker | **Breached by 100% of paths in Control and 4H EMA** |
| **Daily Loss Limit** | Daily Portfolio Loss $\ge 2.0\%$ | `MonteCarloEngine.daily_loss_limit_pct = 2.0` | Daily execution freeze circuit breaker | Breached in Scenario 9 flash crash ($3.0\%$) |

### Reconciliation of the Contradiction:
1. **Why "100% Survival Rate" Was Reported:** In `BootstrapEngine.py:94`, ruin is recorded only if `max_dd * 100.0 >= self.ruin_threshold_pct` ($50.0\%$). Because the deepest drawdown reached by any simulated path was $20.84\%$ for Control, zero paths reached the $50\%$ loss level. Therefore, `prob_ruin = 0.0%`, and the survival rate was mathematically reported as $100.0\% - 0.0\% = 100.0\%$. Under the Rule of Three ($3/N$), the 95% upper confidence bound for the risk of $50\%$ ruin is $\le 0.30\%$.
2. **Why It Is Misleading Without Qualification:** Describing a strategy as having a "100% survival rate" in executive summaries conveys the impression of capital safety. However, a strategy that loses $15\%$ to $21\%$ of capital and breaches production drawdown limits on $100\%$ of simulated paths is fundamentally unsafe, despite avoiding total bankruptcy.

---

## 3. Drawdown Distribution Under Randomized Trade Ordering

Under Scenario 1 (Randomized Trade Ordering, 1,000 iterations), the completed trade PnL sequence was randomly permuted to test path-dependency. The resulting empirical distributions are:

| Metric | `RS_MOM_DONCHIAN_40_CONTROL` | `RS_MOM_DONCHIAN_40_ADX25` | `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE` |
| :--- | :--- | :--- | :--- |
| **Baseline Backtest MaxDD** | $17.33\%$ | $8.59\%$ | $15.04\%$ |
| **Median Shuffled MaxDD** | $16.72\%$ | $7.34\%$ | $15.81\%$ |
| **95th Percentile MaxDD** | **$18.41\%$** | **$8.93\%$** | **$17.44\%$** |
| **99th Percentile MaxDD** | **$19.23\%$** | **$9.87\%$** | **$18.20\%$** |
| **Worst-Case Simulated MaxDD** | **$20.84\%$** (Breaches 20%) | **$10.71\%$** | **$19.81\%$** |
| **Expected Shortfall (CVaR 95%)**| **$19.00\%$** | **$9.44\%$** | **$17.96\%$** |
| **Probability of Breaching 10% Limit**| **$100.00\%$ (1,000 / 1,000)** | **$0.80\%$ (8 / 1,000)** | **$100.00\%$ (1,000 / 1,000)** |
| **Probability of Breaching 20% Limit**| **$0.90\%$ (9 / 1,000)** | **$0.00\%$ (0 / 1,000)** | **$0.00\%$ (0 / 1,000)** |
| **Probability of Total Ruin ($\ge 50\%$)**| **$0.00\%$ ($\le 0.30\%$ bound)** | **$0.00\%$ ($\le 0.30\%$ bound)** | **$0.00\%$ ($\le 0.30\%$ bound)** |

### Analytical Takeaways:
- **Control Strategy:** Every single shuffled sequence ($100.00\%$) breached the $10\%$ production limit. In the worst path, consecutive losing trades clustered to produce a **$20.84\%$ drawdown**, violating the $20\%$ research limit.
- **4H EMA Slope:** Similarly, $100.00\%$ of paths breached the $10\%$ production limit, with a 95th percentile drawdown of $17.44\%$ and worst-case $19.81\%$.
- **ADX25 Filter:** ADX25 demonstrated superior drawdown control. Only $0.80\%$ of paths breached the $10\%$ limit, and the 95th percentile drawdown was $8.93\%$.

---

## 4. Comprehensive Audit of All Nine Monte Carlo Stress Scenarios

The complete institutional stress testing suite was inspected across all 9 scenarios:

```
+-------------------------------------------------------------+------------------------------------+------------------------------------+
| Stress Scenario & Description                               | Control Performance Impact         | ADX25 Performance Impact           |
+-------------------------------------------------------------+------------------------------------+------------------------------------+
| 1. Randomized Trade Ordering (Path dependency)              | 95th MaxDD: 18.41%, Worst: 20.84%  | 95th MaxDD: 8.93%, Worst: 10.71%   |
| 2. Slippage Variation (Lognormal up to 3x)                  | Mean Ret: -16.58%, 95th DD: 18.28% | Mean Ret: -6.50%, 95th DD: 8.92%   |
| 3. Transaction Cost Variation (Fee inflation 1.0x - 3.0x)   | Mean Ret: -24.61%, Prob Neg: 100%  | Mean Ret: -9.86%, Prob Neg: 100%   |
| 4. Adverse Fills (5-15 bps penalty on every execution)      | Mean Ret: -24.95%, Prob Neg: 100%  | Mean Ret: -10.00%, Prob Neg: 100%  |
| 5. Delayed Execution Latency (2-10 bps execution drift)     | Mean Ret: -27.58%, Prob Neg: 100%  | Mean Ret: -11.44%, Prob Neg: 100%  |
| 6. Missed Trades (8% random order omission rate)            | Mean Ret: -14.60%, Prob Neg: 100%  | Mean Ret: -5.67%, Prob Neg: 100%   |
| 7. Regime Volatility Stress (20% adverse losing shocks)     | Mean Ret: -21.72%, 95th DD: 26.50% | Mean Ret: -8.89%, 95th DD: 12.05%  |
| 8. Parameter Perturbations (+/- 5% threshold jitter)        | Mean Ret: -15.83%, 95th DD: 17.72% | Mean Ret: -6.19%, 95th DD: 8.83%   |
| 9. Portfolio Simultaneous Loss (Correlated flash crash)     | Hit: 3.00% (Breaches 2% limit)     | Hit: 3.00% (Breaches 2% limit)     |
+-------------------------------------------------------------+------------------------------------+------------------------------------+
```

### Critical Vulnerabilities Identified:
1. **Fee & Latency Elasticity (Scenarios 3, 4, 5):** Under realistic institutional frictions (fee increases or 5–10 bps adverse slippage), net returns degrade rapidly. Control collapses to $-27.58\%$, and ADX25 collapses to $-11.44\%$. All candidates have a $100.0\%$ probability of negative return under fee stress.
2. **Regime Volatility Stress (Scenario 7):** When losing trades suffer wider stops during high-volatility regimes, drawdowns explode:
   - Control 95th percentile MaxDD reaches **$26.50\%$** (worst case: **$29.12\%$**).
   - 4H EMA 95th percentile MaxDD reaches **$23.79\%$** (worst case: **$25.36\%$**).
   - Both severely violate the 20% research gate.
3. **Correlated Flash Crash (Scenario 9):** Because the portfolio allows up to 4 concurrent positions with $0.5\%$ risk per trade (and up to $3\%$ total open portfolio risk), a simultaneous flash crash across all open positions results in an immediate **$3.0\%$ hit**, triggering the daily loss circuit breaker ($2.0\%$).

---

## 5. Methodological Audit: Destruction of Chronological Dependencies

### Mechanics of `simulate_randomized_trade_ordering`:
In `MonteCarloEngine.py:100`, the permutation logic is implemented as:
```python
shuffled_pnls = rng.permutation(pnls)
```
Where `pnls` is a 1-dimensional NumPy array containing the historical dollar PnLs of all completed trades across the 24-month backtest.

### Methodological Critique & Inherent Limitations:
The auditor confirms that trade-order permutation **destroys all real-world chronological dependencies**:
1. **Elimination of Volatility Clustering:** In real markets, periods of extreme volatility cluster together (Mandelbrot, 1963; Engle, 1982). Permuting trade PnLs distributes large losses uniformly across time, diluting severe localized clusters of consecutive stop-outs.
2. **Erasure of Macro & Market Regime Context:** A Donchian breakout strategy behaves differently in extended bull trends (e.g. BTC Q4 2024) compared to choppy mean-reverting ranges (e.g. summer 2025). Shuffling mixes trades from 2024 bull markets with 2025 range markets, destroying regime structure.
3. **Destruction of Multi-Asset Contemporaneous Correlation:** In a 7-asset portfolio, multiple assets frequently suffer stop-outs during the same market-wide liquidation event (e.g. crypto flash crashes or tech earnings sell-offs). Permuting trades individually uncouples these simultaneous losses, treating them as if they occurred weeks apart.

### Value and Proper Interpretation of the Permutation Test:
Despite these limitations, randomized trade ordering is a valid and informative stress test **if interpreted correctly**:
- It demonstrates that the backtest equity curve was fortuitously cushioned by favorable trade sequencing.
- When the identical set of trades is reordered, the likelihood of hitting the 10% production risk limit is **$100.00\%$** for Control and 4H EMA.
- If real-world volatility clustering were preserved, actual drawdown distributions would be **even worse** than reported by the IID shuffle.

---

## 6. Auditor Governance Conclusion

1. **Risk Characterization Correction:** The claim that candidates "passed" Monte Carlo evaluation with a "100% survival rate" must be formally qualified. While no path suffered complete bankruptcy ($\ge 50\%$ ruin), **Control and 4H EMA are fundamentally non-compliant with production risk parameters**, exhibiting a $100\%$ breach rate of the $10\%$ drawdown limit and exceeding the $20\%$ research limit in worst-case and regime-stressed paths.
2. **ADX25 Relative Merit:** ADX25 demonstrated genuine risk reduction, containing 95th percentile drawdowns to $8.93\%$ and limiting 10% breach probability to $0.80\%$. However, because its mean return remains negative ($-6.19\%$ baseline, $-9.86\%$ under fee stress), it remains economically unviable.
3. **Prohibition:** Quantitative risk reporting must never conflate "survival against catastrophic bankruptcy" with "compliance with operational drawdown mandates."
