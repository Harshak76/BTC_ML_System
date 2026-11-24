# BTC-ML SYSTEM V2 — PHASE 3C MONTE CARLO REPORT
## Institutional Stress Testing & Fragility Analysis Across 9 Scenarios

- **Date:** 2026-11-24
- **Auditor:** Senior Quantitative Researcher & Backtesting Auditor
- **Repository Branch:** `feat/phase-3c-controlled-filter-experiment`
- **Simulations:** 1,000 paths per scenario (Random Seed: 42)
- **Engine:** `btc_ml_system.src.validation.monte_carlo.MonteCarloEngine`
- **Mandatory Disclosure:**
  > **`HISTORICAL EXPLORATORY EVALUATION — PRIOR DATASET INSPECTION DISCLOSED`**  
  > Evaluated on historical data with prior inspection disclosed.

---

## 1. STRESS SCENARIO ARCHITECTURE

To evaluate structural robustness against real-world execution shocks, each candidate was subjected to institutional Monte Carlo stress scenarios:
1. **Randomized Trade Ordering:** Tests sequence path-dependency and worst-case drawdown accumulation.
2. **Slippage Variation:** Applies lognormal stochastic slippage shocks up to 3x baseline levels.
3. **Fee Inflation (1.0x to 3.0x):** Tests resilience against exchange/broker fee increases.
4. **Adverse Fills:** Incurs a fixed 5–15 bps execution penalty on every fill.
5. **Delayed Execution:** Stochastically delays orders by 1 additional bar.
6. **Missed Trades (8% Dropout):** Simulates API disconnects, liquidity gaps, or dropped signals.

---

## 2. EMPIRICAL STRESS TEST RESULTS

| Scenario / Metric | Control (`DONCHIAN_40`) | ADX Treatment (`ADX25`) | 4H EMA Treatment |
|---|---|---|---|
| **Shuffle: 95th Percentile MaxDD** | **$13.83\%$** | **$8.38\%$** | **$14.50\%$** |
| **Shuffle: Worst-Case MaxDD** | **$16.86\%$** | **$10.25\%$** | **$17.27\%$** |
| **Fee Inflation (1x–3x): Mean Return** | **$-18.36\%$** | **$-8.10\%$** | **$-19.14\%$** |
| **Fee Inflation: Prob. Negative Return** | **$100.00\%$** | **$100.00\%$** | **$100.00\%$** |
| **Slippage Stress: Mean Return** | **$-10.33\%$** | **$-4.63\%$** | **$-11.99\%$** |
| **Slippage Stress: 95th MaxDD** | **$13.90\%$** | **$7.51\%$** | **$13.38\%$** |
| **Adverse Fills: Mean Return** | **$-18.70\%$** | **$-8.25\%$** | **$-19.45\%$** |
| **Adverse Fills: Prob. Negative Return** | **$100.00\%$** | **$100.00\%$** | **$100.00\%$** |
| **Missed Trades (8%): Mean Return** | **$-8.80\%$** | **$-3.89\%$** | **$-10.47\%$** |
| **Missed Trades: Prob. Negative Return** | **$100.00\%$** | **$100.00\%$** | **$100.00\%$** |

---

## 3. FRAGILITY & SENSITIVITY ANALYSIS

### 1. Fee Elasticity
- The Control candidate's loss expands rapidly from $-9.57\%$ to **$-18.36\%$** under fee inflation, demonstrating high fee fragility due to excessive trade turnover (913 trades).
- The ADX filter exhibits substantially lower fee sensitivity: loss increases from $-4.30\%$ to **$-8.10\%$**, owing to its $56.7\%$ lower trade volume.
- However, under 2x fee stress, **$100.0\%$ of simulated paths produce net losses** across all three strategies.

### 2. Path Dependency & Worst-Case Drawdowns
- Under trade reshuffling, the worst-case maximum drawdown was:
  - Control: $16.86\%$
  - ADX25: $10.25\%$
  - 4H EMA: $17.27\%$
- None of the candidates suffered mathematical capital ruin (equity $< 50\%$ initial capital), meaning all three technically survived catastrophic ruin.

---

## 4. GATE 6 EVALUATION: MONTE CARLO SURVIVAL RATE > 95%

- **Survival Definition:** Maintaining equity above $50\%$ of initial capital (no ruin) under 2x cost inflation and random dropouts.
- **Control:** Zero ruin events observed (100% survival above 50% capital).
- **ADX25:** Zero ruin events observed (100% survival above 50% capital).
- **4H EMA:** Zero ruin events observed (100% survival above 50% capital).
- **Gate 6 Status:** **PASSED** (all candidates survived without catastrophic ruin, though all exhibited negative expected returns).
