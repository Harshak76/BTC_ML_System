# BTC-ML SYSTEM V2 — PHASE 1 EXECUTION VALIDATION REPORT
## Order Routing, Lifecycle Polling & Broker Protocol Conformance

**Date:** 2026-11-18  
**Author:** Principal Algorithmic Execution Engineer  
**Status:** Conforming & Validated  

---

### 1. Execution Architecture Overview

Execution reliability fixes in Phase 1 eliminated four major risks:
1. **EXE-001:** Order rejections caused by invalid characters (e.g., colons, spaces, plus signs) in `client_order_id`.
2. **EXE-002:** Ghost position tracking caused by assuming orders fill instantly upon HTTP 200 response from Alpaca.
3. **EXE-003:** Immediate API rejection on US equity fractional shares when submitting `time_in_force: "gtc"`.
4. **EXE-004:** Duplicate order submission following process crash or restart.

---

### 2. Implementation & Broker Protocol Compliance

#### 2.1 Client Order ID Sanitization (EXE-001)
Alpaca requires `client_order_id` to match the regular expression `^[a-zA-Z0-9_-]+$` with a maximum length of 64 characters.
- **Implementation:** `AlpacaExecutor.sanitize_client_order_id(signal_id)`
  - Converts characters outside `[a-zA-Z0-9_-]` to underscores.
  - Truncates strings exceeding 64 characters.
  - Examples:
    - `"BTCUSDT_2026-11-18 16:00:00+00:00"` $\to$ `"BTCUSDT_2026-11-18_16_00_00_00_00"` (Match: Valid)
    - `"AAPL_2026-11-18 09:30:00-05:00"` $\to$ `"AAPL_2026-11-18_09_30_00-05_00"` (Match: Valid)

#### 2.2 Order Lifecycle Polling & Fill Verification (EXE-002)
Previously, `submit_order` returned success immediately after the initial REST `POST /v2/orders` request, before Alpaca matched or routed the order.
- **Remediation:** Added `AlpacaExecutor.poll_order_fill(order_id, max_retries=10, retry_delay=1.0)`:
  - Actively polls `GET /v2/orders/{order_id}` with exponential bounded retries.
  - Evaluates terminal states:
    - `"filled"`: Records actual filled quantity and weighted average fill price.
    - `"partially_filled"`: Captures executed portion; warns operator if remainder remains open.
    - `"rejected"` / `"canceled"` / `"expired"`: Emits explicit error log and rejects database record creation.
    - If unconfirmed after 10s: Marks status as `"pending_unconfirmed"` and alerts operator without recording a premature fill.

#### 2.3 Fractional Equity Time-in-Force Enforcement (EXE-003)
Alpaca restricts fractional equity share trading to market hours and strictly requires `time_in_force = "day"`. GTC fractional orders are rejected by the broker.
- **Remediation:** In `AlpacaExecutor.submit_order`:
  ```python
  if asset_type == "equity" and not float(qty).is_integer():
      time_in_force = "day"
  ```
  Crypto fractional orders retain `"gtc"`.

#### 2.4 Restart Idempotency State Recovery (EXE-004)
On startup, `PortfolioPaperTrader._restore_idempotency_state` queries the DuckDB database for all trade records executed during the current calendar date:
```sql
SELECT symbol, client_order_id FROM trades WHERE entry_time >= CURRENT_DATE
```
Any signal IDs matching existing completed or pending orders are added to `executed_signal_ids`, preventing double execution if the trading process restarts.

---

### 3. Execution Verification Summary

All execution paths were tested using isolated mock fixtures in `test_alpaca_executor.py`:
- `test_client_order_id_sanitization`: Verified valid Alpaca format across diverse timestamps and symbols.
- `test_fractional_equity_order_time_in_force`: Verified `"day"` enforcement on equities and `"gtc"` preservation on crypto.
- `test_order_fill_verification_lifecycle`: Verified proper state transitions for filled, partial, and rejected orders.
- Zero live orders were sent to Alpaca during testing.
