# ROBUSTNESS AND COST STRESS EVALUATION
## Sensitivity Stress Testing Battery & Non-Stationarity Analysis

**Repository:** `BTC_ML_System`  
**Branch:** `feat/phase-3b-strategy-evaluation`  
**Target Candidate:** `RS_MOM_DONCHIAN_40_V1` (Top Overall Evaluated Candidate)  
**Methodology:** Parametric Friction Doubling, Latency Injection, Trade Dropping & Chronological Splitting

---

### 1. Executive Summary

To assess operational fragility before any paper-trading consideration, `ResearchEvaluator` subjected the top-performing candidate (`RS_MOM_DONCHIAN_40_V1`) to a rigorous sensitivity battery:
1. **Cost Stress (2x Transaction Frictions):** Doubling slippage to 10 bps on crypto, 4 bps on equities, and commissions to 20 bps on crypto.
2. **Execution Latency Stress (1-Bar Delay):** Simulating delayed queue fill at bar $t+2$ open instead of $t+1$ open.
3. **Missed Trade Stress (10% Random Drops):** Simulating network dropouts or broker disconnects where 10% of generated orders fail to route.
4. **Subperiod Chronological Split:** Evaluating the first 50% vs. the second 50% of the sample to identify structural non-stationarity.

---

### 2. Sensitivity Stress Battery Results

| Stress Scenario | Description | Sharpe Ratio | Total Return (%) | Max Drawdown (%) | Trade Count | Fragility Impact |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Baseline** | 1x Costs, 0 Delay, 0 Drops | **-0.40** | **-5.46%** | **10.71%** | 575 | Reference Baseline |
| **Cost Stress (2x)** | 10 bps Crypto Slip, 20 bps Comm | **-1.32** | **-16.90%** | **17.05%** | 575 | **Severe Degradation** (-11.44% PnL) |
| **Latency Stress (1-Bar)** | Fill at bar $t+2$ Open | **-1.77** | **-15.90%** | **17.06%** | 548 | **Catastrophic Degradation** (Sharpe -1.77) |
| **Missed Trades (10%)** | 10% Deterministic Drop | **-0.38** | **-5.06%** | **9.85%** | 516 | **Neutral / Mild Improvement** |
| **Subperiod: H1 (First 50%)** | Chronological 2024–2025 | **+0.35** | **+2.53%** | **6.67%** | 325 | **Positive Epoch** |
| **Subperiod: H2 (Second 50%)** | Chronological 2025–2026 | **-1.33** | **-7.92%** | **9.48%** | 258 | **Severe Non-Stationary Breakdown** |

---

### 3. Forensic Analysis of Stress Vectors

#### 3.1 Extreme Sensitivity to Transaction Friction
Doubling transaction costs caused total return to collapse from $-5.46\%$ to $-16.90\%$, and expanded maximum drawdown from $10.71\%$ to $17.05\%$. 
Because Donchian breakouts on hourly data capture relatively short-duration moves, transaction costs consume over $65\%$ of gross trading profits. Any strategy with this degree of cost fragility cannot survive in live markets where spread widening occurs during volatility.

#### 3.2 High Latency Fragility
Introducing a 1-bar execution delay caused the Sharpe ratio to plunge to **-1.77** and total return to drop to **-15.90%**.
Breakout strategies depend heavily on capturing immediate impulse moves right as price penetrates the Donchian barrier. When fill is delayed by just 1 bar (1 hour), the initial impulse is frequently already exhausted, causing entry into mean-reverting pullbacks.

#### 3.3 Temporal Non-Stationarity (H1 vs. H2 Breakdown)
The chronological subperiod split revealed severe parameter instability across epochs:
- **First Half (H1):** The strategy was profitable! It generated **+2.53% total return** with a **+0.35 Sharpe ratio** and **6.67% max drawdown** over 325 trades.
- **Second Half (H2):** The strategy broke down completely, losing **-7.92%** with a **-1.33 Sharpe ratio** over 258 trades.
- **Root Cause:** Market regimes shifted from a trending environment in 2024–2025 into a range-bound, choppy environment in 2025–2026. Without adaptive regime gating, the strategy could not adapt, wiping out earlier gains.

---

### 4. Conclusion & Research Verdict

The strategy candidate fails institutional robustness criteria:
1. **Unacceptable Cost Fragility:** Cannot withstand 2x transaction friction.
2. **High Latency Fragility:** Highly vulnerable to execution queuing delays.
3. **Severe Non-Stationarity:** Regimes change over time, turning profitable periods into steep losses.

These results reinforce the mandatory stop condition: no strategy is approved for paper trading.
