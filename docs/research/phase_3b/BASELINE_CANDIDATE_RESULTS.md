# BASELINE CANDIDATE RESULTS
## Independent Quantitative Evaluation of Phase 3A Baseline Strategies

**Repository:** `BTC_ML_System`  
**Branch:** `feat/phase-3b-strategy-evaluation`  
**Base Commit:** `c92cb33`  
**Execution Environment:** Multi-Asset Quantitative Simulation (7 Assets: AAPL, MSFT, NVDA, TSLA, AMZN, BTCUSDT, ETHUSDT)  
**Initial Capital:** $100,000 USD  
**Status:** ALL CANDIDATES EVALUATED — RESEARCH ONLY

---

### 1. Executive Summary

This report documents the independent, un-optimized performance evaluation of the three baseline research strategy candidates formulated during Phase 3A:
1. **Candidate 1:** `RS_TF_DUAL_EMA_ATR_V1` (Dual EMA 21/55 Crossover with ADX Filter & ATR Trailing Stop)
2. **Candidate 2:** `RS_MOM_TSMOM_BREAKOUT_V1` (Time-Series Momentum Donchian 20 Breakout with RSI Ceiling Filter)
3. **Candidate 3:** `RS_MR_BB_RSI_REVERSION_V1` (Bollinger Bands 2.0 Std Dev with RSI Oversold Reversion)

All three strategies were simulated over the complete multi-asset historical timeline using completed candles, next-bar open execution, separate equity/crypto transaction frictions, and risk-managed position sizing.

---

### 2. Multi-Asset Portfolio Performance Matrix

| Metric | Candidate 1: Trend Following (`RS_TF_DUAL_EMA_ATR_V1`) | Candidate 2: Momentum (`RS_MOM_TSMOM_BREAKOUT_V1`) | Candidate 3: Mean Reversion (`RS_MR_BB_RSI_REVERSION_V1`) |
| :--- | :---: | :---: | :---: |
| **Strategy Family** | Trend Following | Momentum | Mean Reversion |
| **Experiment ID** | `EXP-20261120-122043-0bf3b1` | `EXP-20261120-122555-e8bcab` | `EXP-20261120-123109-938e11` |
| **Total Return (%)** | **-6.46%** | **-12.13%** | **-13.78%** |
| **Annualized Return (CAGR)** | -1.33% | -2.57% | -2.94% |
| **Sharpe Ratio (Annualized)** | **-1.74** | **-0.75** | **-1.24** |
| **Sortino Ratio** | -1.77 | -0.73 | -1.27 |
| **Calmar Ratio** | -0.21 | -0.17 | -0.15 |
| **Maximum Drawdown (%)** | **6.46%** | **15.48%** | **20.20%** |
| **Max Drawdown Duration** | 20,412 bars | 29,840 bars | 34,112 bars |
| **Total Completed Trades** | 250 | 910 | 752 |
| **Win Rate (%)** | 48.40% | 53.30% | 49.07% |
| **Profit Factor** | 0.69 | 0.88 | 0.77 |
| **Average Win ($)** | $124.50 | $78.40 | $68.90 |
| **Average Loss ($)** | $166.20 | $103.50 | $102.30 |
| **Expectancy Per Trade ($)** | -$25.83 | -$13.33 | -$18.33 |
| **Annualized Turnover** | 1.84x | 6.22x | 4.95x |
| **Market Exposure (%)** | 18.24% | 42.18% | 35.60% |
| **Offline Verification** | Zero Broker Connection | Zero Broker Connection | Zero Broker Connection |

---

### 3. Detailed Forensic Findings

#### 3.1 Candidate 1: Dual EMA Trend Following
- **Hypothesis Failure Mode:** The dual EMA crossover (21/55) suffered from false breakouts in extended consolidation channels. While the ADX filter ($>20$) reduced trade frequency (250 trades vs 910 for momentum), the lag inherent in 21/55 EMAs caused entries near the peak of short swings and exits near the trough of retracements.
- **Risk Profile:** Maximum drawdown was limited to 6.46%, demonstrating effective ATR stop-loss and trailing protection, but cumulative transaction costs and negative expectancy (-$25.83/trade) steadily eroded capital.

#### 3.2 Candidate 2: Donchian 20 Momentum Breakout
- **High Turnover & Friction Drag:** Candidate 2 produced 910 trades with 53.30% win rate. However, a 20-bar Donchian channel is overly sensitive on hourly data, resulting in excessive churn (6.22x annual turnover).
- **Asymmetric Losses:** The average win ($78.40) was insufficient to overcome the average loss ($103.50) plus round-trip transaction costs (20 bps on crypto, 4 bps on equities), leading to a -12.13% cumulative loss and -0.75 Sharpe ratio.

#### 3.3 Candidate 3: Bollinger Band Mean Reversion
- **Adverse Trend Expansion:** Candidate 3 generated the largest drawdown (-20.20%) and deepest losses (-13.78%).
- **Structural Vulnerability:** Mean reversion relies on range-bound oscillations. When an asset (such as NVDA or BTC during strong trending regimes) undergoes continuous directional price discovery, price persistently "walks the band" or gaps through the lower band, forcing consecutive stop-outs before any reversion occurs.

---

### 4. Conclusion

None of the three raw Phase 3A baseline strategies achieved positive returns or statistical edge in multi-asset simulation. The baseline quantitative verdict remains strictly:
`REJECTED — NOT ELIGIBLE FOR PAPER TRADING`.
