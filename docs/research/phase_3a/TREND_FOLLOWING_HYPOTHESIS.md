# PHASE 3A — RESEARCH HYPOTHESIS: TREND FOLLOWING FAMILY
## CANDIDATE 1: DUAL EMA CROSSOVER WITH ATR CHANNEL & TRAILING STOP

**Strategy Identifier:** `RS_TF_DUAL_EMA_ATR_V1`  
**Strategy Version:** `1.0.0`  
**Family:** Trend Following  
**Implementation File:** `btc_ml_system/src/research/strategies/trend_following.py`  
**Configuration File:** `btc_ml_system/configs/research/trend_following_v1.yaml`  
**Status:** `RESEARCH HYPOTHESIS — NON-OPTIMIZED BASELINE`

---

## 1. Quantitative Hypothesis & Economic Rationale

### 1.1. Core Hypothesis
Liquid financial assets (large-cap equities and major cryptocurrencies) display autocorrelated price trends driven by gradual institutional capital reallocation, macro regime shifts, and news diffusion delays.

A dual exponential moving average crossover ($EMA_{21} > EMA_{55}$) identifies the establishment of an intermediate-term trend. However, moving average crossovers are notoriously susceptible to capital erosion in sideways / mean-reverting ranges.

To mitigate whipsaw losses:
1. **Trend Strength Filter:** We enforce an Average Directional Index (ADX) filter ($ADX_{14} \ge 20.0$), ensuring positions are only opened during active directional momentum.
2. **Volatility-Adjusted Stops:** Stop losses are anchored to the Average True Range ($2.0 \times ATR_{14}$), scaling distance dynamically with asset volatility.
3. **Trailing Asymmetry:** A trailing stop ($2.5\%$) locks in accrued gains during extended parabolic trend expansions.

---

## 2. Mathematical Formulations

### 2.1. Exponential Moving Averages
$$\alpha_k = \frac{2}{k + 1}, \quad EMA_k[t] = \alpha_k \cdot P_{\text{close}}[t] + (1 - \alpha_k) \cdot EMA_k[t-1]$$
- Fast Period: $k_1 = 21$
- Slow Period: $k_2 = 55$

### 2.2. Volatility Measurement (Average True Range)
$$\text{TR}[t] = \max\left( \text{High}[t] - \text{Low}[t], |\text{High}[t] - \text{Close}[t-1]|, |\text{Low}[t] - \text{Close}[t-1]| \right)$$
$$ATR_{14}[t] = \frac{1}{14} \sum_{i=0}^{13} \text{TR}[t-i]$$

### 2.3. Trend Strength Filter (ADX)
$$+DM = \begin{cases} \text{High}_t - \text{High}_{t-1} & \text{if } \text{High}_t - \text{High}_{t-1} > \text{Low}_{t-1} - \text{Low}_t \text{ and } > 0 \\ 0 & \text{otherwise} \end{cases}$$
$$-DM = \begin{cases} \text{Low}_{t-1} - \text{Low}_t & \text{if } \text{Low}_{t-1} - \text{Low}_t > \text{High}_t - \text{High}_{t-1} \text{ and } > 0 \\ 0 & \text{otherwise} \end{cases}$$
$$+DI = 100 \cdot \frac{\text{EMA}_{14}(+DM)}{\text{EMA}_{14}(\text{TR})}, \quad -DI = 100 \cdot \frac{\text{EMA}_{14}(-DM)}{\text{EMA}_{14}(\text{TR})}$$
$$DX = 100 \cdot \frac{|+DI - -DI|}{+DI + -DI}, \quad ADX = \text{EMA}_{14}(DX)$$

---

## 3. Explicit Entry and Exit Specifications

### 3.1. Entry Long Conditions (Evaluated at Completed Bar Close $t$)
A long order is scheduled for execution at bar $t+1$ `open` if all conditions are satisfied:
1. **Bullish EMA Cross:** $EMA_{21}[t-1] \le EMA_{55}[t-1]$ AND $EMA_{21}[t] > EMA_{55}[t]$
2. **Trend Strength Confirmation:** $ADX_{14}[t] \ge 20.0$
3. **Price Confirmation:** $\text{Close}[t] > EMA_{21}[t]$

### 3.2. Exit Conditions
A position is closed at bar $t+1$ `open` (or intraday on barrier breach) if any of the following occur:
1. **Bearish Reverse Cross:** $EMA_{21}[t-1] \ge EMA_{55}[t-1]$ AND $EMA_{21}[t] < EMA_{55}[t]$
2. **Stop Loss Breach:** $\text{Low}[t] \le \text{Entry Price} - 2.0 \times ATR_{14}$
3. **Take Profit Target:** $\text{High}[t] \ge \text{Entry Price} + 4.0 \times ATR_{14}$
4. **Trailing Stop Activation:** $\text{Low}[t] \le \text{Highest Price} \times (1.0 - 0.025)$

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
- High payoff ratio ($> 2.5$) during multi-week bull trends (e.g. BTC 2024–2025 cycle, NVDA secular AI run).
- Rapid loss-cutting via volatility stops.

### Known Failure Modes:
- **Range Churn:** Repeated whipsaw crossovers in sideways consolidations where ADX hovers around 20.
- **Top Lag:** Moving averages lag sudden trend reversals (V-tops), causing profit giveback before reverse cross triggers.
