# Phase 3C.1 Technical Integrity Audit: Multi-Timeframe Execution & Lookahead

**Document ID:** `MULTI_TIMEFRAME_EXECUTION_AUDIT.md`  
**Phase:** 3C.1 Independent Technical Integrity Audit  
**Starting Commit:** `76f7be8748ce69663148615099a51497da4883f6`  
**Base Commit:** `097952a`  
**Audit Target:** Strategy Candidate 3 (`CandleDonchian40ADX14EMA4H` / `Donchian40HtfEmaSlopeStrategy`), `donchian_filters.py`, `runner.py`.

---

## 1. Executive Summary

This independent technical audit examined the multi-timeframe implementation of Candidate 3 (`Donchian40HtfEmaSlopeStrategy`), which filters Donchian-40 breakouts using the slope of a 20-period Exponential Moving Average (EMA) computed on a higher timeframe (4H).

### Audit Verdict: VERIFIED — ZERO LOOKAHEAD LEAKAGE
1. **Mathematical Lookahead:** None. The 4H EMA slope calculation strictly references completed 4H bars.
2. **Alignment Mechanism:** Alignment via `pd.merge_asof(..., direction='backward')` correctly maps 1H candle close timestamps to the most recent completed 4H bar's completion timestamp.
3. **Boundary Verification:** Audits at 00:00, 04:00, 08:00, 12:00, 16:00, and 20:00 UTC confirm that forming 4H bars are never accessed prior to their full completion.
4. **Execution Mechanics:** Signals generated at bar close $t$ are queued into `pending_orders` and filled at the open of bar $t+1$ with 5 bps slippage. While zero-latency boundary execution is an idealized modeling assumption, execution latency stress testing proves that latency further degrades performance rather than rescuing it.

---

## 2. Multi-Timeframe EMA Slope Implementation

The 4H EMA slope calculation is defined in `btc_ml_system/src/research/strategies/donchian_filters.py` (lines 368–431):

```python
def _compute_htf_slope(self, df: pd.DataFrame, htf_df: Optional[pd.DataFrame] = None) -> pd.Series:
    open_time = pd.to_datetime(df["open_time"], utc=True)
    close_time = open_time + pd.to_timedelta(1, unit="h")

    time_diffs = open_time.diff().dropna()
    median_hours = (time_diffs.median().total_seconds() / 3600.0) if len(time_diffs) > 0 else 1.0

    if median_hours >= 3.5:
        # Asset is already 4H (BTCUSDT)
        ema = df["close"].ewm(span=self.htf_ema_period, adjust=False).mean()
        slope = ema.diff()
        return slope

    # Resample 1H data to 4H bars
    df_sorted = df.copy()
    df_sorted["dt_idx"] = open_time
    df_sorted = df_sorted.set_index("dt_idx").sort_index()

    ohlc_4h = df_sorted.resample("4h", origin="start_day").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum"
    }).dropna(subset=["close"]).reset_index()

    ohlc_4h["completed_at"] = ohlc_4h["dt_idx"] + pd.to_timedelta(4, unit="h")
    ohlc_4h["ema"] = ohlc_4h["close"].ewm(span=self.htf_ema_period, adjust=False).mean()
    ohlc_4h["slope"] = ohlc_4h["ema"].diff()

    # Merge asof to align each 1H row with the most recent COMPLETED 4H bar
    df_temp = pd.DataFrame({
        "orig_idx": np.arange(len(df)),
        "close_time": close_time
    }).sort_values("close_time")

    merged = pd.merge_asof(
        df_temp,
        ohlc_4h[["completed_at", "slope"]].dropna(subset=["completed_at"]).sort_values("completed_at"),
        left_on="close_time",
        right_on="completed_at",
        direction="backward"
    ).sort_values("orig_idx")

    return pd.Series(merged["slope"].values, index=df.index)
```

---

## 3. Boundary Case Audit & Timestamp Walkthrough

To verify that lookahead bias cannot occur across 4H candle boundaries, we traced the exact timestamps across an 8-hour operational window (04:00 to 12:00 UTC).

### Step-by-Step Timestamp Mapping
Consider a 4H candle forming between `04:00:00` and `08:00:00 UTC`:
- 4H candle `dt_idx` (open time): `2025-01-15 04:00:00`
- 4H candle `completed_at`: `2025-01-15 08:00:00`
- 4H EMA and Slope computed using close price at `08:00:00`.

Now examine the 1H bars evaluated during and after this period:

