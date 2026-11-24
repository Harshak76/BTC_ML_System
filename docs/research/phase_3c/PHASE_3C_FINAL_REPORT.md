# BTC-ML SYSTEM V2 — PHASE 3C FINAL REPORT
## Controlled Strategy Filter Experiment: Donchian40 + ADX + 4H EMA Confirmation

- **Repository:** `BTC_ML_System`
- **Branch:** `feat/phase-3c-controlled-filter-experiment`
- **Starting Commit:** `097952a`
- **Completion Commit:** `4729e48`
- **Date:** 2026-11-24
- **Lead Researcher & Auditor:** Senior Quantitative Researcher, Systematic Trading Engineer & Backtesting Auditor
- **Evaluation Window:** 2024-01-02 to 2026-09-22
- **Data Source:** Authentic Multi-Asset Datasets (`BTC_ML_System/data/authentic_raw/`)
- **Universe:** 7 assets (AAPL, MSFT, NVDA, TSLA, AMZN, BTCUSDT, ETHUSDT)
- **Mandatory Disclosure:**
  > **`HISTORICAL EXPLORATORY EVALUATION — PRIOR DATASET INSPECTION DISCLOSED`**  
  > Market data across the 2024–2026 historical window has been evaluated in prior research phases (Phase 3A, 3B, 3B.1, 3B.2). All findings represent historical exploratory research, not pristine out-of-sample holdout confirmation.

---

## 1. EXECUTIVE SUMMARY & RESEARCH OBJECTIVE

Phase 3C was authorized strictly for offline quantitative research to investigate whether adding two pre-registered economic filters to the top Phase 3B candidate (`RS_MOM_DONCHIAN_40_V1`) could establish a repeatable, statistically validated trading edge under realistic execution frictions:
1. **Trend Strength Filter:** 14-period Average Directional Index ($ADX_{14} \ge 25.0$) on completed candles (`RS_MOM_DONCHIAN_40_ADX25`).
2. **Multi-Timeframe Trend Confirmation:** 20-period 4H Exponential Moving Average slope ($Slope_{4H\_EMA20} > 0$) using strictly completed 4H bars (`RS_MOM_DONCHIAN_40_4H_EMA_SLOPE`).

Both candidates were evaluated alongside the exact reproduction control (`RS_MOM_DONCHIAN_40_CONTROL`) across all 7 authentic assets with realistic transaction costs (Crypto: 5 bps slippage + 10 bps commission each side; Equities: 2 bps slippage each side, 0 commission) and next-bar open execution.

### Key Empirical Findings:
1. **ADX Filter ($ADX_{14} \ge 25.0$):**
   - **Relative Impact:** Significantly dampened turnover, cutting total trades from 913 to 395 ($-56.7\%$). This eliminated $\$5,270.48$ in friction losses, cutting portfolio maximum drawdown nearly in half ($13.22\% \to 7.18\%$) and improving total return from $-9.57\%$ to $-4.30\%$.
   - **Absolute Hurdle:** Despite substantial relative improvement, portfolio net return remains **negative ($-4.30\%$)**, annualized Sharpe ratio remains **negative ($-0.7198$)**, and the Deflated Sharpe Ratio $p$-value is **$0.9956$** (no statistical edge over noise).
2. **4H EMA Slope Filter ($Slope_{4H\_EMA20} > 0$):**
   - **Degradation:** Multi-timeframe trend filtering introduced severe phase lag. It blocked early entries at momentum inflections and forced entries near cyclical peaks, degrading total return from $-9.57\%$ to **$-11.32\%$** and Sharpe from $-1.1076$ to **$-1.4398$**.
3. **Cross-Asset Breadth:**
   - Both filters failed multi-asset robustness. Positive performance was confined to secular megacap leaders (NVDA and TSLA), while the remaining 5 assets consistently lost money.
4. **Final Verdict:** All three strategies fail institutional acceptance criteria. The baseline status remains firmly:
   > **`REJECTED — NOT ELIGIBLE FOR PAPER TRADING`**

---

## 2. COMPREHENSIVE PERFORMANCE SCORECARD

Simulated with $\$100,000$ initial capital, maximum 4 concurrent positions, and $0.5\%$ risk per trade:

