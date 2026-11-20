# MEAN REVERSION VARIANTS
## Controlled Expansion & Deviation Band Sensitivity

**Repository:** `BTC_ML_System`  
**Branch:** `feat/phase-3b-strategy-evaluation`  
**Strategy Family:** Mean Reversion (Bollinger Band Lower Deviations with RSI Oversold & Mean Exit)  
**Universe:** Multi-Asset Portfolio (AAPL, MSFT, NVDA, TSLA, AMZN, BTCUSDT, ETHUSDT)

---

### 1. Pre-Registered Mean Reversion Hypotheses

To investigate whether demanding more extreme statistical deviations protects mean reversion strategies against trending runaway losses, three pre-registered variants were tested:
1. **Variant 1 (Baseline):** `RS_MR_BB_RSI_20_STD_V1` — 20-period Bollinger Band, 2.0 standard deviations, RSI(14) $\le 32.0$.
2. **Variant 2:** `RS_MR_BB_RSI_22_STD_V1` — 20-period Bollinger Band, 2.2 standard deviations, RSI(14) $\le 30.0$.
3. **Variant 3:** `RS_MR_BB_RSI_25_STD_V1` — 20-period Bollinger Band, 2.5 standard deviations, RSI(14) $\le 28.0$.

All variants required bullish rejection confirmation ($\text{Close} > \text{Open}$), an ATR(14) stop-loss multiplier of 1.5x, and a target exit at the middle band (20-period SMA).

---

### 2. Quantitative Performance Comparison

| Performance Metric | Variant 1 (2.0 Std Dev) | Variant 2 (2.2 Std Dev) | Variant 3 (2.5 Std Dev) |
| :--- | :---: | :---: | :---: |
| **Strategy ID** | `RS_MR_BB_RSI_20_STD_V1` | `RS_MR_BB_RSI_22_STD_V1` | `RS_MR_BB_RSI_25_STD_V1` |
| **Experiment ID** | `EXP-20261120-123109-938e11` | `EXP-20261120-123252-df4a1b` | `EXP-20261120-123435-0130f0` |
| **Total Return (%)** | **-13.78%** | **-15.83%** | **-7.43%** |
| **Annualized Return (CAGR)** | -2.94% | -3.42% | **-1.54%** |
| **Sharpe Ratio** | **-1.24** | **-2.02** | **-1.24** |
| **Sortino Ratio** | -1.27 | -1.98 | -1.25 |
| **Calmar Ratio** | -0.15 | -0.18 | -0.15 |
| **Max Drawdown (%)** | 20.20% | 18.56% | **10.25%** |
| **Completed Trades** | 752 | 497 | **270** |
| **Win Rate (%)** | 49.07% | 47.28% | **50.00%** |
| **Profit Factor** | 0.77 | 0.72 | **0.81** |
| **Expectancy Per Trade** | -$18.33 | -$31.86 | -$27.52 |
| **Annualized Turnover** | 4.95x | 3.31x | **1.78x** |
| **Market Exposure (%)** | 35.60% | 23.40% | **13.80%** |

---

### 3. Quantitative Analysis & Forensic Findings

#### 3.1 Severe Failure in Intermediate Expansion (2.2 Std Dev)
- Counter-intuitively, moving from 2.0 to 2.2 standard deviations (`RS_MR_BB_RSI_22_STD_V1`) produced the worst performance across the entire 9-candidate pool:
  - Sharpe ratio plunged to **-2.02**.
  - Total return fell to **-15.83%**.
  - Negative expectancy doubled to **-$31.86 per trade**.
- **Root Cause:** Piercing 2.2 standard deviations on hourly candles frequently indicates a genuine structural breakdown rather than a temporary liquidity dip. Buying into 2.2 std dev breakdowns without strong macro trend support "caught falling knives" during trending selloffs.

#### 3.2 Tail Filtering at 2.5 Std Dev
- Demanding 2.5 standard deviations (`RS_MR_BB_RSI_25_STD_V1`) cut trade volume dramatically by $64.1\%$ (270 trades vs 752 trades).
- Maximum drawdown was halved from $20.20\%$ to $10.25\%$, and total loss shrank from $-13.78\%$ to $-7.43\%$.
- However, because reversion exits at the 20 SMA mean have a fixed reward cap, the few trades that failed hit 1.5x ATR stops, leaving the strategy with negative net expectancy (-$27.52/trade).

---

### 4. Recommendation for Phase 3C

Mean reversion as an autonomous standalone entry engine is rejected. The risk of buying into persistent downtrends without higher-timeframe regime conditioning is excessive. In Phase 3C, mean reversion logic should only be evaluated as an oversold dip-buying overlay within confirmed bullish regimes.
