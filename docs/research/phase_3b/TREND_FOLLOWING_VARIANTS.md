# TREND FOLLOWING VARIANTS
## Controlled Expansion & Sensitivity Analysis

**Repository:** `BTC_ML_System`  
**Branch:** `feat/phase-3b-strategy-evaluation`  
**Strategy Family:** Trend Following (Dual EMA Crossover with ADX Filter & ATR Risk Limits)  
**Universe:** Multi-Asset Portfolio (AAPL, MSFT, NVDA, TSLA, AMZN, BTCUSDT, ETHUSDT)

---

### 1. Pre-Registered Variant Hypotheses

To evaluate the structural stability of the trend-following hypothesis rather than curve-fitting, three pre-registered variants were tested:
1. **Variant 1 (Baseline):** `RS_TF_DUAL_EMA_21_55_V1` — Fast EMA 21, Slow EMA 55 (Intermediate trend window).
2. **Variant 2:** `RS_TF_DUAL_EMA_20_50_V1` — Fast EMA 20, Slow EMA 50 (Standard classical moving average window).
3. **Variant 3:** `RS_TF_DUAL_EMA_50_100_V1` — Fast EMA 50, Slow EMA 100 (Long-term smoothed macroeconomic trend filter).

All variants maintained identical confirmation rules:
- ADX(14) $\ge 20.0$ trend strength filter.
- ATR(14) stop-loss multiplier: 2.0x ATR.
- Take-profit multiplier: 4.0x ATR.
- Trailing stop: 2.5% trailing from highest high.

---

### 2. Quantitative Performance Comparison

| Performance Metric | Variant 1 (EMA 21/55) | Variant 2 (EMA 20/50) | Variant 3 (EMA 50/100) |
| :--- | :---: | :---: | :---: |
| **Strategy ID** | `RS_TF_DUAL_EMA_21_55_V1` | `RS_TF_DUAL_EMA_20_50_V1` | `RS_TF_DUAL_EMA_50_100_V1` |
| **Experiment ID** | `EXP-20261120-122043-0bf3b1` | `EXP-20261120-122229-5ae3d7` | `EXP-20261120-122415-5dac6e` |
| **Total Return (%)** | **-6.46%** | **-6.82%** | **-1.54%** |
| **Annualized Return (CAGR)** | -1.33% | -1.41% | **-0.31%** |
| **Sharpe Ratio** | **-1.74** | **-1.61** | **-0.44** |
| **Sortino Ratio** | -1.77 | -1.63 | -0.42 |
| **Calmar Ratio** | -0.21 | -0.20 | -0.11 |
| **Max Drawdown (%)** | 6.46% | 7.00% | **2.76%** |
| **Completed Trades** | 250 | 272 | **158** |
| **Win Rate (%)** | 48.40% | 48.16% | **56.33%** |
| **Profit Factor** | 0.69 | 0.70 | **0.87** |
| **Expectancy Per Trade** | -$25.83 | -$25.07 | **-$9.77** |
| **Annualized Turnover** | 1.84x | 1.98x | **1.12x** |
| **Exposure (%)** | 18.24% | 19.50% | **12.45%** |

---

### 3. Quantitative Analysis & Parameter Sensitivity

#### 3.1 Impact of Lookback Extension (50/100 EMA)
- **Noise Attenuation:** Extending lookback from 21/55 to 50/100 reduced trade frequency by $36.8\%$ (158 trades vs. 250 trades) and cut annualized turnover almost in half (1.12x vs. 1.84x).
- **Drawdown Compression:** Maximum drawdown compressed from $6.46\%$ down to $2.76\%$, the lowest drawdown of any evaluated candidate across the entire research phase.
- **Sharpe Ratio Improvement:** The Sharpe ratio improved substantially from $-1.74$ to $-0.44$, and win rate rose from $48.4\%$ to $56.3\%$.

#### 3.2 Classical vs. Fibonacci Window (20/50 vs. 21/55)
- Variants 1 and 2 performed almost identically:
  - Total return: $-6.46\%$ vs. $-6.82\%$
  - Sharpe ratio: $-1.74$ vs. $-1.61$
  - Win rate: $48.40\%$ vs. $48.16\%$
- This demonstrates that minor parameter tweaks between 20/50 and 21/55 do not alter the underlying statistical distribution. The primary driver of performance is timeframe smoothing, not isolated integer selection.

---

### 4. Recommendation for Phase 3C

The 50/100 EMA configuration (`RS_TF_DUAL_EMA_50_100_V1`) demonstrated superior risk preservation and noise reduction. While insufficient as a standalone trading model, its low turnover and $2.76\%$ max drawdown make it an attractive candidate for multi-timeframe trend qualification in Phase 3C multi-factor ensembles.
