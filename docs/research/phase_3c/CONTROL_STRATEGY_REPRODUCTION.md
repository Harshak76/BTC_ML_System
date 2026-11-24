# BTC-ML SYSTEM V2 — PHASE 3C CONTROL STRATEGY REPRODUCTION REPORT
## Baseline Donchian-40 Momentum Benchmark Evaluation

- **Candidate ID:** `RS_MOM_DONCHIAN_40_CONTROL`
- **Family:** Momentum (`StrategyFamily.MOMENTUM`)
- **Version:** 2.0.0
- **Auditor:** Quantitative Research Lab & Backtesting Auditor
- **Evaluation Window:** 2024-01-02 to 2026-09-22
- **Data Source:** `BTC_ML_System/data/authentic_raw/` (Alpaca API v2 + authentic spot crypto)
- **Mandatory Disclosure:**
  > **`HISTORICAL EXPLORATORY EVALUATION — PRIOR DATASET INSPECTION DISCLOSED`**  
  > This reproduction serves as the experimental control benchmark. The underlying 2024–2026 market data was previously inspected in Phase 3A, 3B, 3B.1, and 3B.2.

---

## 1. REPRODUCTION SPECIFICATION & HYPOTHESIS

`RS_MOM_DONCHIAN_40_CONTROL` replicates the baseline Donchian 40 momentum strategy identified in Phase 3B.
- **Entry Logic:** At completed candle $t$ close, enter Long if $Close_t > \max_{1..40}(High_{t-i})$, $Close_t > Close_{t-40}$, and $RSI_{14, t} < 75.0$.
- **Exit Logic:** Exit if $Close_t < \min_{1..20}(Low_{t-i})$, or on ATR-based stop-loss ($2.0 \times ATR_{14}$ below fill) or take-profit ($4.5 \times ATR_{14}$ above fill), or $2.0\%$ trailing stop.
- **Execution:** Next-bar open fill ($t+1$).
- **Friction:** Crypto: 5 bps slippage entry/exit, 10 bps commission; Equities: 2 bps slippage entry/exit, 0 bps commission.

---

## 2. PORTFOLIO-LEVEL MULTI-ASSET PERFORMANCE

Simulated across the full 7-asset portfolio (AAPL, MSFT, NVDA, TSLA, AMZN, BTCUSDT, ETHUSDT) with $\$100,000$ initial capital, maximum 4 concurrent positions, and $0.5\%$ risk per trade:

| Metric | Empirical Value | Target / Benchmark | Assessment |
|---|---|---|---|
| **Initial Capital** | $\$100,000.00$ | $\$100,000.00$ | Baseline |
| **Final Equity** | **$\$90,428.59$** | $> \$100,000.00$ | **Capital Depletion** |
| **Total Net Return** | **$-9.5714\%$** | $> 0.00\%$ | **Failed** |
| **Annualized Sharpe Ratio** | **$-1.1076$** | $> 1.0000$ | **Negative Risk-Adjusted Edge** |
| **Sortino Ratio** | **$-0.3736$** | $> 1.5000$ | Negative downside deviation |
| **Calmar Ratio** | **$-0.3196$** | $> 1.0000$ | Negative return to drawdown ratio |
| **Maximum Drawdown** | **$13.2159\%$** | $< 20.00\%$ | Passed ($< 20\%$) |
| **Total Completed Trades** | **913** | $\ge 100$ | Statistically sufficient sample |
| **Win Rate** | **$41.51\%$** ($379 / 913$) | $> 45.00\%$ | Typical trend-following hit rate |
| **Profit Factor** | **0.8453** | $> 1.2500$ | Gross losses exceed gross gains |
| **Expectancy per Trade** | **$-\$10.48$** | $> \$0.00$ | Consistent negative drift per trade |

---

## 3. STANDALONE ASSET-LEVEL BREAKDOWN

When evaluated as isolated, single-asset strategies, the control strategy demonstrates substantial dispersion across asset classes:

| Symbol | Total Return | Sharpe Ratio | Max Drawdown | Trades | Win Rate | Profit Factor | Final Equity |
|---|---|---|---|---|---|---|---|
| **AAPL** | $-3.78\%$ | $-0.4512$ | $5.74\%$ | 143 | $42.7\%$ | 0.76 | $\$96,221.61$ |
| **MSFT** | $-2.36\%$ | $-0.2481$ | $6.10\%$ | 139 | $41.7\%$ | 0.86 | $\$97,641.84$ |
| **NVDA** | **$+2.12\%$** | **$+0.2272$** | $3.57\%$ | 137 | $47.4\%$ | 1.14 | $\$102,119.68$ |
| **TSLA** | **$+3.01\%$** | **$+0.4068$** | $2.14\%$ | 95 | $52.6\%$ | 1.34 | $\$103,009.04$ |
| **AMZN** | $-3.06\%$ | $-0.3734$ | $4.73\%$ | 134 | $44.0\%$ | 0.80 | $\$96,936.83$ |
| **BTCUSDT** | $-3.87\%$ | $-2.9589$ | $4.65\%$ | 54 | $29.6\%$ | 0.46 | $\$96,129.94$ |
| **ETHUSDT** | $-6.41\%$ | $-1.2701$ | $7.39\%$ | 211 | $33.2\%$ | 0.69 | $\$93,589.50$ |

### Quantitative Diagnostics:
1. **Equity Dispersion:** NVDA and TSLA delivered positive returns (+2.12% and +3.01%) due to strong secular upside drift during 2024–2025.
2. **Crypto Frictions:** Both BTCUSDT (-3.87%, Sharpe -2.96) and ETHUSDT (-6.41%, Sharpe -1.27) were heavily penalized by 30 bps round-trip transaction frictions and whipsaws in choppy consolidation phases.
3. **Breadth Failure:** Only 2 of 7 assets were profitable (failing the Gate 3 requirement of $\ge 4$ profitable assets).

---

## 4. CONTROL REPRODUCTION VERDICT

The reproduction of `RS_MOM_DONCHIAN_40_CONTROL` confirms the Phase 3B findings:
- The unfiltered 40-bar Donchian breakout suffers severe friction drag and excessive false breakouts (913 portfolio trades, win rate $41.51\%$, profit factor $0.85$).
- Net annualized portfolio Sharpe is $-1.1076$, firmly confirming that the raw core without additional filtering is unprofitable and **REJECTED**.
