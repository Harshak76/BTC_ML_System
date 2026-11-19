# PHASE 3A — RESEARCH HYPOTHESIS: MEAN REVERSION FAMILY
## CANDIDATE 3: BOLLINGER BAND DEVIATION WITH RSI OVERSOLD CONFIRMATION

**Strategy Identifier:** `RS_MR_BB_RSI_REVERSION_V1`  
**Strategy Version:** `1.0.0`  
**Family:** Mean Reversion  
**Implementation File:** `btc_ml_system/src/research/strategies/mean_reversion.py`  
**Configuration File:** `btc_ml_system/configs/research/mean_reversion_v1.yaml`  
**Status:** `RESEARCH HYPOTHESIS — NON-OPTIMIZED BASELINE`

---

## 1. Quantitative Hypothesis & Economic Rationale

### 1.1. Core Hypothesis
In financial markets undergoing consolidation, cyclical ranging, or normal volatility regimes, asset price fluctuations reflect bounded stochastic deviations around a rolling equilibrium price (represented by the 20-period moving average).

When selling pressure pushes price $\ge 2.0$ standard deviations below the mean and RSI drops below 32, liquidity providers exhaust short-term inventory, creating a temporary statistical imbalance.

To capture this reversion safely:
1. **Structural Extremity:** Lower Bollinger Band penetration ($\text{Low} \le \mu - 2\sigma$).
2. **Exhaustion Confirmation:** $RSI_{14} \le 32.0$ guarantees momentum oversold status.
3. **Price Rejection Confirmation:** Enforces a bullish candle ($\text{Close}[t] > \text{Open}[t]$) before triggering, ensuring aggressive selling has halted.
4. **Equilibrium Target:** Exits at the middle band ($\text{SMA}_{20}$), capturing the mean-reversion move without speculating on trend reversal.

---

## 2. Mathematical Formulations

### 2.1. Bollinger Bands (20 Periods, 2 Standard Deviations)
$$\mu_{20}[t] = \frac{1}{20} \sum_{i=0}^{19} \text{Close}[t-i]$$
$$\sigma_{20}[t] = \sqrt{\frac{1}{20} \sum_{i=0}^{19} (\text{Close}[t-i] - \mu_{20}[t])^2}$$
$$\text{BB}_{\text{upper}}[t] = \mu_{20}[t] + 2.0 \cdot \sigma_{20}[t]$$
$$\text{BB}_{\text{lower}}[t] = \mu_{20}[t] - 2.0 \cdot \sigma_{20}[t]$$

### 2.2. Relative Strength Index (RSI)
$$RSI_{14}[t] = 100.0 - \frac{100.0}{1.0 + \frac{\text{RollingMean}_{14}(\max(\Delta P, 0))}{\text{RollingMean}_{14}(\max(-\Delta P, 0)) + 10^{-12}}}$$

---

## 3. Explicit Entry and Exit Specifications

### 3.1. Entry Long Conditions (Evaluated at Completed Bar Close $t$)
A long order is scheduled for execution at bar $t+1$ `open` if all conditions are satisfied:
1. **Lower Band Penetration:** $\text{Low}[t] \le \text{BB}_{\text{lower}}[t]$ OR $\text{Close}[t-1] \le \text{BB}_{\text{lower}}[t-1]$
2. **RSI Oversold:** $RSI_{14}[t] \le 32.0$ OR $RSI_{14}[t-1] \le 32.0$
3. **Bullish Rejection Candle:** $\text{Close}[t] > \text{Open}[t]$ (green bar indicating buying absorption)

### 3.2. Exit Conditions
A position is closed at bar $t+1$ `open` (or intraday on barrier breach) if:
1. **Mean Reversion Target Achieved:** $\text{Close}[t] \ge \mu_{20}[t]$ (Middle Band)
2. **Stop Loss Breach:** $\text{Low}[t] \le \text{Entry Price} - 1.5 \times ATR_{14}$

---

## 4. Execution & Risk Parameters

- **Supported Universe:** `AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`, `BTCUSDT`, `ETHUSDT`
- **Supported Timeframes:** `1h`, `4h`
- **Risk per Trade:** $0.50\%$ of portfolio equity
- **Execution Timing:** Next-Bar Open (`open` price of bar $t+1$)
- **Transaction Costs:**
  - Equities: 2 bps entry slippage, 2 bps exit slippage, 0 bps commission (**4 bps round-trip**).
  - Crypto: 5 bps entry slippage, 5 bps exit slippage, 10 bps exit commission (**20 bps round-trip**).

---

## 5. Expected Edge & Known Failure Modes

### Expected Edge:
- High win rate ($> 60\%$) in non-trending, consolidating markets.
- Uncorrelated return stream to Trend Following and Momentum strategies, providing portfolio diversification.

### Known Failure Modes:
- **Band Walking in Strong Bear Trends:** During macro liquidations or severe down-trends, price can continuously hug the lower band, causing consecutive stop-outs.
- **Tight Profit Target:** Exiting at the 20 SMA caps upside, requiring high win rates to overcome transaction friction.
