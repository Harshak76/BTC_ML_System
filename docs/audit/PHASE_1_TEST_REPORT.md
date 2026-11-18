# BTC-ML SYSTEM V2 — PHASE 1 TEST REPORT
## Automated Verification & Regression Test Suite

**Date:** 2026-11-18  
**Branch:** `phase-1-security-data-execution`  
**Test Framework:** Pytest 9.1.1 (Python 3.12.1, pluggy 1.6.0)  
**Execution Environment:** Windows Subsystem / PowerShell (Local Isolated Sandbox)  
**Total Test Results:** 34 Passed / 0 Failed / 100% Pass Rate  

---

### 1. Executive Summary

A comprehensive regression and unit test suite was executed across all components of `btc-ml-system`. The test suite expanded from 16 baseline tests to 34 total automated tests, adding 18 targeted unit and mock integration tests covering the security, data integrity, execution lifecycle, risk accounting, and backtest timing fixes implemented in Phase 1.

Every test executed deterministically without external network access or unmocked live broker requests.

---

### 2. Comprehensive Test Execution Roster

| Test Module | Test Name | Target Finding | Status | Time |
| :--- | :--- | :--- | :--- | :--- |
| `test_alpaca_executor.py` | `test_client_order_id_sanitization` | EXE-001 | **PASSED** | 0.05s |
| `test_alpaca_executor.py` | `test_fractional_equity_order_time_in_force` | EXE-003 | **PASSED** | 0.08s |
| `test_alpaca_executor.py` | `test_order_fill_verification_lifecycle` | EXE-002 | **PASSED** | 0.12s |
| `test_alpaca_executor.py` | `test_hard_risk_caps_rejection` | RSK-002 | **PASSED** | 0.04s |
| `test_alpaca_executor.py` | `test_live_money_safety_guard` | SEC-003 | **PASSED** | 0.03s |
| `test_backtest_timing.py` | `test_next_bar_open_execution_timing` | BKT-001 | **PASSED** | 0.22s |
| `test_backtest_timing.py` | `test_same_bar_close_execution_timing` | BKT-001 | **PASSED** | 0.20s |
| `test_backtest_timing.py` | `test_opening_gap_slippage_handling` | BKT-002 | **PASSED** | 0.19s |
| `test_database.py` | `test_schema_initialization` | DAT-BASE | **PASSED** | 0.15s |
| `test_database.py` | `test_trade_insertion_and_query` | DAT-BASE | **PASSED** | 0.18s |
| `test_database.py` | `test_equity_curve_insertion` | DAT-BASE | **PASSED** | 0.12s |
| `test_database.py` | `test_positions_upsert_and_clear` | DAT-BASE | **PASSED** | 0.14s |
| `test_database.py` | `test_portfolio_snapshot_insertion` | DAT-BASE | **PASSED** | 0.11s |
| `test_database.py` | `test_export_to_csv` | DAT-BASE | **PASSED** | 0.16s |
| `test_database.py` | `test_trade_journal_duckdb_integration` | DAT-BASE | **PASSED** | 0.21s |
| `test_database.py` | `test_auto_analyzer_with_duckdb` | DAT-BASE | **PASSED** | 0.19s |
| `test_eth_config.py` | `test_eth_config_session_filter_disabled` | STR-001 | **PASSED** | 0.02s |
| `test_eth_config.py` | `test_session_filter_permits_24_7_when_disabled` | STR-001 | **PASSED** | 0.02s |
| `test_eth_config.py` | `test_crypto_strategy_evaluates_with_disabled_session_filter` | STR-001 | **PASSED** | 0.10s |
| `test_features.py` | `test_feature_generation` | FEAT-BASE | **PASSED** | 0.35s |
| `test_labels.py` | `test_triple_barrier_labeler` | LBL-BASE | **PASSED** | 0.28s |
| `test_leakage.py` | `test_purged_splits` | ML-BASE | **PASSED** | 0.22s |
| `test_market_data.py` | `test_completed_candle_filtering` | DAT-001 | **PASSED** | 0.15s |
| `test_market_data.py` | `test_gap_detection_and_stale_cache_handling` | DAT-002 | **PASSED** | 0.18s |
| `test_pipeline.py` | `test_pipeline_integration` | PIPE-BASE | **PASSED** | 1.85s |
| `test_risk.py` | `test_risk_engine` | RSK-BASE | **PASSED** | 0.05s |
| `test_risk_policy.py` | `test_risk_denominator_calculations_on_10k_portfolio` | RSK-001 | **PASSED** | 0.04s |
| `test_risk_policy.py` | `test_aggregate_open_risk_ceiling_and_circuit_breakers` | RSK-001 | **PASSED** | 0.05s |
| `test_security.py` | `test_no_hardcoded_credentials_in_source_and_configs` | SEC-001 | **PASSED** | 0.14s |
| `test_security.py` | `test_gitignore_exclusions` | SEC-002 | **PASSED** | 0.01s |
| `test_security.py` | `test_duckdb_database_preserved_and_intact` | SEC-002 | **PASSED** | 0.06s |
| `test_trading_modes.py` | `test_strict_mode_configuration` | MODE-BASE | **PASSED** | 0.08s |
| `test_trading_modes.py` | `test_loose_stage1_mode_configuration` | MODE-BASE | **PASSED** | 0.09s |
| `test_trading_modes.py` | `test_config_fallback_and_switch` | MODE-BASE | **PASSED** | 0.07s |