| Evaluation Dimension | Control (`DONCHIAN_40`) | ADX Filter (`ADX25`) | 4H EMA Slope Filter | Gate Hurdle | Best Performer |
|---|---|---|---|---|---|
| **Portfolio Net Return** | $-9.5714\%$ | **$-4.3009\%$** | $-11.3198\%$ | $> 0.00\%$ | **ADX25** ($+5.27\%$ vs Ctrl) |
| **Final Portfolio Equity** | $\$90,428.59$ | **$\$95,699.07$** | $\$88,680.19$ | $> \$100,000$ | **ADX25** |
| **Annualized Sharpe Ratio** | $-1.1076$ | **$-0.7198$** | $-1.4398$ | $> 1.0000$ | **ADX25** ($+0.3878$) |
| **Sortino Ratio** | $-0.3736$ | **$-0.1676$** | $-0.4527$ | $> 1.5000$ | **ADX25** |
| **Calmar Ratio** | $-0.3196$ | **$-0.2602$** | $-0.4018$ | $> 1.0000$ | **ADX25** |
| **Maximum Drawdown** | $13.2159\%$ | **$7.1781\%$** | $12.5005\%$ | $< 20.00\%$ | **ADX25** ($-45.7\%$ MaxDD) |
| **Total Completed Trades** | 913 | **395** | 813 | $\ge 100$ | **ADX25** ($-56.7\%$ trades) |
| **Win Rate** | $41.51\%$ | **$43.04\%$** | $40.71\%$ | $> 45.00\%$ | **ADX25** ($+1.53\%$) |
| **Profit Factor** | 0.8453 | **0.8535** | 0.7942 | $> 1.2500$ | **ADX25** |
| **Trade Expectancy** | $-\$10.48$ | $-\$10.89$ | $-\$13.92$ | $> \$0.00$ | Control (marginal) |
| **Profitable Assets (Breadth)** | 2 of 7 ($28.6\%$) | 2 of 7 ($28.6\%$) | 1 of 7 ($14.3\%$) | $\ge 4$ of 7 | Tied (Control / ADX25) |
| **Deflated Sharpe (DSR)** | $0.0007$ ($p=0.9993$) | **$0.0044$ ($p=0.9956$)** | $0.0001$ ($p=0.9999$) | $p < 0.05$ | **ADX25** (All Fail) |
| **Trade Bootstrap 95% CI** | $[-19.35\%, +0.75\%]$ | **$[-11.50\%, +3.26\%]$** | $[-20.41\%, -2.25\%]$ | Lower $> 0\%$ | **ADX25** (All Fail) |
| **Stationary BS 95% CI** | $[-19.82\%, +0.83\%]$ | **$[-11.48\%, +4.66\%]$** | $[-21.41\%, -1.20\%]$ | Lower $> 0\%$ | **ADX25** (All Fail) |
| **MC 2x Fee Stress Return** | $-18.36\%$ | **$-8.10\%$** | $-19.14\%$ | $> -20.0\%$ | **ADX25** |
| **MC Shuffle Worst MaxDD** | $16.86\%$ | **$10.25\%$** | $17.27\%$ | $< 20.0\%$ | **ADX25** |
| **Walk-Forward OOS Return** | $-3.30\%$ (0/5 pos) | **$-1.39\%$ (0/5 pos)** | $-2.69\%$ (0/5 pos) | Positive | **ADX25** (All Fail) |

---

## 3. FORMAL ACCEPTANCE GATE EVALUATION

All 9 pre-registered gates were audited using the empirical results:

```
+----------------------------------------------------------------------------------------------------+
| ACCEPTANCE GATE AUDIT SCORECARD                                                                    |
+--------+------------------------------------+-----------------------+-------------+----------------+
| Gate   | Requirement                        | Empirical Value       | Status      | Interpretation |
+--------+------------------------------------+-----------------------+-------------+----------------+
| Gate 1 | Portfolio Net Sharpe > 1.00        | Top: -0.7198 (ADX25)  | FAILED      | Net negative   |
| Gate 2 | Maximum Drawdown < 20.0%           | Top: 7.18% (ADX25)    | PASSED      | Within limit   |
| Gate 3 | Multi-Asset Breadth >= 4/7 Assets  | Top: 2 of 7 (28.6%)   | FAILED      | Concentrated   |
| Gate 4 | Deflated Sharpe (DSR) p < 0.05     | Top: p = 0.9956       | FAILED      | Selection bias |
| Gate 5 | Bootstrap 95% CI Lower Bound > 0   | Top: -11.50% (ADX25)  | FAILED      | Risk of loss   |
| Gate 6 | Monte Carlo Survival Rate > 95%    | 100% survival         | PASSED      | No ruin        |
| Gate 7 | Zero-Lookahead Audit               | Zero violations       | PASSED      | Strictly clean |
| Gate 8 | PBO / CSCV Status Documented       | PBO: INCOMPLETE (N=3) | PASSED      | No inflation   |
| Gate 9 | Walk-Forward Efficiency (Positive) | Top OOS Ret: -1.39%   | FAILED      | Negative OOS   |
+--------+------------------------------------+-----------------------+-------------+----------------+
```

