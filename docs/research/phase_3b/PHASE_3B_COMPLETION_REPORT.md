# PHASE 3B COMPLETION REPORT
## Controlled Strategy Expansion & Independent Performance Evaluation

**Repository:** `BTC_ML_System`  
**Starting Commit:** `c92cb33`  
**Current Branch:** `feat/phase-3b-strategy-evaluation`  
**Execution Scope:** Strictly Offline Research Simulation (Zero Broker Connection)  
**Overall Quantitative Status:**  
`REJECTED — NOT ELIGIBLE FOR PAPER TRADING`

---

### 1. Executive Summary

Phase 3B has successfully executed the controlled quantitative strategy expansion and independent performance evaluation of candidate strategies on the BTC-ML System V2 platform.

All nine pre-registered research candidates (three Phase 3A baselines and six systematic variants across Trend Following, Momentum, and Mean Reversion) were independently evaluated across five US equities (`AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`) and two cryptocurrencies (`BTCUSDT`, `ETHUSDT`).

Every simulation adhered to rigorous execution and risk accounting protocols: completed candles only, next-bar open execution, dynamic fill-price-anchored stops, conservative gap-through-stop and collision rules, trailing stop lookahead elimination, regular equity market session gating, continuous 24/7 crypto execution, and realistic transaction frictions.

---

### 2. Candidate Evaluation Summary Table

| Strategy ID | Family | Strategy Description | Sharpe Ratio | Total Return (%) | Max Drawdown (%) | Trade Count | Win Rate (%) | Profit Factor |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `RS_TF_DUAL_EMA_21_55_V1` | Trend Following | Dual EMA (21/55) with ADX & ATR Stop | **-1.74** | **-6.46%** | 6.46% | 250 | 48.40% | 0.69 |
| `RS_TF_DUAL_EMA_20_50_V1` | Trend Following | Dual EMA (20/50) with ADX & ATR Stop | **-1.61** | **-6.82%** | 7.00% | 272 | 48.16% | 0.70 |
| `RS_TF_DUAL_EMA_50_100_V1` | Trend Following | Dual EMA (50/100) with ADX & ATR Stop | **-0.44** | **-1.54%** | **2.76%** | **158** | **56.33%** | **0.87** |
| `RS_MOM_DONCHIAN_20_V1` | Momentum | Donchian 20 Breakout & RSI Ceiling | **-0.75** | **-12.13%** | 15.48% | 910 | 53.30% | 0.88 |
| `RS_MOM_DONCHIAN_40_V1` | Momentum | Donchian 40 Breakout & RSI Ceiling | **-0.40** | **-5.46%** | **10.71%** | **575** | **55.48%** | **0.94** |
| `RS_MOM_DONCHIAN_55_V1` | Momentum | Donchian 55 Breakout & RSI Ceiling | **-0.79** | **-9.35%** | 11.55% | 476 | 54.62% | 0.89 |
| `RS_MR_BB_RSI_20_STD_V1` | Mean Reversion | Bollinger Band (2.0 std) RSI Reversion | **-1.24** | **-13.78%** | 20.20% | 752 | 49.07% | 0.77 |
| `RS_MR_BB_RSI_22_STD_V1` | Mean Reversion | Bollinger Band (2.2 std) RSI Reversion | **-2.02** | **-15.83%** | 18.56% | 497 | 47.28% | 0.72 |
| `RS_MR_BB_RSI_25_STD_V1` | Mean Reversion | Bollinger Band (2.5 std) RSI Reversion | **-1.24** | **-7.43%** | **10.25%** | **270** | **50.00%** | **0.81** |

---

### 3. Key Quantitative Findings

#### 3.1 Top Performer: `RS_MOM_DONCHIAN_40_V1`
- Achieved the highest portfolio Sharpe ratio ($-0.40$), profit factor ($0.94$), and win rate ($55.5\%$) among momentum variants.
- On US equities, the strategy achieved $+1.02\%$ net return with a **72.6% win rate** and **+0.22 Sharpe ratio**.
- On cryptocurrencies, however, choppy non-trending regimes and 20 bps round-trip friction caused net losses ($-3.41\%$ on BTC, $-5.90\%$ on ETH).

#### 3.2 Lowest Risk: `RS_TF_DUAL_EMA_50_100_V1`
- Demonstrated the strongest capital preservation profile: maximum portfolio drawdown was limited to **2.76%**, with a **56.33% win rate** and low turnover ($1.12\times$).
- Smoothing lookbacks to 50/100 eliminated short-term whipsaws.

#### 3.3 Root Causes of Unsuccessful Candidates
- **Mean Reversion Breakdown:** All mean reversion candidates suffered negative expectancy. In strongly trending markets, price continuously pierced the lower bands without mean-reverting, hitting stop-losses repeatedly.
- **Short Lookback Friction Churn:** 20-bar Donchian breakouts and 20/50 EMAs generated excessive trade churn ($5\times - 6\times$ annual turnover), allowing transaction frictions to consume all gross profits.
- **Ranging Regime Drain:** In the regime analysis, momentum produced a **75.0% win rate and +$336 PnL** during trending regimes, but lost **-$5,796 across 543 trades** during ranging chop.

---

### 4. Overfitting & Multiple-Testing Audit

1. **Genuine Candidate Matrix:** Constructed an authentic $T \times N$ matrix ($T = 43,069$ hourly bars, $N = 9$ genuine candidate streams) with zero synthetic Gaussian perturbation.
2. **Probability of Backtest Overfitting (PBO):**
   $$\text{PBO} = 0.4802 \quad (48.02\%)$$
   A PBO near $50\%$ confirms that selecting the best performer from this pool offers no statistical advantage over a coin toss out-of-sample without regime conditioning.
3. **Deflated Sharpe Ratio (DSR):**
   $$\text{DSR} = 0.000335 \quad (0.033\%)$$
   Well below the mandatory $95\%$ significance threshold ($\alpha = 0.05$).
4. **Persistent Experiment Tracking:** All 9 candidate runs were serialized into the DuckDB `experiment_registry` table. DuckDB `trades` table remains exactly at 1,334 records.

---

### 5. Acceptance Criteria Verification

- [x] All three original baseline candidates independently evaluated.
- [x] Six controlled pre-registered variants implemented and evaluated.
- [x] Execution and risk accounting assumptions audited and verified.
- [x] Asset-level performance results computed for all 7 assets.
- [x] Benchmark comparisons against Buy & Hold, Cash, and SMA trend documented.
- [x] Genuine return streams persisted and aligned without synthetic fabrication.
- [x] CSCV / PBO calculated on genuine candidate matrix ($N = 9 \ge 4$).
- [x] Experiment registry persisted in DuckDB (10 total experiments logged).
- [x] Complete test suite passing: **95 passed, 0 failed (100% pass rate)**.
- [x] Zero broker connections or order placements occurred.
- [x] Frozen production configurations remain untouched.

---

### 6. Final Status & Mandatory Stop Condition

The Phase 3B controlled strategy evaluation is complete.

**OVERALL VERDICT:**
`REJECTED — NOT ELIGIBLE FOR PAPER TRADING`

No live trading, broker connection, or automated deployment is authorized.

In accordance with Phase 3B governance rules, execution is stopped. We await explicit operator authorization before proceeding to Phase 3C (multi-factor modeling, regime-conditioned filtering, and portfolio construction).
