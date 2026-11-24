# BTC-ML SYSTEM V2 — PHASE 3C 4H EMA SLOPE TREATMENT REPORT
## Evaluation of Donchian-40 with Multi-Timeframe 4H EMA Slope Confirmation

- **Candidate ID:** `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE`
- **Family:** Momentum (`StrategyFamily.MOMENTUM`)
- **Version:** 2.0.0
- **Auditor:** Senior Quantitative Researcher & Backtesting Auditor
- **Evaluation Window:** 2024-01-02 to 2026-09-22
- **Data Source:** `BTC_ML_System/data/authentic_raw/`
- **Mandatory Disclosure:**
  > **`HISTORICAL EXPLORATORY EVALUATION — PRIOR DATASET INSPECTION DISCLOSED`**  
  > Evaluated on historical data with prior inspection disclosed.

---

## 1. TREATMENT HYPOTHESIS & MTF MECHANISM

The 4H EMA slope treatment evaluates multi-timeframe trend alignment:
- **Condition:** Long Entry requires Control Signal $= 1$ **AND** $Slope_{4H\_EMA20} > 0$ on strictly completed 4H bars.
- **Strict Lookahead Protection:** At 1H candle $t$ close (e.g. 14:00 UTC), the forming 4H candle (12:00–16:00 UTC) is masked. The strategy strictly references the latest *completed* 4H candle (closed at 12:00 UTC).
- **Null Hypothesis ($H_{0, B}$):** $\text{Sharpe}_{\text{4H\_EMA}} \le \text{Sharpe}_{\text{Control}}$
- **Alternative Hypothesis ($H_{1, B}$):** $\text{Sharpe}_{\text{4H\_EMA}} > \text{Sharpe}_{\text{Control}}$

---

## 2. PORTFOLIO-LEVEL MULTI-ASSET PERFORMANCE

Simulated under identical portfolio conditions: $\$100,000$ initial capital, 4 max positions, $0.5\%$ risk per trade:

| Metric | Control (`DONCHIAN_40`) | 4H EMA Slope Treatment | Absolute Change | Impact |
|---|---|---|---|---|
| **Final Equity** | $\$90,428.59$ | **$\$88,680.19$** | **$-\$1,748.40$** | **Performance Degraded** |
| **Total Net Return** | $-9.5714\%$ | **$-11.3198\%$** | **$-1.7484\%$** | **$-18.3\%$ worse loss** |
| **Annualized Sharpe** | $-1.1076$ | **$-1.4398$** | **$-0.3322$** | **Degraded risk-adjusted return** |
| **Sortino Ratio** | $-0.3736$ | **$-0.4527$** | $-0.0791$ | Increased downside volatility |
| **Calmar Ratio** | $-0.3196$ | **$-0.4018$** | $-0.0822$ | Worse return/drawdown |
| **Maximum Drawdown** | $13.2159\%$ | **$12.5005\%$** | $-0.7154\%$ | Marginal reduction |
| **Total Completed Trades** | 913 | **813** | **$-100$ trades** | Filter only blocked 10.9% of trades |
| **Win Rate** | $41.51\%$ | **$40.71\%$** | **$-0.80\%$** | Quality declined |
| **Profit Factor** | 0.8453 | **0.7942** | **$-0.0511$** | Deteriorated gain/loss ratio |
| **Expectancy per Trade** | $-\$10.48$ | **$-\$13.92$** | **$-\$3.44$** | Increased negative drift |

---

## 3. ASSET-LEVEL PERFORMANCE BREAKDOWN

| Asset | Control Return | 4H EMA Return | Control Sharpe | 4H EMA Sharpe | Win Rate | Profit Factor | Trades |
|---|---|---|---|---|---|---|---|
| **AAPL** | $-3.78\%$ | **$-3.80\%$** | $-0.4512$ | **$-0.5040$** | $42.4\%$ | 0.72 | 125 |
| **MSFT** | $-2.36\%$ | **$-2.56\%$** | $-0.2481$ | **$-0.3029$** | $40.5\%$ | 0.83 | 126 |
| **NVDA** | $+2.12\%$ | **$-0.85\%$** | $+0.2272$ | **$-0.0921$** | $43.5\%$ | 0.94 | 124 |
| **TSLA** | $+3.01\%$ | **$+1.72\%$** | $+0.4068$ | **$+0.2457$** | $53.5\%$ | 1.21 | 86 |
| **AMZN** | $-3.06\%$ | **$-1.96\%$** | $-0.3734$ | **$-0.2423$** | $44.9\%$ | 0.86 | 118 |
| **BTCUSDT** | $-3.87\%$ | **$-3.87\%$** | $-2.9589$ | **$-2.9589$** | $29.6\%$ | 0.46 | 54 |
| **ETHUSDT** | $-6.41\%$ | **$-6.50\%$** | $-1.2701$ | **$-1.4512$** | $32.2\%$ | 0.63 | 180 |

### Critical Failure Analysis:
1. **The NVDA Breakdown:** On NVDA, the Control generated $+2.12\%$ return (Sharpe $+0.2272$). The 4H EMA slope filter inverted NVDA into a loss ($-0.85\%$, Sharpe $-0.0921$). Because 4H EMA slope lags turning points by several bars, it blocked early breakout entries at key momentum inflections and entered late near intermediate peaks.
2. **Lag Penalty:** Multi-timeframe trend filters introduce substantial phase lag. Requiring 4H EMA slope $> 0$ forced trades to enter only after substantial 4H momentum had already accrued, leaving less remaining room to take-profit ($4.5\times ATR$) before mean-reverting.
3. **No Trade Reduction in Crypto:** On BTCUSDT (already a 4H series), the filter had zero effect (identical 54 trades). On ETHUSDT, trades only dropped from 211 to 180, while net loss worsened from $-6.41\%$ to $-6.50\%$.

---

## 4. HYPOTHESIS TESTING VERDICT

- **Null Hypothesis ($H_{0, B}$):** **CANNOT BE REJECTED**.
  $$\text{Sharpe}_{\text{4H\_EMA}} = -1.4398 \le \text{Sharpe}_{\text{Control}} = -1.1076$$
- The 4H EMA slope filter failed to improve performance across any dimension. It degraded the annualized Sharpe ratio, increased total losses by $\$1,748.40$, depressed win rate to $40.71\%$, and reduced profit factor to $0.7942$.
- **Verdict:** **REJECTED — NOT ELIGIBLE FOR PAPER TRADING**.
