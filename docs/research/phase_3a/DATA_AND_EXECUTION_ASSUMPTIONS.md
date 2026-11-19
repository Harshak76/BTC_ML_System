# PHASE 3A — DATA & EXECUTION ASSUMPTIONS SPECIFICATION

**Specification Version:** 1.0.0  
**Status:** `RESEARCH & SIMULATION STANDARD`

---

## 1. Overview

This document specifies the market data ingestion standards, cleaning protocols, execution models, and transaction cost assumptions enforced across all quantitative research in Phase 3.

---

## 2. Research Universe & Market Data Sources

### 2.1. Supported Research Assets
- **US Equities (50% Basket):** `AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`
- **Cryptocurrency (50% Basket):** `BTCUSDT` (25%), `ETHUSDT` (25%)
- **Timeframes:** Primary `1h`; Secondary `4h`, `1d`.

### 2.2. Data Limitations of Free Historical Sources
1. **Survivorship Bias:** The equity basket consists of mega-cap survivors of the 2024–2026 market regime. While acceptable for initial factor research, true universe validation requires survivor-bias-free historical constituents.
2. **Missing Bid-Ask Depth:** Free CSV/REST sources provide OHLCV bars without Level 2 order book depth. Slippage must be modeled statistically rather than simulated from historical order queues.
3. **Stitching & Splits:** Stock dividends and splits must be backward-adjusted to avoid artificial price discontinuities (audited under Phase 1 `DAT-002`).

---

## 3. Data Cleaning, Filtering & Temporal Integrity

### 3.1. Completed Candle Enforcement (`DAT-001`)
- Signals are strictly evaluated on completed candles where `close_time <= current_time`.
- In-progress live candles are filtered out prior to signal generation to prevent intra-bar lookahead and phantom fills.

### 3.2. Warm-Up Requirements
- Every indicator requires a defined historical warm-up window before its output is mathematically valid:
  - Slow EMA (55 bars) $\implies \ge 55$ bars warm-up.
  - Volatility Regime Ratio ($\text{ATR}_{100}$) $\implies \ge 100$ bars warm-up.
- Signals generated during the warm-up window are forced to `0` (flat) to prevent small-sample edge effects.

### 3.3. Duplicate & Missing Bar Protocol
- Duplicate timestamps are rejected at ingestion via `drop_duplicates(subset=['open_time'])`.
- Missing intervals (e.g. weekend crypto gaps or equity market closures) are not forward-filled with zero volume; rather, intervals reflect true chronological trading bars.

---

## 4. Execution Simulation Mechanics

### 4.1. Next-Bar Open Timing (`BKT-001`)
- All research simulations implement **next-bar open execution**:
  $$\text{Signal Generated: Close of Bar } t$$
  $$\text{Order Filled: Open of Bar } t+1$$
- Eliminates "same-bar close" execution bias where a strategy enters at the close price that generated the signal.

### 4.2. Asset-Specific Transaction Cost Schedules

| Asset Class | Execution Target | Entry Slippage | Exit Slippage | Exit Commission | Total Round-Trip Friction |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **US Equities** | Alpaca Equities | 2.0 bps | 2.0 bps | 0.0 bps | **4.0 bps (0.04%)** |
| **Cryptocurrency** | Binance Spot | 5.0 bps | 5.0 bps | 10.0 bps | **20.0 bps (0.20%)** |
| **Stress Benchmark** | 2x Cost Stress | 10.0 bps | 10.0 bps | 20.0 bps | **40.0 bps (0.40%)** |

---

## 5. Return Unit Standardization & Boundary Validation

To eliminate the scale confusion identified during the Phase 2.3 audit:
1. **System Standard:** All periodic return series, trade PnLs, and performance reports are standardized in **`PERCENTAGE_POINTS`** (e.g., $+1.50$ represents $+1.50\%$).
2. **Boundary Validation (`validate_return_units`):**
   - Decimal fractions (e.g. $0.015$) are rejected if percentage points are expected.
   - Percentage points (e.g. $15.0$) are rejected if decimal fractions are expected.
   - Parameter stability calculations receive return inputs strictly scaled in percentage points.

---

## 6. Historical Data Contamination Disclosure

The historical multi-asset dataset spanning 2024 through 2026 was repeatedly queried and backtested during Phase 0, Phase 1, and Phase 2.

**Fiduciary Rule:**
The 2024–2026 historical holdout slice ($20\%$) is formally declared **`is_contaminated: True`**. It is useful for relative hypothesis ranking, but cannot serve as certified unpolluted validation. Prospective live paper execution on future, unseen market data is mandatory before any live deployment.