---

### 3. Detailed Test Module Breakdown

#### 3.1 `test_alpaca_executor.py` (5 Tests)
- **`test_client_order_id_sanitization`:** Tests raw signal IDs containing colons, timestamps, spaces, and special symbols (`"BTCUSDT_2026-11-18 16:00:00+00:00"`). Confirms output matches regex `^[a-zA-Z0-9_-]+$`, max 64 chars.
- **`test_fractional_equity_order_time_in_force`:** Mocks order placement for AAPL with quantity `0.45` shares. Asserts outgoing payload has `"time_in_force": "day"`. For crypto (BTC with `0.02`), asserts `"time_in_force": "gtc"`.
- **`test_order_fill_verification_lifecycle`:** Simulates three lifecycle states:
  - Immediate complete fill (`filled` status).
  - Multi-step partial fill transitioning to fill on second poll.
  - Immediate broker rejection (`rejected` status with error payload).
- **`test_hard_risk_caps_rejection`:** Asserts orders exceeding `$2,500` max position value or `30%` equity are rejected locally before network submission.
- **`test_live_money_safety_guard`:** Asserts passing `https://api.alpaca.markets/v2` raises `RuntimeError` unless `ALLOW_LIVE_MONEY_TRADING=true`.

#### 3.2 `test_market_data.py` (2 Tests)
- **`test_completed_candle_filtering`:** Creates an hourly candle set where the last candle is forming in the current hour (`close_time > now_utc`). Validates that `DataProvider.get_completed_candles` discards the unfinished bar, eliminating intra-bar signal flicker.
- **`test_gap_detection_and_stale_cache_handling`:** Injects a 20-hour gap between cached Parquet bars and new live data. Asserts `DataProvider._stitch_and_clean` detects the gap and triggers an automated backfill.

#### 3.3 `test_risk_policy.py` (2 Tests)
- **`test_risk_denominator_calculations_on_10k_portfolio`:** Validates risk sizing on a $10,000 portfolio:
  - `component_allocation`: BTC (25% weight = $2,500 sub-capital) at 0.5% risk yields exactly `$12.50` dollar risk.
  - `portfolio_equity`: BTC at 0.5% risk on total portfolio yields `$50.00` dollar risk.
- **`test_aggregate_open_risk_ceiling_and_circuit_breakers`:** Validates that when total open risk reaches 3.0% ($300 on $10,000), subsequent signals are blocked. Confirms daily loss limit (2.0%) and max drawdown (10.0%) circuit breakers trigger rejection.

#### 3.4 `test_backtest_timing.py` (3 Tests)
- **`test_next_bar_open_execution_timing`:** Signal generated on bar $t$ fills on bar $t+1$ at `open` price ($105.00), not bar $t$ `close` ($100.00).
- **`test_same_bar_close_execution_timing`:** Legacy mode fills on bar $t$ at `close` ($100.00).
- **`test_opening_gap_slippage_handling`:** Position with stop price $95.00 encounters an adverse gap open at $85.00. Exit occurs at $85.00, properly recording the slippage.

#### 3.5 `test_eth_config.py` (3 Tests)
- **`test_eth_config_session_filter_disabled`:** Verifies `configs/eth_1h_v4.5.yaml` contains `session_filter.enabled: false`.
- **`test_session_filter_permits_24_7_when_disabled`:** Validates that `SessionFilter.is_session_valid` returns `True` across all 24 hours (00:00 to 23:00 UTC).
- **`test_crypto_strategy_evaluates_with_disabled_session_filter`:** Validates that `CryptoRegimeMomentumStrategy` generates valid direction signals under calm regimes.

#### 3.6 `test_security.py` (3 Tests)
- **`test_no_hardcoded_credentials_in_source_and_configs`:** Recursively scans all `.py` and `.yaml` files in `btc_ml_system/` asserting zero instances of hardcoded Alpaca API keys or secret strings.
- **`test_gitignore_exclusions`:** Validates `.gitignore` excludes `.env` and `*.duckdb`.
- **`test_duckdb_database_preserved_and_intact`:** Opens `data/btc_ml_system.duckdb` and asserts table presence and `SELECT COUNT(*) >= 1300` on historical `trades`.

---

### 4. Flakiness & Determinism Evaluation

- **Network Isolation:** All broker interactions (`requests.get`, `requests.post`) were mocked using `unittest.mock.patch`. Zero external network calls were executed during test runs.
- **Database Isolation:** Database tests operate on dedicated temporary files (`NamedTemporaryFile`), leaving production DuckDB files untouched.
- **Deterministic Execution:** Total execution time across 34 tests is ~7.63s, with zero timeout or race conditions.
