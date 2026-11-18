# BTC-ML SYSTEM V2 — SYSTEM AUDIT REPORT
**Phase 0: Complete Repository and Quantitative System Audit**  
**Date:** November 18, 2026  
**Auditors:** Principal Quantitative Developer, Senior Algorithmic Trading Engineer, Quantitative Researcher, Senior Python Software Architect, Financial Risk Engineer, Site Reliability Engineer  
**Repository:** [Harshak76/BTC_ML_System](https://github.com/Harshak76/BTC_ML_System)

---

## 1. Executive Summary

This system audit conducts a forensic, end-to-end examination of the **btc-ml-system** codebase as it transitions from a Version 5.0 multi-asset prototype to an institutional-grade quantitative research and autonomous paper-trading platform.

The system encompasses:
1. **Multi-Asset Universe:** 5 US Equities (`AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`) and 2 Cryptocurrencies (`BTCUSDT`, `ETHUSDT`).
2. **Execution Targets:** Alpaca Paper Trading REST API v2 (`https://paper-api.alpaca.markets/v2`) and Alpaca Real-Time Market Data APIs (`v2/stocks` and `v1beta3/crypto`).
3. **Analytical Persistence:** Embedded DuckDB analytical storage (`data/btc_ml_system.duckdb`) tracking trades, open positions, candidate signals, continuous equity curves, and portfolio snapshots.
4. **Strategy Regimes:**
   - **Equities (V4.3 Frozen):** 1H Trend Pullback with Daily HTF EMA(50) slope filter and 2.33x R:R.
   - **Bitcoin (V4.5 Locked):** 4H HTF Trend with Multi-Timeframe Confirmation (Medium), Donchian Breakout, RSI Pullback, Volume Confirmation, and Volatility Regime Filter.
   - **Ethereum (V4.5 Clean):** 1H Regime Momentum with Bollinger Band Squeeze & RSI Expansion, strictly in CALM regime, unencumbered by session or MTF filters.
5. **Portfolio Risk Limits:**
   - 0.5% per-trade risk.
   - 3.0% maximum aggregate open portfolio risk.
   - 2.0% daily portfolio loss circuit breaker.
   - 10.0% peak-to-trough maximum drawdown hard circuit breaker.
   - Pairwise correlation filter: 0.70 threshold in Strict mode vs 0.80 threshold in Loose Stage 1 mode.

---

## 2. Quantitative System Scorecard

| Subsystem | Architectural Grade | Operational Readiness | Key Risk / Vulnerability |
| :--- | :---: | :---: | :--- |
| **Security & Secrets** | **F (Critical)** | **Non-Compliant** | Hardcoded Alpaca API keys and secret in config & source files; git tracking of secrets. |
| **Market Data Ingestion** | **C+ (Medium)** | **Partially Ready** | Potential candle lookback stitching gap; evaluation on forming/unclosed candles. |
| **Execution Engine** | **C (High)** | **Needs Hardening** | Client order ID format risk (spaces/colons); unverified order fills; fractional order TIF mismatch. |
| **Risk Management** | **B- (High)** | **Functioning with Gaps** | Risk denominator discrepancy (Component sub-capital vs Total Portfolio Equity). |
| **Strategy & Logic** | **A- (Low)** | **Production Ready** | Logic adheres to locked quantitative specifications (frozen Equity V4.3, BTC 4H MTF, ETH Clean). |
| **Backtesting Engine** | **B (Medium)** | **Discrepancy Present** | Next-bar open execution in single-asset backtester vs same-bar close in portfolio manager. |
| **Database & Persistence** | **A (Low)** | **Production Ready** | Robust DuckDB schema, startup position reconciliation, trade journal persistence. |
| **Test Coverage** | **B (Medium)** | **Acceptable Baseline** | 28/28 unit tests passing across packages; lacks mock REST network integration tests. |

---

## 3. Preserved Architecture & Invariants

Throughout this audit, the following immutable invariants have been strictly respected:
1. **Zero Production Code Modifications:** All findings are documented without speculative in-place code edits during Phase 0.
2. **Historical Data Preservation:** Historical DuckDB records (1,334 trades, 47,100 equity curve steps) remain untouched.
3. **Strategy Parameter Freeze:** All strategy parameters, regime quantiles, entry buffers, and exit multiples remain frozen.
4. **Risk Parameter Preservation:** No risk limits, circuit breakers, or allocation weights were modified or relaxed.
5. **Paper Trading Isolation:** Live-money execution remains strictly disabled.

---

## 4. Key Findings Summary Table

| Finding ID | Subsystem | Severity | Summary |
| :--- | :--- | :---: | :--- |
| **SEC-001** | Security | **CRITICAL** | Alpaca API key & secret exposed in plaintext in `portfolio_paper_v5.yaml`, `alpaca_executor.py`, and `data_provider.py`. |
| **SEC-002** | Security | **HIGH** | `.gitignore` omits `.env`, `.env.*`, and `*.duckdb`, allowing sensitive files and database binaries to be tracked. |
| **EXE-001** | Execution | **HIGH** | `client_order_id` in `alpaca_executor.py` contains raw signal timestamps with spaces and colons, risking 422 rejections. |
| **EXE-002** | Execution | **HIGH** | Order submission lacks execution state polling, fill confirmation, and partial-fill reconciliation. |
| **EXE-003** | Execution | **MEDIUM** | Fractional stock orders default to `time_in_force="gtc"`, which Alpaca rejects (requires `day`). |
| **DAT-001** | Market Data | **HIGH** | Live paper trading evaluates signals on incomplete / unclosed candles (`iloc[-1]`), inducing intra-bar flicker. |
| **DAT-002** | Market Data | **MEDIUM** | Cache stitching logic can introduce multi-week historical gaps into rolling indicator windows. |
| **RSK-001** | Risk | **HIGH** | 0.5% risk calculation uses component sub-allocation as denominator instead of total portfolio equity. |
| **BKT-001** | Backtesting | **MEDIUM** | Execution timing discrepancy: `backtester.py` uses next-bar open, while `portfolio_manager.py` uses same-bar close. |
| **ARC-001** | Architecture | **MEDIUM** | Prototype `crypto_ml_trader/` and legacy `paper_trader.py` remain as disconnected, dead code artifacts. |

---

## 5. Scope of Completed Audit Deliverables

The audit findings and architectural blueprints are distributed across the following dedicated reports located in `docs/audit/`:
- `ARCHITECTURE_MAP.md`: Reconstruction of the complete execution flow, module interaction diagrams, and paradigm boundaries.
- `MODULE_DEPENDENCY_MAP.md`: Dependency graphs, duplicate modules, circular references, and dead code inventory.
- `DATA_FLOW_AUDIT.md`: In-depth analysis of data providers, live streaming vs polling, candle alignment, and timezone handling.
- `STRATEGY_AUDIT.md`: Verification of entry/exit rules, indicators, regimes, and MTF filters for Equities, BTC, and ETH.
- `BACKTESTING_AUDIT.md`: Scrutiny of execution assumptions, lookahead bias, slippage, commission models, and performance metrics.
- `RISK_AUDIT.md`: Mathematical and operational verification of all portfolio risk controls, circuit breakers, and position sizing.
- `EXECUTION_AUDIT.md`: Audit of Alpaca REST API order life cycle, error handling, position reconciliation, and kill switches.
- `DATABASE_AUDIT.md`: Forensic inspection of DuckDB schemas, ACID guarantees, migrations, and query performance.
- `TEST_COVERAGE_REPORT.md`: Comprehensive breakdown of existing test suites, edge-case coverage, and testing gaps.
- `SECURITY_AUDIT.md`: Vulnerability analysis covering secrets management, repository hygiene, and API communication security.
- `IMPLEMENTATION_ROADMAP.md`: Detailed, prioritized, phased implementation plan for Phase 1 through Phase 5.
