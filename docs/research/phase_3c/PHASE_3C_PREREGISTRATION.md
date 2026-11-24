# BTC-ML SYSTEM V2 — PHASE 3C PRE-REGISTRATION
## Controlled Strategy Filter Experiment: Donchian40 + ADX + 4H EMA Confirmation

- **Repository:** `BTC_ML_System`
- **Branch:** `feat/phase-3c-controlled-filter-experiment`
- **Starting Commit:** `097952ad52f8eaeea11e0f649f1957041e214ac6` (`097952a`)
- **Execution Mode:** Offline Quantitative Research Only.
- **Operating Status:**
  - Broker Connections: `DISABLED / DISALLOWED`
  - Order Placement: `DISABLED / DISALLOWED`
  - Paper Trading: `NOT ELIGIBLE` (Baseline frozen as `REJECTED — NOT ELIGIBLE FOR PAPER TRADING`)
  - Live Trading: `STRICTLY PROHIBITED`
  - Parameter Mining / Curve-Fitting: `STRICTLY PROHIBITED`
- **Disclosure Statement:**
  > **`HISTORICAL EXPLORATORY EVALUATION — PRIOR DATASET INSPECTION DISCLOSED`**  
  > Market data across the 2024–2026 historical window has been inspected in previous development and verification phases (Phase 3A, Phase 3B, Phase 3B.1, Phase 3B.2). Consequently, any out-of-sample or walk-forward partitions evaluated in Phase 3C constitute historical exploratory research and must not be represented as uninspected holdout confirmation.

---

## 1. RESEARCH OBJECTIVE & BACKGROUND

In Phase 3B and Phase 3B.2, the 40-bar Donchian breakout variant (`RS_MOM_DONCHIAN_40_V1`) was identified as the single top-performing momentum candidate among the evaluated baseline set, achieving a standalone asset-level annualized Sharpe of +0.3807 on BTCUSDT. However, under full multi-asset portfolio evaluation and realistic transaction friction models, all candidates exhibited negative portfolio-level returns and elevated drawdown due to whipsaws in sideways/consolidating regimes and counter-trend entries against higher-timeframe market structure.

Phase 3C investigates whether adding two distinct, pre-registered economic filters to the Donchian 40 momentum core can statistically improve risk-adjusted returns and reduce drawdowns without data dredging:
1. **Trend Strength Filter:** 14-period Average Directional Index ($ADX_{14} \ge 25$).
2. **Multi-Timeframe Trend Direction Filter:** 4-Hour Exponential Moving Average slope ($Slope_{4H\_EMA20} > 0$) using strictly completed 4H bars.

---

## 2. FORMAL CANDIDATE SPECIFICATIONS

All candidates are implemented within the isolated research package `btc_ml_system.src.research.strategies` and registered in `ResearchStrategyRegistry`. They share identical position sizing, execution mechanics, and risk management bounds.

### Candidate 1: Control Benchmark (`RS_MOM_DONCHIAN_40_CONTROL`)
- **Strategy ID:** `RS_MOM_DONCHIAN_40_CONTROL`
- **Family:** `StrategyFamily.MOMENTUM`
- **Hypothesis:** Replicates the baseline Donchian 40 breakout mechanism from Phase 3B. Time-series momentum produces upward price drift upon breaking the 40-bar channel high, provided RSI is not exhausted.
- **Parameters:**
  - `channel_entry_period`: 40 bars (1H)
  - `channel_exit_period`: 20 bars (1H)
  - `mom_period`: 40 bars (1H)
  - `rsi_period`: 14 bars (1H)
  - `rsi_max_entry`: 75.0
  - `atr_period`: 14 bars (1H)
  - `atr_stop_multiplier`: 2.0
  - `atr_tp_multiplier`: 4.5
  - `trailing_stop_pct`: 0.02 (2.0%)
- **Entry Rules (at completed 1H bar $t$ close):**
  1. $Close_t > \max_{i=1..40}(High_{t-i})$ (Channel Breakout)
  2. $Momentum_t = \frac{Close_t - Close_{t-40}}{Close_{t-40}} > 0$ (Positive Momentum)
  3. $RSI_{14, t} < 75.0$ (RSI Exhaustion Ceiling)
- **Exit Rules:**
  1. Channel Exit: $Close_t < \min_{i=1..20}(Low_{t-i})$
  2. Stop Loss: $Price \le FillPrice - 2.0 \times ATR_{14}$
  3. Take Profit: $Price \ge FillPrice + 4.5 \times ATR_{14}$
  4. Trailing Stop: $Price \le High_{post\_entry} \times (1 - 0.02)$

---