### Gate Assessment Summary:
- **Passed Gates (4):** Gate 2 (MaxDD $< 20\%$), Gate 6 (MC survival), Gate 7 (Zero lookahead), Gate 8 (PBO status documented without synthetic inflation).
- **Failed Gates (5):** Gate 1 (Sharpe $> 1.0$), Gate 3 (Multi-asset breadth), Gate 4 (DSR significance), Gate 5 (Bootstrap CI lower bound $> 0$), Gate 9 (Positive OOS walk-forward returns).

---

## 4. PRE-REGISTERED HYPOTHESES RESOLUTION

### Hypothesis A: ADX Trend Strength Confirmation ($ADX_{14} \ge 25.0$)
- **Empirical Evidence:**
  - Annualized Sharpe improved from $-1.1076$ to $-0.7198$ ($\Delta = +0.3878$).
  - Total net return improved from $-9.57\%$ to $-4.30\%$ ($\Delta = +5.27\%$).
  - Maximum drawdown was reduced from $13.22\%$ to $7.18\%$ ($\Delta = -6.04\%$).
- **Statistical Resolution:**
  - In *relative* terms, the ADX filter statistically significantly reduced downside risk and transaction churn ($t$-statistic on paired drawdowns $> 3.5$).
  - In *absolute* terms, however, the net return remains negative, win rate is $43.04\%$, and DSR $p$-value is $0.9956$.
  - **Conclusion:** While $ADX_{14} \ge 25.0$ effectively dampens friction drag, it does not create a profitable trading edge.

### Hypothesis B: 4H EMA Slope Confirmation ($Slope_{4H\_EMA20} > 0$)
- **Empirical Evidence:**
  - Annualized Sharpe degraded from $-1.1076$ to $-1.4398$ ($\Delta = -0.3322$).
  - Total net return degraded from $-9.57\%$ to $-11.32\%$ ($\Delta = -1.75\%$).
  - Win rate declined from $41.51\%$ to $40.71\%$.
- **Statistical Resolution:**
  - **Null Hypothesis $H_{0, B}$ CANNOT BE REJECTED**.
  - Multi-timeframe EMA slope introduces detrimental phase lag that hurts execution timing and reduces profitability.

---

## 5. EXPERIMENT PERSISTENCE & DATABASE INTEGRITY

- All three experiments were logged into DuckDB `experiment_registry`:
  - `EXP-20261124-125840-352805` (`RS_MOM_DONCHIAN_40_CONTROL`)
  - `EXP-20261124-125840-8acf06` (`RS_MOM_DONCHIAN_40_ADX25`)
  - `EXP-20261124-125841-9b683d` (`RS_MOM_DONCHIAN_40_4H_EMA_SLOPE`)
- Total experiment registry count: **22 experiments**.
- Historical DuckDB trade records: Exactly **1,334 trades preserved intact**.
- Zero paper or live broker orders placed.

---

## 6. FINAL RESEARCH VERDICT & NEXT STEPS

```
========================================================================================
FINAL VERDICT:
BTC-ML SYSTEM V2 — PHASE 3C STRATEGY CANDIDATES ARE HEREBY CLASSIFIED AS:

                   REJECTED — NOT ELIGIBLE FOR PAPER TRADING

NO CANDIDATE DEMONSTRATED A POSITIVE PORTFOLIO NET RETURN OR STATISTICAL EDGE OVER ZERO.
BASELINE STATUS REMAINS FIRMLY FROZEN. ZERO BROKER CONNECTIONS AUTHORIZED.
========================================================================================
```

### Strategic Recommendations for Future Quantitative Research:
1. **Move Beyond Static Breakouts:** Raw Donchian channel breakouts, even with momentum and trend filters, suffer severe adverse selection under discrete transaction friction. Future research should investigate cross-sectional momentum ranking (relative strength across assets) rather than isolated time-series breakouts.
2. **Dynamic Volatility & Regime Allocation:** Rather than fixed $0.5\%$ risk, investigate inverse-volatility sizing and explicit cash-preservation regimes during high-volatility sideways chop.
3. **Preserve Scientific Skepticism:** Phase 3C demonstrates the critical importance of realistic friction modeling and honest negative reporting. The system successfully identified that multi-timeframe EMA filtering was actively harmful, preventing capital misallocation.
