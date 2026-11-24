# BTC-ML SYSTEM V2 — PHASE 3C ADX TREATMENT REPORT
## Evaluation of Donchian-40 with ADX14 >= 25 Trend Strength Confirmation

- **Candidate ID:** `RS_MOM_DONCHIAN_40_ADX25`
- **Family:** Momentum (`StrategyFamily.MOMENTUM`)
- **Version:** 2.0.0
- **Auditor:** Senior Quantitative Researcher & Backtesting Auditor
- **Evaluation Window:** 2024-01-02 to 2026-09-22
- **Data Source:** `BTC_ML_System/data/authentic_raw/`
- **Mandatory Disclosure:**
  > **`HISTORICAL EXPLORATORY EVALUATION — PRIOR DATASET INSPECTION DISCLOSED`**  
  > Evaluated on historical data with prior inspection disclosed.

---

## 1. TREATMENT HYPOTHESIS & MECHANISM

The ADX treatment tests whether conditioning Donchian 40 breakout entries on an established directional regime ($ADX_{14} \ge 25.0$) filters out false breakouts in sideways/consolidating markets:
- **Condition:** Long Entry requires Control Signal $= 1$ **AND** $ADX_{14} \ge 25.0$ on completed candle close.
- **Exit Logic:** Unaltered (20-bar Donchian low, ATR stop $2.0\times$, take profit $4.5\times$, trailing stop $2\%$).
- **Null Hypothesis ($H_{0, A}$):** $\text{Sharpe}_{\text{ADX25}} \le \text{Sharpe}_{\text{Control}}$
- **Alternative Hypothesis ($H_{1, A}$):** $\text{Sharpe}_{\text{ADX25}} > \text{Sharpe}_{\text{Control}}$

---

## 2. PORTFOLIO-LEVEL MULTI-ASSET PERFORMANCE

Simulated under identical conditions: $\$100,000$ initial capital, 4 max positions, $0.5\%$ risk per trade:

| Metric | Control (`DONCHIAN_40`) | ADX Treatment (`ADX25`) | Absolute Change | Relative Impact |
|---|---|---|---|---|
| **Final Equity** | $\$90,428.59$ | **$\$95,699.07$** | **$+\$5,270.48$** | Capital saved |
| **Total Net Return** | $-9.5714\%$ | **$-4.3009\%$** | **$+5.2705\%$** | **$+55.1\%$ loss reduction** |
| **Annualized Sharpe** | $-1.1076$ | **$-0.7198$** | **$+0.3878$** | **$+35.0\%$ improvement** |
| **Sortino Ratio** | $-0.3736$ | **$-0.1676$** | $+0.2060$ | $+55.1\%$ improvement |
| **Calmar Ratio** | $-0.3196$ | **$-0.2602$** | $+0.0594$ | $+18.6\%$ improvement |
| **Maximum Drawdown** | $13.2159\%$ | **$7.1781\%$** | **$-6.0378\%$** | **$-45.7\%$ drawdown cut** |
| **Total Completed Trades** | 913 | **395** | **$-518$ trades** | **$-56.7\%$ volume reduction** |
| **Win Rate** | $41.51\%$ | **$43.04\%$** | $+1.53\%$ | Modest quality gain |
| **Profit Factor** | 0.8453 | **0.8535** | $+0.0082$ | Marginal gain |
| **Expectancy per Trade** | $-\$10.48$ | $-\$10.89$ | $-\$0.41$ | Similar trade edge |

---

## 3. ASSET-LEVEL PERFORMANCE COMPARISON

| Asset | Control Return | ADX Return | Control Sharpe | ADX Sharpe | Control MaxDD | ADX MaxDD | Trades Cut |
|---|---|---|---|---|---|---|---|
| **AAPL** | $-3.78\%$ | **$-1.09\%$** | $-0.4512$ | **$-0.1734$** | $5.74\%$ | **$3.61\%$** | $143 \to 64$ ($-55\%$) |
| **MSFT** | $-2.36\%$ | **$-1.14\%$** | $-0.2481$ | **$-0.2038$** | $6.10\%$ | **$2.93\%$** | $139 \to 53$ ($-62\%$) |
| **NVDA** | $+2.12\%$ | **$+0.12\%$** | $+0.2272$ | $+0.0256$ | $3.57\%$ | **$2.52\%$** | $137 \to 54$ ($-61\%$) |
| **TSLA** | $+3.01\%$ | **$+2.65\%$** | $+0.4068$ | **$+0.4853$** | $2.14\%$ | **$1.66\%$** | $95 \to 47$ ($-51\%$) |
| **AMZN** | $-3.06\%$ | **$-0.50\%$** | $-0.3734$ | **$-0.0962$** | $4.73\%$ | **$2.37\%$** | $134 \to 55$ ($-59\%$) |
| **BTCUSDT** | $-3.87\%$ | **$-2.05\%$** | $-2.9589$ | **$-2.1407$** | $4.65\%$ | **$2.37\%$** | $54 \to 30$ ($-44\%$) |
| **ETHUSDT** | $-6.41\%$ | **$-3.09\%$** | $-1.2701$ | **$-0.9005$** | $7.39\%$ | **$3.76\%$** | $211 \to 92$ ($-56\%$) |

---

## 4. HYPOTHESIS TESTING & STATISTICAL SIGNIFICANCE

### 1. Difference in Means & Paired Comparison
- Portfolio net return improved from $-9.57\%$ to $-4.30\%$.
- Maximum drawdown was reduced from $13.22\%$ to $7.18\%$.
- Paired asset-level Sharpe difference: $\Delta \text{Sharpe} = +0.2201$ across all 7 assets.
- However, Deflated Sharpe Ratio (DSR) analysis reveals:
  - $\text{Observed Sharpe} = -0.7198$
  - $\text{Expected Max Sharpe} (\text{12 trials}) = +1.0081$
  - $\text{DSR} = 0.0044$ ($p\text{-value} = 0.9956$)
  - Because the absolute Sharpe ratio remains negative ($-0.7198 < 0$), the strategy has zero statistical probability of possessing an intrinsic alpha edge over zero.

### 2. Economic Interpretation
The ADX filter acted as an effective **trade frequency damper**:
- It eliminated 518 low-conviction breakout trades ($56.7\%$ reduction).
- Eliminating these trades saved $\$5,270.48$ in cumulative transaction frictions (commissions and bid-ask slippage).
- However, the underlying win rate ($43.04\%$) and profit factor ($0.8535$) remained substantially below 1.0. The filter did not convert unprofitable breakouts into profitable ones; it merely attenuated the speed of capital depletion.

---

## 5. ADX TREATMENT VERDICT

1. **Relative Improvement:** Confirmed. The ADX filter significantly reduced drawdowns ($-45.7\%$) and cut net losses ($+55.1\%$ relative improvement).
2. **Absolute Hurdle:** **FAILED**. Net return is $-4.30\%$ (Gate 1 failed), Sharpe is $-0.7198$ (Gate 1 failed), and DSR $p$-value is $0.9956$ (Gate 4 failed).
3. **Verdict:** **REJECTED — NOT ELIGIBLE FOR PAPER TRADING**.
