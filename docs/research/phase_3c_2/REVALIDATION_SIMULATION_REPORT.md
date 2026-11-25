# BTC-ML SYSTEM V2 — PHASE 3C.2 RESEARCH REPORT
# REVALIDATION SIMULATION REPORT

**Document ID:** `REVALIDATION_SIMULATION_REPORT.md`  
**Phase:** 3C.2 Research Integrity Remediation & Controlled Revalidation  
**Repository:** `BTC_ML_System`  
**Branch:** `fix/phase-3c-2-research-integrity`  
**Base Commit:** `93e7121`  
**Simulated Universe:** 7 assets (AAPL, MSFT, NVDA, TSLA, AMZN, BTCUSDT, ETHUSDT) on consistent 1H execution  
**Date:** 2026-11-25

---

## 1. Executive Summary

In Phase 3C.2, all three strategy candidates:
1. `RS_MOM_DONCHIAN_40_CONTROL`
2. `RS_MOM_DONCHIAN_40_ADX25`
3. `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE`
were re-evaluated on a strictly consistent 1-hour execution timeline across both crypto (BTCUSDT, ETHUSDT) and US equities (AAPL, MSFT, NVDA, TSLA, AMZN) over the 24-month horizon (`2024-09-22 17:00:00` to `2026-09-21 16:00:00` UTC).

### Primary Findings
1. **Severe Degradation on 1H BTC:**  
   In Phase 3C, BTC was simulated on 4H candles, yielding 54 trades and a $-3.87\%$ return. Under the corrected 1H resolution, Donchian-40 triggers on 40-hour breakouts rather than 160-hour extremes, causing BTC trade volume to explode to **258 trades** and standalone net loss to expand to **$-21.54\%$** (Sharpe **$-3.8574$**).
2. **Portfolio-Level Losses Worsen:**  
   - Control Annualized Sharpe dropped from **$-1.1076$** down to **$-2.0646$** (Total Return dropped from $-9.57\%$ to **$-15.83\%$**).
   - ADX25 Annualized Sharpe dropped from **$-0.7198$** down to **$-1.1778$** (Total Return dropped from $-4.30\%$ to **$-6.19\%$**).
   - 4H EMA Slope Annualized Sharpe dropped from **$-1.4398$** down to **$-2.1556$** (Total Return dropped from $-11.32\%$ to **$-15.04\%$**).
3. **Hypothesis Disproven:**  
   The prior negative results were **NOT** an artifact of timeframe mismatch. Correcting the timeframe defect eliminates all doubt: the strategy family produces negative alpha across both individual assets and diversified multi-asset portfolios.

---

## 2. Asset-Level Performance Breakdown (1H Standalone)

Each asset was simulated standalone with $\$100,000$ initial capital, position size capped at $100\%$ capital, and authentic friction modeling (crypto: 5 bps slip, 10 bps fee; equities: 2 bps slip, 0 bps fee):

### Candidate 1: `RS_MOM_DONCHIAN_40_CONTROL`
| Asset | Timeframe | Total Net Return | Annualized Return | Net Sharpe | Max Drawdown | Win Rate | Total Trades | Profit Factor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BTCUSDT** | **1H** | **$-21.54\%$** | **$-11.45\%$** | **$-3.8574$** | **$21.82\%$** | $39.5\%$ | **258** | **0.68** |
| **ETHUSDT** | 1H | $-6.41\%$ | $-3.26\%$ | $-1.2701$ | $7.39\%$ | $40.8\%$ | 211 | 0.81 |
| **AAPL** | 1H | $-1.00\%$ | $-0.50\%$ | $-0.1547$ | $3.16\%$ | $44.4\%$ | 99 | 0.94 |
| **MSFT** | 1H | $-1.18\%$ | $-0.59\%$ | $-0.1692$ | $4.42\%$ | $44.0\%$ | 91 | 0.92 |
| **NVDA** | 1H | $-0.64\%$ | $-0.32\%$ | $-0.0894$ | $3.41\%$ | $42.6\%$ | 101 | 0.96 |
| **TSLA** | 1H | $+3.57\%$ | $+1.77\%$ | $+0.6490$ | $1.73\%$ | $47.1\%$ | 68 | 1.48 |
| **AMZN** | 1H | $-1.58\%$ | $-0.79\%$ | $-0.2623$ | $4.73\%$ | $42.5\%$ | 87 | 0.88 |

---

### Candidate 2: `RS_MOM_DONCHIAN_40_ADX25`
| Asset | Timeframe | Total Net Return | Annualized Return | Net Sharpe | Max Drawdown | Win Rate | Total Trades | Profit Factor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BTCUSDT** | **1H** | **$-7.87\%$** | **$-4.02\%$** | **$-2.0845$** | **$8.02\%$** | $38.1\%$ | **105** | **0.78** |
| **ETHUSDT** | 1H | $-3.09\%$ | $-1.56\%$ | $-0.9005$ | $3.76\%$ | $40.2\%$ | 92 | 0.86 |
| **AAPL** | 1H | $+0.64\%$ | $+0.32\%$ | $+0.1475$ | $2.22\%$ | $47.7\%$ | 44 | 1.15 |
| **MSFT** | 1H | $-1.19\%$ | $-0.60\%$ | $-0.3171$ | $2.18\%$ | $39.4\%$ | 33 | 0.77 |
| **NVDA** | 1H | $-0.30\%$ | $-0.15\%$ | $-0.0834$ | $1.67\%$ | $43.2\%$ | 37 | 0.94 |
| **TSLA** | 1H | $+2.72\%$ | $+1.35\%$ | $+0.6495$ | $1.66\%$ | $50.0\%$ | 32 | 1.62 |
| **AMZN** | 1H | $-0.29\%$ | $-0.15\%$ | $-0.0735$ | $2.37\%$ | $42.1\%$ | 38 | 0.94 |

