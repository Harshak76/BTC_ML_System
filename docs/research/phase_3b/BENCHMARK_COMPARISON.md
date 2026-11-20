# BENCHMARK COMPARISON
## Strategy Candidates vs. Simple Reference Baselines

**Repository:** `BTC_ML_System`  
**Branch:** `feat/phase-3b-strategy-evaluation`  
**Reference Baselines:** Buy-and-Hold, Cash Baseline, Simple SMA(50) Trend Benchmark  
**Execution Frictions:** Identical slippage and commissions applied to active benchmarks

---

### 1. Executive Summary

A disciplined quantitative evaluation must compare candidate trading strategies against simple, low-turnover, and zero-parameter benchmarks:
1. **Buy-and-Hold (B&H):** Fully invested from bar 0 to terminal bar, absorbing all drawdowns.
2. **Cash Baseline:** 100% cash allocation (0% return, 0% drawdown, risk-free baseline).
3. **SMA(50) Trend Benchmark:** Classical moving-average trend following (Long when $\text{Close} > \text{SMA}(50)$, flat otherwise) executed at next-bar open with realistic transaction costs.

---

### 2. Comprehensive Benchmark Comparison Table

| Asset Symbol | Benchmark / Strategy | Total Return (%) | Sharpe Ratio | Max Drawdown (%) | Exposure (%) | Turnover |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **AAPL** | **Buy & Hold** | **+343.03%** | **1.09** | 70.79% | 100.0% | 0.00x |
| | **SMA(50) Trend** | **+341.65%** | **1.29** | **37.09%** | 68.4% | 1.42x |
| | **Cash Baseline** | 0.00% | 0.00 | **0.00%** | 0.0% | 0.00x |
| | Top Candidate (`RS_MOM_DONCHIAN_40`) | +1.02% | 0.22 | 2.45% | 18.2% | 0.85x |
| **BTCUSDT** | **Buy & Hold** | **+35.80%** | **1.13** | 53.45% | 100.0% | 0.00x |
| | **Cash Baseline** | 0.00% | 0.00 | **0.00%** | 0.0% | 0.00x |
| | **SMA(50) Trend** | -20.06% | -0.48 | 52.22% | 54.2% | 3.84x |
| | Top Candidate (`RS_MOM_DONCHIAN_40`) | -3.41% | -2.90 | **4.25%** | 12.5% | 0.72x |
| **ETHUSDT** | **Buy & Hold** | **+7.71%** | **0.39** | 69.15% | 100.0% | 0.00x |
| | **Cash Baseline** | 0.00% | 0.00 | **0.00%** | 0.0% | 0.00x |
| | **SMA(50) Trend** | -64.22% | -0.95 | 73.97% | 51.8% | 4.12x |
| | Top Candidate (`RS_MOM_DONCHIAN_40`) | -5.90% | -1.53 | **6.63%** | 14.1% | 1.15x |

---

### 3. Quantitative Analysis & Benchmark Disclosures

#### 3.1 SMA(50) Trend Benchmark vs. Complex Strategies
- **On Equities:** The simple SMA(50) trend benchmark was remarkably efficient: it captured $+341.65\%$ total return with a **1.29 Sharpe ratio**, nearly matching Buy-and-Hold return ($+343.03\%$) while slashing maximum drawdown in half (from $70.79\%$ to $37.09\%$).
- **On Cryptocurrencies:** Conversely, SMA(50) on crypto suffered severe whipsaw losses ($-20.06\%$ on BTC, $-64.22\%$ on ETH). High turnover in choppy crypto regimes subjected the simple SMA to massive friction bleed.

#### 3.2 Strategy Risk Management vs. Buy-and-Hold
- While Buy-and-Hold achieved positive headline returns on BTC ($+35.8\%$) and ETH ($+7.7\%$), it did so at the expense of unacceptable drawdown:
  - BTC B&H Max Drawdown: **53.45%**
  - ETH B&H Max Drawdown: **69.15%**
- In contrast, the candidate strategies (`RS_MOM_DONCHIAN_40_V1` and `RS_TF_DUAL_EMA_50_100_V1`) strictly capped drawdowns to **2.1% - 6.6%** through disciplined ATR stops and position sizing.
- However, capital preservation alone is not sufficient; strategies must demonstrate positive net expectancy over the cash baseline to warrant operational deployment.

#### 3.3 Cash Baseline Dominance
Because all 9 candidate strategies produced negative net portfolio returns (ranging from $-1.54\%$ to $-15.83\%$), the **Cash Baseline (0.0% return, 0.0% drawdown)** strictly outperformed every candidate strategy at the portfolio level on a risk-adjusted basis.

---

### 4. Conclusion

The benchmark analysis demonstrates that complex indicator combinations do not automatically beat simpler baselines. Complex breakout and mean-reversion rules suffered from excessive trading friction. For Phase 3C, strategies must incorporate structural trend filters (like SMA 50/200) to avoid entering counter-trend trades.