### Candidate 2: ADX Trend Strength Confirmation (`RS_MOM_DONCHIAN_40_ADX25`)
- **Strategy ID:** `RS_MOM_DONCHIAN_40_ADX25`
- **Family:** `StrategyFamily.MOMENTUM`
- **Hypothesis:** Donchian breakouts suffer heavy false-breakout losses during low-volatility, directionless range-bound regimes. Requiring $ADX_{14} \ge 25$ at signal candle close restricts entries to regimes with established directional momentum, filtering out chop.
- **Parameters:**
  - Inherits all Candidate 1 parameters.
  - `adx_period`: 14 bars (1H)
  - `adx_threshold`: 25.0
- **Mathematical Formulation:**
  - $TR_t = \max(High_t - Low_t, |High_t - Close_{t-1}|, |Low_t - Close_{t-1}|)$
  - $+DM_t = (High_t - High_{t-1})$ if $(High_t - High_{t-1} > Low_{t-1} - Low_t)$ and $> 0$, else $0$
  - $-DM_t = (Low_{t-1} - Low_t)$ if $(Low_{t-1} - Low_t > High_t - High_{t-1})$ and $> 0$, else $0$
  - Smoothed values using Wilder's 14-period smoothing:
    $S(X)_t = S(X)_{t-1} \times \frac{13}{14} + X_t \times \frac{1}{14}$
  - $+DI_{14, t} = 100 \times \frac{S(+DM)_t}{S(TR)_t}$
  - $-DI_{14, t} = 100 \times \frac{S(-DM)_t}{S(TR)_t}$
  - $DX_t = 100 \times \frac{|+DI_{14, t} - -DI_{14, t}|}{+DI_{14, t} + -DI_{14, t} + 10^{-12}}$
  - $ADX_{14, t} = S(DX)_t$ (Wilder's smoothed $DX$)
- **Entry Rules:**
  - Control Entry Signal $= 1$ **AND** $ADX_{14, t} \ge 25.0$
- **Exit Rules:**
  - Identical to Candidate 1 (Control).

---

### Candidate 3: Multi-Timeframe 4H EMA Slope Confirmation (`RS_MOM_DONCHIAN_40_4H_EMA_SLOPE`)
- **Strategy ID:** `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE`
- **Family:** `StrategyFamily.MOMENTUM`
- **Hypothesis:** 1H breakouts that trade counter to the intermediate 4H trend suffer adverse selection. Aligning 1H entries with a rising 4H EMA ($Slope_{4H\_EMA20} > 0$) filters out bear-market rallies and false counter-trend breakouts.
- **Parameters:**
  - Inherits all Candidate 1 parameters.
  - `htf_timeframe`: `"4h"`
  - `htf_ema_period`: 20 bars (4H)
- **Mathematical Formulation & Strict Zero-Lookahead Rule:**
  - Resample 1H bars into completed 4H bars strictly aligned on UTC intervals: `00:00, 04:00, 08:00, 12:00, 16:00, 20:00`.
  - For completed 4H bar $k$ closing at $T_{close, 4H, k}$:
    $EMA_{4H, 20}[k] = \alpha \cdot Close_{4H, k} + (1 - \alpha) \cdot EMA_{4H, 20}[k-1], \quad \alpha = \frac{2}{20 + 1}$
    $Slope_{4H, k} = EMA_{4H, 20}[k] - EMA_{4H, 20}[k-1]$
  - **Strict Lookahead Prevention:**
    At 1H bar close $t$ (e.g., 14:00 UTC), the current 4H bar (12:00–16:00 UTC) is **forming and incomplete**. The strategy must only reference the latest *completed* 4H bar whose close time $T_{close, 4H} \le T_{open, 1H, t} + 1\text{ hour}$.
    Forming 4H data is strictly masked and inaccessible.
- **Entry Rules:**
  - Control Entry Signal $= 1$ **AND** $Slope_{4H\_EMA20}[k_{completed}] > 0$
- **Exit Rules:**
  - Identical to Candidate 1 (Control).

---

## 3. FORMAL HYPOTHESES

### Test A: ADX Trend Strength Filter
- **Null Hypothesis ($H_{0, A}$):**
  Adding the $ADX_{14} \ge 25$ filter does not produce a statistically significant increase in the portfolio net annualized Sharpe ratio over the Control candidate across the 7 assets after transaction costs:
  $$H_{0, A}: \text{Sharpe}_{\text{ADX25}} \le \text{Sharpe}_{\text{Control}}$$
- **Alternative Hypothesis ($H_{1, A}$):**
  Adding the $ADX_{14} \ge 25$ filter produces a statistically significant increase in portfolio net annualized Sharpe ratio and reduction in maximum drawdown:
  $$H_{1, A}: \text{Sharpe}_{\text{ADX25}} > \text{Sharpe}_{\text{Control}}$$

### Test B: 4H EMA Slope Filter
- **Null Hypothesis ($H_{0, B}$):**
  Adding the positive 4H EMA slope filter does not produce a statistically significant increase in the portfolio net annualized Sharpe ratio over the Control candidate across the 7 assets after transaction costs:
  $$H_{0, B}: \text{Sharpe}_{\text{4H\_EMA}} \le \text{Sharpe}_{\text{Control}}$$
- **Alternative Hypothesis ($H_{1, B}$):**
  Adding the positive 4H EMA slope filter produces a statistically significant increase in portfolio net annualized Sharpe ratio and reduction in maximum drawdown:
  $$H_{1, B}: \text{Sharpe}_{\text{4H\_EMA}} > \text{Sharpe}_{\text{Control}}$$

---

## 4. EXECUTION, SIZING & TRANSACTION COST PROTOCOL

All backtests must be conducted using the standard `ResearchSimulationRunner` engine with identical portfolio parameters:
- **Initial Capital:** $\$100,000.00$ USD.
- **Max Open Positions:** 4 concurrent assets.
- **Risk per Trade:** $0.5\%$ ($50\text{ bps}$) of current portfolio equity.
- **Execution Timing:** Strictly next-bar open ($t+1$).
- **Intrabar Collision Rule:** If high $\ge$ TP and low $\le$ SL in the same bar, assume SL is triggered first (conservative).
- **Transaction Costs:**
  - **Crypto (BTCUSDT, ETHUSDT):** 5 bps slippage entry + 5 bps slippage exit + 10 bps commission per side. Continuous 24/7 trading.
  - **Equities (AAPL, MSFT, NVDA, TSLA, AMZN):** 2 bps slippage entry + 2 bps slippage exit + 0 bps commission. Regular session only (14:00 to 21:00 UTC, Mon–Fri).
- **Accounting Identity:**
  $$\text{Portfolio Equity}_t = \text{Cash}_t + \sum_{i} \text{Quantity}_{i, t} \times \text{MarkPrice}_{i, t}$$
  Forward returns must strictly preserve this balance sheet identity.

---

## 5. STATISTICAL VALIDATION & ACCEPTANCE CRITERIA

### Nine Acceptance Gates
To be considered for potential paper trading eligibility in subsequent phases, a candidate must pass all 9 pre-registered gates:

| Gate | Metric / Test | Passing Threshold | Rationale |
|---|---|---|---|
| **Gate 1** | Portfolio Net Annualized Sharpe | $\text{Sharpe} > 1.00$ | Standard hurdle for systematic multi-asset momentum |
| **Gate 2** | Maximum Drawdown | $\text{MaxDD} < 20.0\%$ | Portfolio capital preservation constraint |
| **Gate 3** | Multi-Asset Breadth | $\ge 4$ of 7 assets profitable | Prevents single-asset outlier bias |
| **Gate 4** | Deflated Sharpe Ratio (DSR) | $p\text{-value} < 0.05$ | Corrects for multiple testing across trials ($N \ge 12$) |
| **Gate 5** | Stationary Bootstrap | $95\%\text{ CI lower bound} > 0$ | Robustness against time-series resampling |
| **Gate 6** | Monte Carlo Stress Test | Survival Rate $> 95\%$ | Resilient to 2x slippage/commissions and 5% dropouts |
| **Gate 7** | Lookahead Bias Audit | Zero lookahead violations | Strict verification of $t+1$ execution & MTF isolation |
| **Gate 8** | PBO / CSCV Evaluation | PBO Status Documented | Recorded as INCOMPLETE ($N=3 < 4$) without inflation |
| **Gate 9** | Walk-Forward Efficiency | WFE Ratio $> 0.50$ | Out-of-sample consistency across rolling folds |

### Trial Accounting Protocol for DSR
- Phase 3B evaluated 9 variants ($N_{3B} = 9$).
- Phase 3C evaluates 3 candidates ($N_{3C} = 3$).
- Cumulative trial count: $N_{total} = 9 + 3 = 12$ trials.
- DSR calculation must use $N \ge 12$ to penalize selection bias across the entire research lineage.

### PBO Pool Adequacy Rule
- Combinatorially Symmetric Cross-Validation (CSCV) requires $N \ge 4$ genuine candidate strategies to partition candidate pairs and rank out-of-sample winners.
- With $N = 3$ candidates in Phase 3C, CSCV cannot form valid candidate subsets.
- In accordance with Phase 3B.2.2 governance rules, synthetic Gaussian perturbation is strictly prohibited.
- The PBO report must formally state: `PBO: INCOMPLETE — INSUFFICIENT GENUINE CANDIDATE POOL`.

---

## 6. PRE-REGISTRATION COMMITMENT

This document is formally committed to git prior to executing any backtest simulations or statistical tests for Phase 3C. Any subsequent alteration to parameters, thresholds, or candidate definitions constitutes an audit violation.
