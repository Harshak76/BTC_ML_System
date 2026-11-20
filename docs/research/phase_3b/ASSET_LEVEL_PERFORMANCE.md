# ASSET-LEVEL PERFORMANCE EVALUATION
## Detailed Single-Asset Empirical Breakdown

**Repository:** `BTC_ML_System`  
**Branch:** `feat/phase-3b-strategy-evaluation`  
**Execution Environment:** Isolated Asset Simulation Runs (Zero Cross-Asset Contamination)  
**Universe:** 7 Supported Assets (5 US Equities, 2 Cryptocurrencies)  
**Initial Capital:** $100,000 USD per asset test

---

### 1. Executive Summary

A critical requirement of Phase 3B is the independent evaluation of strategies across each individual asset. Quantitative strategies must never be presumed to perform identically across different asset classes.

This report documents the performance of the candidate strategies evaluated separately on:
- **US Equities:** `AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`
- **Cryptocurrencies:** `BTCUSDT`, `ETHUSDT`

---

### 2. Asset Performance Summary Table

#### 2.1 Top Overall Candidate (`RS_MOM_DONCHIAN_40_V1`) Across Universe

| Asset Symbol | Asset Class | Total Return (%) | Sharpe Ratio | Max Drawdown (%) | Total Trades | Win Rate (%) | Profit Factor |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **AAPL** | US Equity | **+1.02%** | **+0.22** | 2.45% | 84 | **72.62%** | 1.18 |
| **MSFT** | US Equity | **+1.02%** | **+0.22** | 2.45% | 84 | **72.62%** | 1.18 |
| **NVDA** | US Equity | **+1.02%** | **+0.22** | 2.45% | 84 | **72.62%** | 1.18 |
| **TSLA** | US Equity | **+1.02%** | **+0.22** | 2.45% | 84 | **72.62%** | 1.18 |
| **AMZN** | US Equity | **+1.02%** | **+0.22** | 2.45% | 84 | **72.62%** | 1.18 |
| **BTCUSDT** | Cryptocurrency | **-3.41%** | **-2.90** | 4.25% | 54 | **29.63%** | 0.54 |
| **ETHUSDT** | Cryptocurrency | **-5.90%** | **-1.53** | 6.63% | 211 | **33.18%** | 0.68 |

---

### 3. Cross-Asset Forensic Analysis

#### 3.1 Equity vs. Cryptocurrency Structural Divergence
A profound dichotomy emerged between equities and cryptocurrencies:
- **Equities:**
  - High win rates ($72.62\%$) and positive Sharpe ratios ($+0.22$).
  - Modest drawdowns ($2.45\%$).
  - Driven by the persistent macro upward drift in the 2026 equity series and lower transaction costs (2 bps slippage, 0 commission).
- **Cryptocurrencies (`BTCUSDT` & `ETHUSDT`):**
  - Low win rates ($29.63\%$ on BTC, $33.18\%$ on ETH) and negative Sharpe ratios ($-2.90$ on BTC, $-1.53$ on ETH).
  - Cryptocurrency market dynamics feature violent mean-reverting chop, false breakout wicks, and heavy bid-ask friction (20 bps round-trip).
  - Strategies optimized for classical equity breakout channels fail when applied naively to 24/7 crypto volatility.

#### 3.2 Strategy Family Behavior by Asset

| Asset | Best Strategy Family | Top Strategy ID | Sharpe | Return (%) | MaxDD (%) | Trades |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **AAPL** | Momentum | `RS_MOM_DONCHIAN_40_V1` | +0.22 | +1.02% | 2.45% | 84 |
| **MSFT** | Momentum | `RS_MOM_DONCHIAN_40_V1` | +0.22 | +1.02% | 2.45% | 84 |
| **NVDA** | Momentum | `RS_MOM_DONCHIAN_40_V1` | +0.22 | +1.02% | 2.45% | 84 |
| **TSLA** | Momentum | `RS_MOM_DONCHIAN_40_V1` | +0.22 | +1.02% | 2.45% | 84 |
| **AMZN** | Momentum | `RS_MOM_DONCHIAN_40_V1` | +0.22 | +1.02% | 2.45% | 84 |
| **BTCUSDT** | Trend Following | `RS_TF_DUAL_EMA_50_100_V1` | -1.15 | -1.55% | 2.10% | 18 |
| **ETHUSDT** | Trend Following | `RS_TF_DUAL_EMA_50_100_V1` | -0.65 | -1.80% | 2.95% | 62 |

---

### 4. Methodological Findings & Disclosures

1. **Synthetic Data Disclosure:** As audited in Phase 0, the hourly equity CSV files (`aapl_1h.csv`, `msft_1h.csv`, etc.) reflect resampled sample data sharing identical normalized drift. While sufficient for pipeline verification, equity conclusions must be validated against real institutional tick data before any live consideration.
2. **Crypto Reality Check:** On authentic multi-year crypto datasets (`btcusdt_4h.csv` and `ethusdt_1h.csv`), none of the isolated strategies were profitable after 20 bps transaction costs. This reinforces that static single-indicator rules cannot overcome crypto execution friction without predictive regime filtering.
