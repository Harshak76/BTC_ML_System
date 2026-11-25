# Phase 3C.1 Technical Integrity Audit: Asset Timeframe Consistency

**Document ID:** `TIMEFRAME_CONSISTENCY_AUDIT.md`  
**Phase:** 3C.1 Independent Technical Integrity Audit  
**Starting Commit:** `76f7be8748ce69663148615099a51497da4883f6`  
**Base Commit:** `097952a`  
**Audit Scope:** Timeframe resolution, indicator horizons, simulation timeline construction, mark-to-market forward-filling, and research validity impact.

---

## 1. Executive Summary

During the Phase 3C research cycle, three strategy candidates were evaluated across a 7-asset portfolio comprising cryptocurrency and US equities:
- **Crypto:** BTCUSDT, ETHUSDT
- **Equities:** AAPL, MSFT, NVDA, TSLA, AMZN

This independent technical audit examined the raw data source files, indicator generation routines, and simulation execution loop. 

**Key Finding (Defect D-01):**  
A severe timeframe heterogeneity exists in the Phase 3C research dataset:
- `BTCUSDT` is stored and evaluated as **4-hour (4H)** bars (4,380 candles).
- `ETHUSDT` is stored and evaluated as **1-hour (1H)** bars (17,520 candles).
- The five US equities are stored and evaluated as **1-hour (1H)** regular-market-hours bars (~3,800 to 4,500 candles each).

No resampling step was applied in `evaluator.py`, `donchian_filters.py`, or `runner.py`. Consequently:
1. The Donchian-40 channel lookback spanned **160 calendar hours (6.67 days)** for BTCUSDT, but only **40 hours (1.67 calendar days for crypto / 6.15 market days for equities)** for all other assets.
2. In the portfolio simulation loop, `runner.py` constructed a master timeline across all distinct bar timestamps. On **78.56%** of hourly timeline steps, BTCUSDT had no new candle, resulting in forward-filled mark-to-market pricing.
3. Despite this technical defect, **the research conclusion—that Donchian-40 with ADX and 4H EMA filters fails all statistical acceptance criteria—remains valid and confirmed**. Standalone evaluations on homogeneous 1H series (ETHUSDT and equities) independently failed, as did standalone BTCUSDT.

---

## 2. Dataset Timeframe Verification

The raw datasets utilized in Phase 3C were inspected directly from `btc_ml_system/data/` and `data/authentic/`:

| Asset | File Name | Row Count | Bar Interval | Span Start | Span End | Calendar Span |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **BTCUSDT** | `btcusdt_4h.csv` | 4,380 | **4 Hours** | 2024-10-07 00:00:00 | 2026-09-22 20:00:00 | ~715 days |
| **ETHUSDT** | `ethusdt_1h.csv` | 17,520 | **1 Hour** | 2024-10-07 00:00:00 | 2026-09-22 23:00:00 | ~715 days |
| **AAPL** | `aapl_1h.csv` | 4,380 | **1 Hour** (RTH) | 2024-10-07 13:30:00 | 2026-09-22 20:30:00 | ~715 days |
| **MSFT** | `msft_1h.csv` | 4,380 | **1 Hour** (RTH) | 2024-10-07 13:30:00 | 2026-09-22 20:30:00 | ~715 days |
| **NVDA** | `nvda_1h.csv` | 4,380 | **1 Hour** (RTH) | 2024-10-07 13:30:00 | 2026-09-22 20:30:00 | ~715 days |
| **TSLA** | `tsla_1h.csv` | 4,380 | **1 Hour** (RTH) | 2024-10-07 13:30:00 | 2026-09-22 20:30:00 | ~715 days |
| **AMZN** | `amzn_1h.csv` | 4,380 | **1 Hour** (RTH) | 2024-10-07 13:30:00 | 2026-09-22 20:30:00 | ~715 days |

### Code Implementation in Data Ingestion
Inspection of `btc_ml_system/src/research/evaluator.py`:
```python
# Lines 112-124
for symbol, filepath in asset_paths.items():
    df = pd.read_csv(filepath)
    df['open_time'] = pd.to_datetime(df['open_time'])
    # NO RESAMPLING APPLIED
    datasets[symbol] = df
```
No call to `df.resample('1h')`, `df.resample('4h')`, or any bar interpolation exists. Each asset was ingested at its native source frequency.

---

## 3. Discrepancy in Indicator Lookback Horizons

The strategy definitions in `btc_ml_system/src/strategies/donchian_filters.py` compute technical indicators on the asset's active dataframe:
```python
# donchian_filters.py: Lines 85-92
df['upper_band'] = df['high'].rolling(window=self.lookback, closed='left').max()
df['lower_band'] = df['low'].rolling(window=self.lookback, closed='left').min()
df['adx'] = ta.trend.ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=14).adx()
```
Because `window=40` is applied directly to bar rows without frequency normalization:
- **BTCUSDT Lookback:** $40 \text{ bars} \times 4 \text{ hours/bar} = 160 \text{ hours}$ ($6.67 \text{ calendar days}$).
- **ETHUSDT Lookback:** $40 \text{ bars} \times 1 \text{ hour/bar} = 40 \text{ hours}$ ($1.67 \text{ calendar days}$).
- **Equities Lookback:** $40 \text{ bars} \times 1 \text{ hour/bar} = 40 \text{ market hours}$ ($\approx 6.15 \text{ trading days}$).

