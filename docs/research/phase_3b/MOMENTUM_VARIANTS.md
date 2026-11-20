# MOMENTUM VARIANTS
## Controlled Expansion & Breakout Window Sensitivity

**Repository:** `BTC_ML_System`  
**Branch:** `feat/phase-3b-strategy-evaluation`  
**Strategy Family:** Momentum (Time-Series Donchian Breakouts with RSI Ceiling & Trailing Exits)  
**Universe:** Multi-Asset Portfolio (AAPL, MSFT, NVDA, TSLA, AMZN, BTCUSDT, ETHUSDT)

---

### 1. Pre-Registered Momentum Hypotheses

To examine whether breakout lookback duration improves signal robustness, three pre-registered variants were tested:
1. **Variant 1 (Baseline):** `RS_MOM_DONCHIAN_20_V1` — 20-bar breakout, 10-bar exit channel.
2. **Variant 2:** `RS_MOM_DONCHIAN_40_V1` — 40-bar breakout, 20-bar exit channel.
3. **Variant 3:** `RS_MOM_DONCHIAN_55_V1` — 55-bar breakout, 25-bar exit channel.

All variants shared identical secondary filtering:
- Positive momentum over the lookback window ($\text{Close}_t > \text{Close}_{t-k}$).
- RSI(14) $< 75.0$ exhaustion ceiling.
- ATR(14) stop-loss multiplier: 2.0x ATR.
- Take-profit multiplier: 4.5x ATR.

---

### 2. Quantitative Performance Comparison

| Performance Metric | Variant 1 (Donchian 20) | Variant 2 (Donchian 40) | Variant 3 (Donchian 55) |
| :--- | :---: | :---: | :---: |
| **Strategy ID** | `RS_MOM_DONCHIAN_20_V1` | `RS_MOM_DONCHIAN_40_V1` | `RS_MOM_DONCHIAN_55_V1` |
| **Experiment ID** | `EXP-20261120-122555-e8bcab` | `EXP-20261120-122739-ab5bf6` | `EXP-20261120-122925-e860a1` |
| **Total Return (%)** | **-12.13%** | **-5.46%** | **-9.35%** |
| **Annualized Return (CAGR)** | -2.57% | **-1.12%** | -1.95% |
| **Sharpe Ratio** | **-0.75** | **-0.40** | **-0.79** |
| **Sortino Ratio** | -0.73 | **-0.38** | -0.76 |
| **Calmar Ratio** | -0.17 | **-0.10** | -0.17 |
| **Max Drawdown (%)** | 15.48% | **10.71%** | 11.55% |
| **Completed Trades** | 910 | **575** | **476** |
| **Win Rate (%)** | 53.30% | **55.48%** | 54.62% |
| **Profit Factor** | 0.88 | **0.94** | 0.89 |
| **Expectancy Per Trade** | -$13.33 | **-$9.50** | -$19.64 |
| **Annualized Turnover** | 6.22x | **3.88x** | **3.15x** |
| **Market Exposure (%)** | 42.18% | **31.25%** | **28.40%** |
| **Research Status** | Candidate Evaluated | **Top Evaluated Candidate** | Candidate Evaluated |

---

### 3. Quantitative Analysis & Structural Insights

#### 3.1 Variant 2 (`RS_MOM_DONCHIAN_40_V1`) Emerges as Top Overall Performer
Across the entire 9-candidate research pool, `RS_MOM_DONCHIAN_40_V1` achieved the highest relative performance:
- Highest Sharpe ratio: **-0.40** (vs. -0.75 for Donchian 20 and -1.74 for Trend Following).
- Lowest relative drawdown among momentum candidates: **10.71%** (vs. 15.48% for Donchian 20).
- Best win rate: **55.48%** with a profit factor of **0.94**.

#### 3.2 Friction Reduction Mechanism
The primary driver of outperformance in Variant 2 was the reduction in transaction friction. 
- Donchian 20 triggered 910 trades, generating $6.22\times$ annual portfolio turnover. Each round trip consumed 20 bps on crypto and 4 bps on equities.
- Donchian 40 reduced trade count by $36.8\%$ (575 trades) and lowered turnover to $3.88\times$, avoiding substantial slippage churn without compromising breakout capture.

#### 3.3 Degradation at Donchian 55
Extending the lookback further to 55 bars (`RS_MOM_DONCHIAN_55_V1`) deteriorated performance:
- Sharpe dropped back to $-0.79$, and total return dropped to $-9.35\%$.
- A 55-bar breakout on hourly data is excessively slow, missing early breakout momentum and buying closer to exhaustion tops where risk/reward is less favorable.

---

### 4. Recommendation for Phase 3C

`RS_MOM_DONCHIAN_40_V1` represents the most viable candidate for further research. When combined with volatility-regime conditioning (which eliminated losses during ranging regimes), Donchian 40 breakout logic shows potential as a directional feature in multi-strategy ensembles.