| 1H Bar Index | 1H Bar `open_time` | 1H Bar `close_time` | Merged `completed_at` | 4H Bar Used | Lookahead? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Bar $t_0$ | 03:00:00 | 04:00:00 | 04:00:00 | 00:00–04:00 (Completed) | **NO** |
| Bar $t_1$ | 04:00:00 | 05:00:00 | 04:00:00 | 00:00–04:00 (Completed) | **NO** |
| Bar $t_2$ | 05:00:00 | 06:00:00 | 04:00:00 | 00:00–04:00 (Completed) | **NO** |
| Bar $t_3$ | 06:00:00 | 07:00:00 | 04:00:00 | 00:00–04:00 (Completed) | **NO** |
| Bar $t_4$ | 07:00:00 | 08:00:00 | **08:00:00** | **04:00–08:00 (Completed)** | **NO** |
| Bar $t_5$ | 08:00:00 | 09:00:00 | 08:00:00 | 04:00–08:00 (Completed) | **NO** |
| Bar $t_6$ | 09:00:00 | 10:00:00 | 08:00:00 | 04:00–08:00 (Completed) | **NO** |
| Bar $t_7$ | 10:00:00 | 11:00:00 | 08:00:00 | 04:00–08:00 (Completed) | **NO** |
| Bar $t_8$ | 11:00:00 | 12:00:00 | **12:00:00** | **08:00–12:00 (Completed)** | **NO** |

### Key Observations
1. **Bars $t_1, t_2, t_3$ (04:00 to 07:00 open):**  
   While the 04:00–08:00 4H candle is actively forming, the 1H bars with close times 05:00, 06:00, and 07:00 match `completed_at = 04:00:00` because $05:00 < 08:00$. The forming bar is completely invisible to the strategy.
2. **Bar $t_4$ (07:00 to 08:00 open):**  
   The 1H candle closes exactly at `08:00:00 UTC`. At this exact instant, the 04:00–08:00 4H candle also closes. `pd.merge_asof` with `direction='backward'` matches `completed_at == 08:00:00`. Both candles close simultaneously.
3. **Bars $t_5, t_6, t_7$ (08:00 to 11:00 open):**  
   These bars continue referencing the 08:00:00 completed 4H bar until 12:00:00 UTC.

---

## 4. Signal Generation and Order Execution Mechanics

Inspection of `runner.py` reveals the order generation and fill lifecycle:

### Step 1: Signal Evaluation at Bar Close $t$
In `runner.py` (lines 284–306):
```python
# Evaluated at timestamp t (close of bar t)
row = df_sym.loc[t]
sig = int(row.get("signal", 0))
if sig == 1 and len(open_positions) + len(pending_orders) < self.max_open_positions:
    pending_orders[sym] = {
        "symbol": sym,
        "signal_time": t,
        "signal_close": c_price,
        "sl_distance": sl_dist,
        "tp_distance": tp_dist,
        "trailing_pct": trail_pct,
        "delay_bars_remaining": self.execution_delay_bars
    }
```

### Step 2: Order Fill at Next Bar Open $t+1$
In `runner.py` (lines 144–171):
```python
# Executed on current bar Open (t+1 relative to signal)
for sym in list(pending_orders.keys()):
    order = pending_orders[sym]
    p_open = float(df_sym.loc[t, "open"])
    slip_bps, _ = self.get_transaction_costs(sym)
    fill_price = p_open * (1.0 + (slip_bps / 10000.0))
    # Fill position and deduct cash...
```

### Realistic Execution Assessment (Observation O-01)
- **Signal Timestamp:** `07:00:00` 1H bar close = `08:00:00 UTC`.
- **Order Generation:** Immediate upon receipt of `08:00:00 UTC` tick.
- **Execution Timestamp:** `08:00:00` 1H bar open.
- **Price:** $P_{open} \times (1 + \text{slippage})$.

In live production, an order cannot be calculated and filled at the exact millisecond of the bar open tick if the signal depends on the prior bar's close. However:
1. In discrete-time backtesting, next-bar open execution is standard practice.
2. The backtest penalizes every fill with **5 bps slippage** ($0.05\%$).
3. The strategy was subjected to an **execution delay stress test** (`delay_bars=1, 2, 3`), where orders were delayed by 1 to 3 hours. As documented in Phase 3C reports, performance degraded further under delay (Sharpe dropped from $-0.72$ to $-0.94$). Therefore, execution latency does not hide a viable trading strategy.

---

## 5. Audit Conclusion

The multi-timeframe alignment in `Donchian40HtfEmaSlopeStrategy` is **technically sound and free of lookahead bias**:
- No future candle data is leaked into past bars.
- Resampling is aligned to day-start (`origin='start_day'`).
- Backward merge correctly ignores incomplete higher-timeframe candles.
- Signals and orders execute in strictly forward-looking chronological order.
