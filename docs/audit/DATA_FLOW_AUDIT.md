# BTC-ML SYSTEM V2 — MARKET DATA FLOW AUDIT
**Phase 0: Market Data Ingestion, Streaming, Candle Integrity & Alignment**  
**Date:** November 18, 2026  
**Auditors:** Senior Algorithmic Trading Engineer, Principal Quantitative Developer  

---

## 1. Data Ingestion Architecture

The market data architecture handles dual-asset classes across two operational modes:
- **Live Paper Trading Mode:** Live polling via `DataProvider.fetch_live_data()` communicating with Alpaca Data REST endpoints.
- **Historical Backtesting Mode:** Local cached CSV loading via `DataProvider.fetch_data(live=False)` or legacy `DataIngestion.fetch_binance_klines()`.

### Data Provider Endpoints
1. **US Equities (`AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`):**
   - Endpoint: `https://data.alpaca.markets/v2/stocks/{symbol}/bars`
   - Feed: `iex` (Investors Exchange - Alpaca free market data tier).
   - Timeframes: `1Hour` (LTF base), `1Day` (HTF trend).
2. **Cryptocurrencies (`BTCUSDT`, `ETHUSDT`):**
   - Endpoint: `https://data.alpaca.markets/v1beta3/crypto/us/bars`
   - Mapped Symbols: `BTC/USD` and `ETH/USD`.
   - Timeframes: `1Hour` and `4Hour` (LTF/HTF).

---

## 2. Symbol Mapping & Representation Audit

The mapping across internal identifiers, Alpaca data queries, Alpaca order submissions, and Alpaca position queries was audited for consistency:

| Internal Symbol | Asset Class | Alpaca Data API Symbol | Alpaca Order API Symbol | Alpaca Position Response Symbol | Alpaca Close Endpoint (`DELETE`) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| `AAPL` | Equity | `AAPL` | `AAPL` | `AAPL` | `/v2/positions/AAPL` | **Consistent** |
| `MSFT` | Equity | `MSFT` | `MSFT` | `MSFT` | `/v2/positions/MSFT` | **Consistent** |
| `NVDA` | Equity | `NVDA` | `NVDA` | `NVDA` | `/v2/positions/NVDA` | **Consistent** |
| `TSLA` | Equity | `TSLA` | `TSLA` | `TSLA` | `/v2/positions/TSLA` | **Consistent** |
| `AMZN` | Equity | `AMZN` | `AMZN` | `AMZN` | `/v2/positions/AMZN` | **Consistent** |
| `BTCUSDT` | Crypto | `BTC/USD` | `BTC/USD` | `BTCUSD` | `/v2/positions/BTCUSD` | **Consistent** |
| `ETHUSDT` | Crypto | `ETH/USD` | `ETH/USD` | `ETHUSD` | `/v2/positions/ETHUSD` | **Consistent** |

*Verification:* In `alpaca_executor.py:164`, `clean_sym = alpaca_sym.replace("/", "")` properly strips the forward slash when calling `DELETE /v2/positions/{clean_sym}`, correctly addressing Alpaca's crypto endpoint convention where order placement requires `BTC/USD` but positions delete requires `BTCUSD`.

---

## 3. Data Integrity & Alignment Findings

### Finding DAT-001: Signal Generation on Incomplete / Unclosed Forming Candles
- **Severity:** HIGH
- **Exact File Path:** `BTC_ML_System/btc_ml_system/src/portfolio_paper_trader.py`
- **Function or Class:** `PortfolioPaperTrader.run_paper_tick` (lines 378-399)
- **Existing Behavior:** The polling loop executes every 30 seconds. On each tick, `DataProvider.fetch_live_data()` fetches the newest bars from Alpaca and immediately evaluates indicators (RSI, Donchian, EMA) on `latest_bar = df_strat.iloc[-1]`.
- **Expected Behavior:** In professional quantitative execution, signals must be evaluated exclusively on **closed, finalized candles** (e.g. `df_strat.iloc[-2]` or candle timestamp validation `now_utc >= candle_close_time`), OR explicitly modeled as an intra-bar tick strategy.
- **Identified Gap:** The latest candle returned by Alpaca during an active hour is the **forming candle**. Its `close` price is the current tick price, its `volume` is only partial, and its `high`/`low` are incomplete. This causes:
  1. **Signal Flickering:** A breakout or RSI condition may trigger at minute 15, place a paper trade, and by minute 59 the candle closes back below the threshold.
  2. **Strategy Mismatch:** In historical backtesting, every candle is fully completed with 100% of volume and finalized range. Evaluating live on an open bar creates substantial execution divergence from backtested performance.
