# PHASE 3A — RESEARCH HYPOTHESIS: MOMENTUM FAMILY
## CANDIDATE 2: TIME-SERIES MOMENTUM WITH DONCHIAN BREAKOUT & RSI CEILING

**Strategy Identifier:** `RS_MOM_TSMOM_BREAKOUT_V1`  
**Strategy Version:** `1.0.0`  
**Family:** Momentum  
**Implementation File:** `btc_ml_system/src/research/strategies/momentum.py`  
**Configuration File:** `btc_ml_system/configs/research/momentum_v1.yaml`  
**Status:** `RESEARCH HYPOTHESIS — NON-OPTIMIZED BASELINE`

---

## 1. Quantitative Hypothesis & Economic Rationale

### 1.1. Core Hypothesis
Momentum anomalies (Jegadeesh & Titman, 1993; Moskowitz et al., 2012) establish that assets exhibiting strong positive performance over past windows ($L = 20$) tend to continue outperforming in subsequent periods due to investor underreaction, disposition effect, and trend-chasing capital flows.

A classic 20-bar Donchian channel breakout ($\text{Close}[t] > \max_{1 \le i \le 20} \text{High}[t-i]$) identifies a structural breakout through prior resistance.

To prevent buying into exhausted blow-off tops:
1. **Exhaustion Ceiling Filter:** We enforce an RSI filter ($RSI_{14} < 75.0$), disqualifying entries when momentum is statistically overextended.
2. **Positive Return Momentum:** We require cumulative lookback return over 20 bars to be strictly positive ($Mom_{20} > 0.0\%$).
3. **Asymmetric Exit Channel:** While entries require a 20-bar high breakout, exits trigger aggressively on a breach of the trailing 10-bar low, preserving asymmetry.

---

## 2. Mathematical Formulations

### 2.1. Donchian Channels (Lookahead-Protected)
To guarantee zero lookahead bias, channels are shifted by 1 bar:
$$\text{Donchian High}_{20}[t] = \max_{i=1}^{20} \text{High}[t-i]$$
$$\text{Donchian Low}_{10}[t] = \min_{i=1}^{10} \text{Low}[t-i]$$

### 2.2. Cumulative Time-Series Momentum
$$\text{Mom}_{20}[t] = \frac{\text{Close}[t] - \text{Close}[t-20]}{\text{Close}[t-20]} \times 100.0$$

### 2.3. Relative Strength Index (RSI)
$$\Delta P[t] = \text{Close}[t] - \text{Close}[t-1]$$
$$U[t] = \max(\Delta P[t], 0), \quad D[t] = \max(-\Delta P[t], 0)$$
$$RS[t] = \frac{\text{RollingMean}_{14}(U)}{\text{RollingMean}_{14}(D) + 10^{-12}}, \quad RSI_{14}[t] = 100.0 - \frac{100.0}{1.0 + RS[t]}$$

---

## 3. Explicit Entry and Exit Specifications

### 3.1. Entry Long Conditions (Evaluated at Completed Bar Close $t$)
A long order is scheduled for execution at bar $t+1$ `open` if all conditions are satisfied:
1. **Donchian Breakout:** $\text{Close}[t] > \text{Donchian High}_{20}[t]$
2. **Positive Trend Momentum:** $\text{Mom}_{20}[t] > 0.0\%$
3. **Exhaustion Ceiling:** $RSI_{14}[t] < 75.0$

### 3.2. Exit Conditions
A position is closed at bar $t+1$ `open` (or intraday on barrier breach) if:
1. **Channel Breakdown:** $\text{Close}[t] < \text{Donchian Low}_{10}[t]$
2. **Stop Loss Breach:** $\text{Low}[t] \le \text{Entry Price} - 2.0 \times ATR_{14}$
3. **Take Profit Target:** $\text{High}[t] \ge \text{Entry Price} + 4.5 \times ATR_{14}$

---

## 4. Execution & Risk Parameters

- **Supported Universe:** `AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`, `BTCUSDT`, `ETHUSDT`
- **Supported Timeframes:** `1h`, `4h`, `1d`
- **Risk per Trade:** $0.50\%$ of portfolio equity
- **Execution Timing:** Next-Bar Open (`open` price of bar $t+1$)
- **Transaction Costs:**
  - Equities: 2 bps entry slippage, 2 bps exit slippage, 0 bps commission (**4 bps round-trip**).
  - Crypto: 5 bps entry slippage, 5 bps exit slippage, 10 bps exit commission (**20 bps round-trip**).

---

## 5. Expected Edge & Known Failure Modes

### Expected Edge:
- Captures high-velocity explosive moves immediately as consolidation ranges break.
- 10-bar exit channel adapts faster than moving averages, protecting open profits during steep pullbacks.

### Known Failure Modes:
- **Bull Traps / False Breakouts:** Breakouts that quickly reverse back into the channel induce full stop-out losses.
- **Slippage on Volatile Bars:** High-momentum breakout candles often experience wider spreads and adverse slippage on open fills.