---

### Candidate 3: `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE`
| Asset | Timeframe | Total Net Return | Annualized Return | Net Sharpe | Max Drawdown | Win Rate | Total Trades | Profit Factor |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BTCUSDT** | **1H** | **$-18.64\%$** | **$-9.81\%$** | **$-3.4088$** | **$19.06\%$** | $38.7\%$ | **230** | **0.71** |
| **ETHUSDT** | 1H | $-6.50\%$ | $-3.30\%$ | $-1.4512$ | $6.66\%$ | $38.9\%$ | 180 | 0.78 |
| **AAPL** | 1H | $-0.13\%$ | $-0.07\%$ | $-0.0173$ | $3.14\%$ | $42.9\%$ | 84 | 0.99 |
| **MSFT** | 1H | $-2.13\%$ | $-1.08\%$ | $-0.3601$ | $4.13\%$ | $42.0\%$ | 81 | 0.82 |
| **NVDA** | 1H | $-1.96\%$ | $-0.99\%$ | $-0.3192$ | $2.60\%$ | $41.8\%$ | 91 | 0.85 |
| **TSLA** | 1H | $+2.51\%$ | $+1.24\%$ | $+0.4810$ | $1.84\%$ | $47.5\%$ | 61 | 1.34 |
| **AMZN** | 1H | $-0.70\%$ | $-0.35\%$ | $-0.1160$ | $4.37\%$ | $40.5\%$ | 79 | 0.94 |

---

## 3. Portfolio-Level Performance Comparison (Phase 3C vs. Phase 3C.2)

The 7-asset portfolio was simulated under identical risk parameters ($\$100,000$ initial capital, max 4 open positions, $0.5\%$ risk per trade, $20\%$ max capital per position):

| Metric | Candidate 1: Control | Candidate 2: ADX25 | Candidate 3: 4H EMA Slope |
| :--- | :--- | :--- | :--- |
| **Phase 3C Reported Net Return** | $-9.57\%$ | $-4.30\%$ | $-11.32\%$ |
| **Phase 3C.2 Remediated Net Return** | **$-15.83\%$** | **$-6.19\%$** | **$-15.04\%$** |
| *Return Delta* | *$-6.26\%$ (Worse)* | *$-1.89\%$ (Worse)* | *$-3.72\%$ (Worse)* |
| **Phase 3C Reported Sharpe** | $-1.1076$ | $-0.7198$ | $-1.4398$ |
| **Phase 3C.2 Remediated Sharpe** | **$-2.0646$** | **$-1.1778$** | **$-2.1556$** |
| *Sharpe Delta* | *$-0.9570$ (Worse)* | *$-0.4580$ (Worse)* | *$-0.7158$ (Worse)* |
| **Phase 3C Max Drawdown** | $13.22\%$ | $7.18\%$ | $12.50\%$ |
| **Phase 3C.2 Max Drawdown** | **$17.33\%$** | **$8.59\%$** | **$15.04\%$** |
| *Drawdown Delta* | *$+4.11\%$ (Worse)* | *$+1.41\%$ (Worse)* | *$+2.54\%$ (Worse)* |
| **Phase 3C Total Trades** | 913 | 395 | 813 |
| **Phase 3C.2 Total Trades** | **913** | **381** | **804** |
| **Phase 3C.2 Win Rate** | $42.2\%$ | $44.4\%$ | $41.3\%$ |
| **Phase 3C.2 Profit Factor** | $0.80$ | $0.89$ | $0.81$ |

---

## 4. Why 1H Sampling Exacerbates Losses

1. **Horizon Compression:** On a 4H bar, a 40-period Donchian channel represents a 160-hour (~6.67 day) breakout, filtering out daily chop. On a 1H bar, Donchian-40 represents a 40-hour (~1.67 day) breakout. In a consolidating crypto market, 40-hour breakouts are overwhelmingly false breakout traps.
2. **Turnover Friction Drag:** By trading false breakouts at nearly 5x the frequency, the strategy pays 5 bps slippage and 10 bps exchange commission repeatedly, incurring compounded frictional drag that drains capital.
3. **Filter Effectiveness Contrast:**
   - The ADX filter successfully pruned trades from 913 down to 381 (a $58.3\%$ reduction) and cut total losses from $-15.83\%$ down to $-6.19\%$.
   - However, even with the ADX filter, the net Sharpe remains negative ($-1.1778$). The filter cushions the fall, but cannot generate positive returns from a negative-sum base strategy.

---

## 5. Audit Conclusion

The revalidated simulations under consistent 1H execution conclusively establish that **Phase 3C's negative findings were genuine and robust**:
- Correcting timeframe resolution worsens performance across all metrics.
- All three candidates decisively fail Gate 1 (Net Return $> 0$) and Gate 3 (Sharpe $\ge 1.0$).
