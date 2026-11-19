# PHASE 2.1 — MONTE CARLO SIMULATION & STRESS TESTING AUDIT REPORT

**Audit Date:** November 19, 2026  
**Auditor:** Quantitative Risk & Software Verification Engine  
**Target Repository:** `BTC_ML_System`  
**Target Module:** `btc_ml_system/src/validation/monte_carlo.py`  
**Experiment File Audited:** `btc_ml_system/experiments/EXP-20261118-171823-104f2f.json`  
**Status:** `VERIFIED WITH LIMITATIONS`  

---

## 1. Executive Summary

We independently audited the Monte Carlo stress testing suite implemented in `src/validation/monte_carlo.py`, which subjects the trading system to path-dependent and execution friction perturbations.

Experiment `EXP-20261118-171823-104f2f` documented results across 7 primary operational scenarios. Our forensic review confirms that the simulation calculations are **empirically accurate**. Most critically, the simulations prove that the current strategy is exceptionally fragile: doubling transaction costs causes the strategy to lose money in **99.2%** of simulated regimes, and modest adverse fills cause a loss in **100.0%** of runs.

---

## 2. Forensic Audit of All 7 Documented Scenarios

### Scenario 1: Randomized Trade Ordering
- **Mechanism:** Permutes the chronological order of the 628 trades 1,000 times without replacement.
- **Reported Metrics:**
  - Median Max DD: 2.58%
  - 95th Percentile Max DD: 3.83%
  - Worst Case Max DD: 5.44%
  - CVaR DD (95%): 4.23%
  - Final Equity P5/P50/P95: \$100,109.15 (Identical across all runs because sum of trade PnLs without compounding is order-invariant).
- **Audit Verification:** Verified correct. Max DD distribution reflects purely path-dependent clustering of losing trades.

### Scenario 2: Execution Slippage Variation
- **Mechanism:** Adds stochastic log-normal slippage shocks (0 to 15 bps per side).
- **Reported Metrics:**
  - Mean Return: -0.41%
  - 5th Percentile Return: -0.59%
  - 95th Percentile Max DD: 5.11%
  - Probability of Negative Return: **100.0%**
- **Audit Verification:** Confirms that even minor slippage expansion wipes out the baseline flat return (-0.05%) entirely.

### Scenario 3: Transaction Cost Variation (1.0x – 3.0x)
- **Mechanism:** Multiplies base fees (10 bps) and slippage (5 bps) by a uniform multiplier in $[1.0, 3.0]$.
- **Reported Metrics:**
  - Mean Return: -5.93%
  - 5th Percentile Return: -11.69%
  - Probability of Negative Return: **99.2%**
  - **At exactly 2.0x Costs:** Net Return = **-4.19%**
- **Audit Verification:** Verified. The strategy cannot clear realistic institutional execution costs.

### Scenario 4: Adverse Fills Penalty
- **Mechanism:** Applies deterministic adverse fill penalty of 5 to 15 bps on all market orders.
- **Reported Metrics:**
  - Mean Return: -6.17%
  - 5th Percentile Return: -8.94%
  - Probability of Negative Return: **100.0%**
- **Audit Verification:** Demonstrates complete lack of alpha margin.

### Scenario 5: Missed Trades (8% Omission)
- **Mechanism:** Randomly drops 8% of trade signals to simulate broker API disconnections, network latency, or server restarts.
- **Reported Metrics:**
  - Mean Return: +0.085%
  - 5th Percentile Return: -1.07%
  - Probability of Negative Return: 45.4%
- **Audit Verification:** Verified. Interestingly, missing trades slightly *improved* the average return because the strategy generates negative expected value per trade.

### Scenario 6: Regime Volatility Stress (20% Adverse Shocks)
- **Mechanism:** Amplifies adverse market bars by 20% to simulate flash-crashes and high-volatility regimes.
- **Reported Metrics:**
  - Mean Return: -2.22%
  - 95th Percentile Max DD: 6.75%
  - Worst Case DD: 7.40%
- **Audit Verification:** Verified. Drawdown expands from 4.78% to 7.40%, remaining under the 10.0% portfolio threshold.

### Scenario 7: Portfolio Simultaneous Loss (Correlated Flash Shock)
- **Mechanism:** Tests simultaneous maximum position stops across all 7 assets during a systemic liquidity shock.
- **Reported Metrics:**
  - Simultaneous Portfolio Hit: 3.00%
  - Daily Loss Limit Threshold: 2.00%
  - Daily Loss Circuit Breaker Triggered: **TRUE**
  - Safety Mechanism Verified: Freezes all trade entries immediately for remainder of day.
- **Audit Verification:** Verified. Confirms that the risk engine's circuit breaker triggers as designed.

---

## 3. Methodological Limitations

1. **Trade Shuffling Assumption:**
   - Shuffling trade returns assumes independence across trades. In reality, losing trades cluster during bear market regimes or periods of high cross-asset correlation.
2. **Static Position Sizing in Resampling:**
   - The simulation resampled trade dollar PnLs rather than percentage returns applied to dynamic capital. While acceptable for fixed-risk unit sizing, it underestimates drawdown compounding under geometric compounding.

---

## 4. Impact on Validation Gate

The validation gate evaluates:
- **Monte Carlo 95th Percentile Drawdown:** Observed 3.83% vs $\le 10.0\%$ limit $\implies$ **PASS**.
- **2x Transaction Cost Stress Test:** Observed Return = -4.19% vs $> 0.0\%$ limit $\implies$ **FAIL**.

---

## 5. Audit Classification

- **Classification:** `VERIFIED WITH LIMITATIONS`
- **Impact on Pre-Paper-Trading Gate:** **CRITICAL FAIL CONFIRMED**.
- **Conclusion:** The Monte Carlo simulations provide conclusive quantitative evidence that the current strategy is not economically viable.
