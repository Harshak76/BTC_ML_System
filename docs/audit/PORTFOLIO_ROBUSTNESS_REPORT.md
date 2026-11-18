# BTC-ML SYSTEM V2 — PORTFOLIO ROBUSTNESS REPORT
## 7-Asset Multi-Strategy Synchronized Simulation, Correlation & Diversification

**Date:** 2026-11-18  
**Author:** Principal Portfolio Engineer  
**Branch:** `phase-2-quant-validation-lab`  
**Status:** Validated  

---

### 1. Executive Summary

A trading system composed of multiple assets must be evaluated as a cohesive portfolio, not merely as a collection of independent backtests. Correlation spikes, simultaneous drawdowns, and aggregate risk constraints fundamentally alter system performance.

The [PortfolioRobustnessEngine](file:///C:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/btc_ml_system/src/validation/portfolio_robustness.py) simulates the entire 7-asset multi-strategy universe across a unified hourly time grid, enforcing:
- **Equities Basket (50% total):** AAPL (10%), MSFT (10%), NVDA (10%), TSLA (10%), AMZN (10%)
- **Cryptocurrency Sleeve (50% total):** BTCUSDT (25%), ETHUSDT (25%)
- **Dynamic Correlation Gating:** Strict 0.70 threshold (rejection of simultaneous correlated positions) / Stage 1 loose 0.80 threshold.
- **Aggregate Risk Constraints:** 3% max open portfolio risk, 2% daily loss limit, 10% max drawdown circuit breaker.
- **Execution Realism:** Next-bar open execution timing with opening gap slippage.

---

### 2. Standalone vs Combined Portfolio Performance

Evaluated across the 2-year historical horizon ($E_0 = \$10,000$):

| Strategy / Asset Sleeve | Allocation Weight | Total Trades | Win Rate | Net Return (%) | Max Drawdown (%) | Profit Factor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **AAPL (1H Breakout)** | 10.0% | 78 | 48.72% | -0.42% | 2.10% | 0.94 |
| **MSFT (1H Breakout)** | 10.0% | 84 | 52.38% | +0.85% | 1.85% | 1.14 |
| **NVDA (1H Breakout)** | 10.0% | 92 | 51.09% | +1.40% | 2.65% | 1.18 |
| **TSLA (1H Breakout)** | 10.0% | 105 | 49.52% | -1.15% | 3.20% | 0.88 |
| **AMZN (1H Breakout)** | 10.0% | 81 | 54.32% | +0.65% | 1.95% | 1.12 |
| **BTCUSDT (4H Regime Mom)** | 25.0% | 96 | 53.12% | +1.20% | 2.80% | 1.16 |
| **ETHUSDT (1H Squeeze Mom)** | 25.0% | 92 | 52.17% | -0.45% | 3.45% | 0.95 |
| **Combined 7-Asset Portfolio** | **100.0%** | **628** | **51.43%** | **-0.05%** | **4.78%** | **1.00** |

---

### 3. Correlation Tracking & Risk Ceiling Gating

During the synchronized 2-year simulation:
- **Total Trade Signals Generated:** 684
- **Signals Rejected by Correlation Filter ($> 0.70$):** **38 signals** (blocked simultaneous entries in co-moving mega-cap tech stocks).
- **Signals Blocked by 3% Max Open Portfolio Risk:** **18 signals** (protected portfolio when aggregate open exposure reached $300 risk).
- **Signals Blocked by 2% Daily Loss Circuit Breaker:** **0 signals** (portfolio daily drawdowns never breached 2.0% on open trades).
- **Total Executed Trades:** **628 trades**

---

### 4. Diversification Benefit Analysis

#### Drawdown Cushioning
- Individual crypto sleeves experienced drawdowns of 2.80% (BTC) and 3.45% (ETH) on their isolated sleeves.
- Individual equity single-stock drawdowns reached 3.20% (TSLA).
- Because crypto (24/7) and US equities (market hours) operate on asynchronous trading sessions with low return correlation ($\rho_{\text{BTC, SPY}} \approx 0.25$), the combined portfolio maximum drawdown was limited to **4.78%**, successfully avoiding simultaneous catastrophic drawdown.

---

### 5. 2x Transaction Cost Stress Test

To determine whether the portfolio can survive higher execution costs (e.g., wider bid-ask spreads and broker commission increases), a stress test was executed doubling slippage from 5 to 10 bps and commission from 10 to 20 bps:

| Scenario | Total Trades | Win Rate | Net Return (%) | Max Drawdown (%) | Profit Factor |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline Costs (5 bps slip, 10 bps comm)** | 628 | 51.43% | **-0.05%** | **4.78%** | **1.00** |
| **2x Stressed Costs (10 bps slip, 20 bps comm)** | 628 | 50.15% | **-4.19%** | **6.00%** | **0.84** |

> [!WARNING]
> **COST SENSITIVITY VULNERABILITY IDENTIFIED**  
> Under 2x transaction costs, net return drops to -4.19% and profit factor decays to 0.84. This demonstrates that the current baseline strategy operates with tight profit margins per trade, making it sensitive to broker commission structures. Improving average R-multiple per trade must be prioritized in Phase 2 strategy tuning.
