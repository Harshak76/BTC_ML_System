# PHASE 3A — MARKET REGIME RESEARCH SPECIFICATION

**Module:** `btc_ml_system.src.regimes`  
**Phase:** Phase 3A Research Foundation  
**Status:** `RESEARCH SPECIFICATION`

---

## 1. Overview & Research Objectives

Financial market series are non-stationary; returns alternate between distinct statistical regimes characterized by varying volatility levels, autocorrelation dynamics, and directional persistence.

No single strategy archetype possesses an invariant statistical edge across all market environments:
- **Trend Following** thrives in directional, high-persistence regimes but bleeds capital during low-volatility ranges.
- **Mean Reversion** generates consistent returns in range-bound, oscillating environments but suffers severe drawdowns when markets transition into explosive trends.
- **Momentum** captures explosive breakout expansions but fails at market exhaustion points.

The objective of quantitative regime research in Phase 3 is to establish an objective, zero-lookahead regime classification engine that dynamically conditions strategy activation, position sizing, and stop distance.

---

## 2. Volatility Regimes: CALM, NORMAL, HIGH

### 2.1. Mathematical Definition
Volatility regimes are classified using the ratio of short-term ATR (14 bars) to long-term rolling ATR (100 bars):

$$\text{VolRatio}[t] = \frac{ATR_{14}[t]}{ATR_{100}[t]}$$

$$\text{Volatility Regime}[t] = \begin{cases}
\text{CALM} & \text{if } \text{VolRatio}[t] < 0.75 \\
\text{HIGH} & \text{if } \text{VolRatio}[t] > 1.35 \\
\text{NORMAL} & \text{otherwise}
\end{cases}$$

### 2.2. Quantitative Behavior Across Volatility States

| Regime | Market Characteristics | Strategy Suitability | Risk Adjustments |
| :--- | :--- | :--- | :--- |
| **CALM** | Tight trading ranges, low realized volatility, narrow ATR | Mean Reversion, Range Scalping | Standard stops; normal position sizes |
| **NORMAL** | Healthy price movement, orderly trends, liquid books | Trend Following, Momentum Breakouts | Standard $2.0\times ATR$ stops |
| **HIGH** | Extreme volatility shocks, wide spreads, news events | Capital Preservation / Defensive Momentum | Widen stops ($2.5\text{--}3.0\times ATR$), reduce sizing by 50% |

---

## 3. Directional Regimes: Trend vs. Range

To complement volatility classification, a secondary structural filter identifies whether the market is actively trending or cycling within a trading range:

### 3.1. Directional Indicators
1. **Trend Strength (ADX):**
   $$ADX_{14}[t] \ge 25.0 \implies \text{Trending Market}$$
   $$ADX_{14}[t] < 20.0 \implies \text{Ranging / Mean-Reverting Market}$$
2. **Band Squeeze / Expansion (Bollinger Band Width):**
   $$BBW[t] = \frac{\text{BB}_{\text{upper}}[t] - \text{BB}_{\text{lower}}[t]}{\text{BB}_{\text{middle}}[t]}$$
   A low $BBW$ percentile ($< 15\%$) indicates volatility compression (imminent breakout). An expanding $BBW$ confirms active directional dispersion.

---

## 4. Zero-Lookahead Guarantee & Temporal Integrity

A critical failure point in historical regime research is using centered moving averages, global quantile cuts, or forward-peeking filters (such as full-sample HMM or Hodrick-Prescott filters) that use future price knowledge to label historical regimes.

### Zero-Lookahead Rules:
1. **Strictly Backward-Looking:** Every rolling statistic ($\text{ATR}_{14}$, $\text{ATR}_{100}$, $\text{ADX}_{14}$, $\text{BBW}$) at bar $t$ is computed strictly over bars $\{t-k, \dots, t\}$.
2. **Expanding / Rolling Quantiles:** Regime cutoff thresholds are either fixed institutional constants (e.g. $0.75$ / $1.35$) or computed via expanding historical windows that never incorporate future bars.
3. **Completed Candle Filtering:** Signals and regime classifications are evaluated strictly at the close of bar $t$ for execution on bar $t+1$.

---

## 5. Strategy Conditioning Framework for Phase 3B

In Phase 3B, regime classification will formally gate strategy candidate activation:

```
[Market Regime Classifier]
        │
        ├── Volatility == CALM & ADX < 20
        │     └──► Activate: RS_MR_BB_RSI_REVERSION_V1 (Mean Reversion)
        │
        ├── Volatility == NORMAL & ADX >= 25
        │     └──► Activate: RS_TF_DUAL_EMA_ATR_V1 (Trend Following)
        │
        ├── Volatility == HIGH & BBW Expanding
        │     └──► Activate: RS_MOM_TSMOM_BREAKOUT_V1 (Momentum Breakout)
        │
        └── Volatility == EXTREME (> 2.0x ATR)
              └──► Activate: Cash Preservation Mode (Circuit Breaker)
```