- **Recommended Fix:** Add a candle completion check in `PortfolioPaperTrader`:
  - Either evaluate signal generation on `df.iloc[-2]` (the last finalized bar).
  - Or verify that `latest_bar['close_time'] <= pd.Timestamp.now(tz="UTC")` before generating entry orders.
- **Required Test:** Simulate streaming data for an incomplete bar with fluctuating prices and verify that no order is dispatched until the candle boundary closes.

---

### Finding DAT-002: Warmup Lookback Stitching Discontinuity
- **Severity:** MEDIUM
- **Exact File Path:** `BTC_ML_System/btc_ml_system/src/data_provider.py`
- **Function or Class:** `DataProvider.fetch_live_data` (lines 110-129)
- **Existing Behavior:** If the live API returns fewer than 150 bars, `DataProvider` loads historical candles from `data/raw/{symbol}_{interval}.csv` and concatenates:
  `prior_cache = cache_df[cache_df["open_time"] < min_live_ot]`
  `combined = pd.concat([prior_cache, live_df], ignore_index=True)`
- **Expected Behavior:** Cache stitching must verify continuity. If the gap between `prior_cache["open_time"].max()` and `min_live_ot` exceeds the candle timeframe interval, missing candles must be detected, logged, and either backfilled or alerted.
- **Identified Gap:** The cached raw CSVs in `data/raw/` end in late September 2026. Live candles fetched in November 2026 have an unhandled 2-month gap between `prior_cache` and `live_df`. Calculating rolling indicators (EMA200, 24-bar ATR) across this boundary treats two distant points in time as adjacent bars, distorting moving averages and volatility estimates.
- **Recommended Fix:** Implement automated backfilling via Alpaca REST API pagination to fetch all missing bars between the cache end-date and current time, eliminating the gap before indicator calculation.
- **Required Test:** Unit test stitching where cache ends 30 days prior to live data, asserting that intermediate bars are fetched or an explicit gap warning is raised.

---

### Finding DAT-003: Stale Historical Cache Invalidation in Backtest Mode
- **Severity:** MEDIUM
- **Exact File Path:** `BTC_ML_System/btc_ml_system/src/data_provider.py`
- **Function or Class:** `DataProvider.fetch_data` (lines 56-75)
- **Existing Behavior:** In backtest mode (`live=False`), `DataProvider` loads the cached CSV if `len(df) >= expected_rows`. It does not check the maximum timestamp of the data.
- **Expected Behavior:** The cache validator should check both the row count and the date range (`df['open_time'].max() >= requested_end_date`).
- **Identified Gap:** If an outdated CSV with 2 years of data from 2022-2024 is present, the system loads it silently, ignoring the current market regime or the requested testing window.
- **Recommended Fix:** Add timestamp boundary validation to `DataProvider.fetch_data` comparing `df['open_time'].min()` and `max()` against the requested backtest start and end dates.
- **Required Test:** Test requesting a 2026 backtest when cache only contains 2024 data, verifying that fresh data is ingested.

---

### Finding DAT-004: Missing Candle Handling & Irregular Time Grids
- **Severity:** LOW
- **Exact File Path:** `BTC_ML_System/btc_ml_system/src/data_quality.py`
- **Function or Class:** `DataQualityChecker.check_data_integrity`
- **Existing Behavior:** `DataQualityChecker` checks for missing timestamps using fixed frequency deltas (`freq_map = {"1h": pd.Timedelta(hours=1)}`). However, US Equities only trade 6.5 hours per day (excluding weekends and market holidays), so standard hourly delta checks flag every overnight and weekend period as "missing data".
- **Expected Behavior:** Data quality checks for equities should use an exchange trading calendar (e.g. NYSE/NASDAQ trading sessions).
- **Identified Gap:** Spurious warnings when validating equity datasets; potential masking of genuine mid-session missing candles.
- **Recommended Fix:** Parameterize `DataQualityChecker` with asset class awareness: use continuous 24/7 calendar for crypto and session-aware calendar for equities.
- **Required Test:** Run data quality check on `aapl_1h.csv` and verify zero false-positive alerts across weekend boundaries.
