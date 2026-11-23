# CORRECTED CANDIDATE RESULTS REPORT
## Phase 3B.2 Portfolio-Level Revalidation Across Authentic Multi-Asset Universe

**Repository:** `BTC_ML_System`  
**Branch:** `fix/phase-3b-2-data-integrity`  
**Execution Environment:** Isolated Offline Multi-Asset Simulation  
**Universe:** 5 Authentic US Equities (`AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`) & 2 Cryptocurrencies (`BTCUSDT`, `ETHUSDT`)  
**Initial Capital:** $100,000 USD | Common Steps: $T = 20,424$ hourly bars  
**Audit Verdict:** `REJECTED — NOT ELIGIBLE FOR PAPER TRADING`

---

### 1. Executive Summary

All nine pre-registered candidate strategies were re-evaluated on the corrected, authentic multi-asset dataset using the remediated execution engine. No strategy parameters were altered.

Every strategy candidate generated a **negative annualized Sharpe ratio** and **negative net total return** at the portfolio level. As observed in Phase 3B, unconditioned trend, momentum, and mean-reversion strategies fail to overcome market frictions without predictive regime gating.

---

### 2. Corrected Candidate Performance Table

| Strategy ID | Family | Description | Sharpe Ratio | Total Return (%) | Max Drawdown (%) | Trade Count | Win Rate (%) | Profit Factor | Turnover |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `RS_TF_DUAL_EMA_21_55_V1` | Trend | Dual EMA (21/55) with ATR Channel | **-1.35** | **-8.21%** | 8.54% | 557 | 44.3% | 0.78 | 1.84x |
| `RS_TF_DUAL_EMA_20_50_V1` | Trend | Dual EMA (20/50) with ATR Channel | **-1.44** | **-9.35%** | 11.56% | 592 | 41.7% | 0.76 | 2.01x |
| `RS_TF_DUAL_EMA_50_100_V1` | Trend | Dual EMA (50/100) with ATR Channel | **-1.34** | **-5.94%** | **7.48%** | **293** | **43.7%** | **0.71** | **0.95x** |
| `RS_MOM_DONCHIAN_20_V1` | Momentum | Donchian 20 Breakout & RSI Ceiling | **-1.64** | **-18.07%** | 21.35% | 1,457 | 39.1% | 0.82 | 4.85x |
| `RS_MOM_DONCHIAN_40_V1` | Momentum | Donchian 40 Breakout & RSI Ceiling | **-1.11** | **-9.57%** | **13.22%** | **913** | **41.5%** | **0.85** | **3.12x** |
| `RS_MOM_DONCHIAN_55_V1` | Momentum | Donchian 55 Breakout & RSI Ceiling | **-1.12** | **-8.54%** | 10.35% | 735 | 41.6% | 0.83 | 2.54x |
| `RS_MR_BB_RSI_20_STD_V1` | Mean Rev | Bollinger Band (2.0 std) RSI Reversion | **-2.90** | **-31.47%** | 33.42% | 1,680 | 43.1% | 0.70 | 5.62x |
| `RS_MR_BB_RSI_22_STD_V1` | Mean Rev | Bollinger Band (2.2 std) RSI Reversion | **-2.46** | **-22.48%** | 23.90% | 1,152 | 43.8% | 0.70 | 3.84x |
| `RS_MR_BB_RSI_25_STD_V1` | Mean Rev | Bollinger Band (2.5 std) RSI Reversion | **-1.66** | **-12.58%** | **14.20%** | **640** | **42.2%** | **0.72** | **2.10x** |

---

### 3. Key Quantitative Findings

#### 3.1 Top Portfolio Candidate: `RS_MOM_DONCHIAN_40_V1`
- Generated the highest Sharpe ratio among all 9 candidates: **-1.11** (periodic Sharpe: -0.0142).
- Limited total portfolio drawdown to **13.22%** over 913 trades with a 41.5% win rate and 0.85 profit factor.
- Compared to Phase 3B (where synthetic equity clones gave an artificially high win rate of 55.5%), authentic multi-asset evaluation reveals the true drag of choppy equity and crypto regimes.

#### 3.2 Trend Following Smoothing: `RS_TF_DUAL_EMA_50_100_V1`
- Lowest portfolio drawdown: **7.48%** with lowest turnover (**0.95x** annual turnover across 293 trades).
- Total return: **-5.94%**. Longer lookback filters eliminated excessive trade churn during trend consolidations.

#### 3.3 Mean Reversion Collapse
- All mean-reversion variants suffered severe drawdowns (-31.47% return, 33.42% max drawdown for BB 2.0 std).
- During strong secular equity rallies (such as NVDA's massive expansion), counter-trend short/reversion signals repeatedly hit stop-losses.

---

### 4. Workstream 5 Conclusion

The candidate revalidation confirms that no candidate strategy possesses positive net expectancy across the multi-asset portfolio under realistic execution frictions. The baseline status remains firmly:
`REJECTED — NOT ELIGIBLE FOR PAPER TRADING`.