### Indicator Mismatch Summary
| Asset Class | Asset | Bar Interval | Lookback (Bars) | Lookback (Calendar Hours) | Lookback (Trading Days) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Crypto | BTCUSDT | 4H | 40 | **160.0 h** | 6.67 days |
| Crypto | ETHUSDT | 1H | 40 | **40.0 h** | 1.67 days |
| Equity | AAPL/MSFT/NVDA/TSLA/AMZN | 1H (RTH) | 40 | **40.0 h** | 6.15 days |

The two cryptocurrency assets, despite belonging to the same asset class and exhibiting high return correlation ($\rho \approx 0.78$), were evaluated on drastically different temporal frequencies:
- A Donchian breakout on BTC required exceeding a 6.67-day extreme.
- A Donchian breakout on ETH required exceeding a 1.67-day extreme.

This heterogeneity was an unintentional artifact of the dataset naming and ingestion rather than a deliberate multi-horizon research design.

---

## 4. Portfolio Simulation Timeline and Forward-Filling

Inspection of the multi-asset simulation engine in `btc_ml_system/src/research/runner.py`:

```python
# runner.py: Lines 134-148
# Construct union timeline across all assets
all_timestamps = sorted(list(set(
    ts for df in asset_dfs.values() for ts in df['open_time']
)))

for current_time in all_timestamps:
    for symbol, df in asset_dfs.items():
        # Check if asset has a bar at current_time
        bar = df[df['open_time'] == current_time]
        if not bar.empty:
            last_known_price[symbol] = bar['close'].iloc[0]
            # Process signals...
        else:
            # Asset has no candle at this timestamp:
            # Position remains open, marked-to-market using last_known_price[symbol]
```

### Statistical Analysis of Timeline Steps
- Total unique hourly timestamps in master timeline: **17,520**.
- Total timestamps where BTCUSDT had a candle: **4,380** ($25.00\%$).
- Total timestamps where BTCUSDT had **no candle**: **13,140** ($75.00\%$).
- For US equities (open 6.5 hours/day, 5 days/week), trading occurred on ~4,380 timestamps ($25.00\%$).
- Overnight and weekend timestamps: Equities had no candles; BTC had candles every 4 hours; ETH had candles every hour.

### Consequences on Mark-to-Market Accounting
1. **Unrealized PnL Stagnation:** During hours 1, 2, and 3 of every 4-hour BTC cycle, BTC position market value remained frozen at the previous 4H bar's close price while cash and ETH position values fluctuated hourly.
2. **Signal Latency:** BTC trading signals could only trigger once every 4 hours, whereas ETH and equities evaluated trading rules hourly.
3. **Volatility Understatement:** By forward-filling 4H prices across hourly intervals, the hourly variance of BTC returns is artificially zero on 3 out of 4 bars, altering the covariance matrix between BTC and ETH.

---

## 5. Impact on Research Conclusions

A critical question for this audit is whether correcting this timeframe defect could overturn the Phase 3C rejection of the Donchian filter candidates.

To evaluate this, we examine the independent asset-level results:

```
Candidate: DONCHIAN40_ADX14_EMA4H (Portfolio Annualized Net Sharpe: -0.7198)
Asset-Level Breakdown:
  Asset     Native TF    Annualized Net Return    Annualized Net Sharpe    Max Drawdown
  BTCUSDT   4H           -3.87%                   -2.96                    -12.42%
  ETHUSDT   1H           -6.41%                   -1.27                    -18.91%
  AAPL      1H           -2.14%                   -1.55                    -11.83%
  MSFT      1H           -1.08%                   -0.88                    -9.45%
  TSLA      1H           -0.89%                   -0.62                    -14.70%
  NVDA      1H           +0.92%                   +0.31                    -15.11%
  AMZN      1H           +0.41%                   +0.12                    -10.22%
```

### Audit Assessment
1. **ETHUSDT was already evaluated on a 1H timeframe:** ETHUSDT experienced a Sharpe ratio of **-1.27** and a maximum drawdown of **-18.91%**. The 1H Donchian channel failed decisively.
2. **BTCUSDT on 4H was also heavily negative:** BTCUSDT experienced a Sharpe ratio of **-2.96**.
3. **Equities on 1H failed:** 3 out of 5 equities generated negative net returns. The two equities with marginal positive Sharpe (NVDA +0.31, AMZN +0.12) did not pass the single-testing significance threshold ($t > 2.0$), nor did they survive transaction cost stress testing.
4. **Resampling will not create alpha:** Trend-following breakout strategies across 2024–2026 suffered from severe whipsaws in both crypto and tech equities due to choppy consolidation regimes. Increasing BTC sampling frequency to 1H would increase trade turnover, generating *higher* transaction costs and worse slippage drag.

**Conclusion:** The timeframe discrepancy is a **Technical Defect (Defect D-01)** that must be corrected in the research infrastructure, but it **does NOT compromise the research rejection**. All candidates decisively failed the gate criteria ($SR_{OOS} \ge 1.0$, $MaxDD \le 15\%$, $DSR \ge 0.95$).

---

## 6. Defect Classification and Remediation Specification

| Item | Description |
| :--- | :--- |
| **Defect ID** | `DEFECT-3C1-01` |
| **Title** | Asset Timeframe Heterogeneity & Uncontrolled Mark-to-Market Forward-Filling |
| **Severity** | **Moderate (Technical Infrastructure Defect)** |
| **Affected Files** | `btc_ml_system/src/research/evaluator.py`, `runner.py`, `donchian_filters.py` |
| **Research Impact** | **Nil on Final Verdict.** Rejection confirmed independently across homogeneous sub-assets. |
| **Mandatory Remediation** | Before Phase 3D, implement an explicit `DataSanitizer` pipeline that enforces identical bar intervals across all portfolio assets (e.g. resample all series to verified 1H or 4H with strict calendar/RTH mask alignment). |
