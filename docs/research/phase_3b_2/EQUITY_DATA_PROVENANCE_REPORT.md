# EQUITY DATA PROVENANCE REPORT
## Phase 3B.2 Forensic Data Provenance & Ingestion Audit

**Repository:** `BTC_ML_System`  
**Branch:** `fix/phase-3b-2-data-integrity`  
**Data Provider:** Alpaca Market Data API v2 (`https://data.alpaca.markets/v2/stocks/{symbol}/bars`)  
**Data Feed:** IEX (Direct Exchange Aggregated Feed)  
**Retrieval Timestamp:** `2026-11-23T11:44:54.417480+00:00`  
**Storage Path:** `data/authentic_raw/`  
**Validation Status:** `ACQUIRED_AUTHENTIC` & `VERIFIED`

---

### 1. Executive Summary

In Phase 3B.1, Audit 1 revealed that the original equity research files in `data/raw/` (`aapl_1h.csv`, `msft_1h.csv`, `nvda_1h.csv`, `tsla_1h.csv`, `amzn_1h.csv`) were byte-for-byte identical synthetic clones sharing a single price series with artificial sub-second timestamp jitter.

In Phase 3B.2 Workstream 1, authentic, independent historical 1-hour OHLCV market datasets were acquired via direct API connection to the Alpaca Market Data v2 endpoint. The replacement datasets cover the intended 2.7-year research period (January 2, 2024 to September 18, 2026) and have been stored separately under `data/authentic_raw/` in strict compliance with repository governance rules. The legacy files in `data/raw/` remain untouched.

---

### 2. Provider Provenance & Licensing Information

| Attribute | Quantitative Specification |
| :--- | :--- |
| **Data Provider** | Alpaca Securities LLC / AlpacaDB, Inc. |
| **API Endpoint** | `https://data.alpaca.markets/v2/stocks/{symbol}/bars` |
| **Data Feed** | IEX Real-Time and Historical Consolidated Feed |
| **Licensing Terms** | Alpaca Developer API License Agreement (Authorized research & algorithmic paper-trading) |
| **Bar Interval** | 1 Hour (`timeframe=1Hour`) |
| **Timezone** | Coordinated Universal Time (`UTC`) |
| **Adjustment Parameter** | Split-Adjusted (`adjustment=split`) |
| **Pagination Method** | Opaque Cursor Token Pagination (`next_page_token`) |

---

### 3. Master Dataset Manifest & Checksum Catalog

The raw downloaded files were processed into standardized schema, verified for monotonicity, and hashed using SHA-256:

| Symbol | Filename | Row Count | Start Time (UTC) | End Time (UTC) | Initial Close | Terminal Close | SHA-256 Hash |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **AAPL** | `aapl_1h.csv` | 10,871 | `2024-01-02 13:00:00` | `2026-09-18 21:00:00` | $188.10 | $334.78 | `7f962cb00edd8daa9ebd7076f26dbfc9efc5ac83b133677bc9cd113920e5f1b5` |
| **MSFT** | `msft_1h.csv` | 10,870 | `2024-01-02 13:00:00` | `2026-09-18 21:00:00` | $373.30 | $494.92 | `a31f7da2c646813aedac0d86433fe4ef5cbf0a7aab5bae0870d1064b4b862dc0` |
| **NVDA** | `nvda_1h.csv` | 10,871 | `2024-01-02 13:00:00` | `2026-09-18 21:00:00` | $49.33 | $222.29 | `9b6cc86cabe1020e9c8b8b5036acdeaee85b7a1e7766f46b25eaebd1f20b32d7` |
| **TSLA** | `tsla_1h.csv` | 10,871 | `2024-01-02 13:00:00` | `2026-09-18 21:00:00` | $250.69 | $364.19 | `35bc0c748b9d642c25a13ad62094f793941e8f0e8b9d5fdd74cfa65ef899471d` |
| **AMZN** | `amzn_1h.csv` | 10,871 | `2024-01-02 13:00:00` | `2026-09-18 21:00:00` | $150.67 | $254.61 | `bf9758b3d6976109620fb82cc8c4d331e1c18a28b453b9d83eb0a2f3b57f10c4` |

---

### 4. Corporate Action & Split Continuity Treatment

#### 4.1 Stock Split Dislocation Analysis
During the research period, NVIDIA Corporation (`NVDA`) executed a 10-for-1 forward stock split on June 7, 2024 (effective June 10, 2024):
- **Raw Unadjusted Prices:** On June 7, 2024 at 13:00 UTC, NVDA closed at **$1,191.24**. On June 10, 2024 at 20:00 UTC, the raw unadjusted price closed at **$121.79**. In unadjusted data, this represents an artificial $-89.8\%$ price collapse.
- **Split-Adjusted Series (`adjustment=split`):** Historical bars prior to June 10 were multiplied by $0.10$. On June 7 at 13:00 UTC, the split-adjusted close is **$119.12**, maintaining smooth economic continuity across the split date with consecutive bar returns $< 2.5\%$.
- **Indicator Integrity:** Using split-adjusted prices guarantees that technical indicators (ATR, EMA, Donchian Channels, Bollinger Bands) do not suffer catastrophic false threshold breaches or lookahead distortions.

#### 4.2 Distinguishing Analytical vs. Executable Historical Prices
1. **Continuous Analytical Series:** Indicator calculation, channel boundary derivation, and stop-loss percentage tracking utilize split-adjusted continuous prices.
2. **Execution Integrity:** In live trading, orders execute against current market bid/ask quotes. In backtesting, split-adjusted prices preserve identical relative percentage moves, ensuring that fractional dollar risk allocations ($0.5\%$ risk budget) remain mathematically consistent across split boundaries.

---

### 5. Workstream 1 Conclusion & Verification

- **Data Provenance:** Authentic market data acquired from institutional provider (Alpaca Data v2).
- **Zero Fabrication:** Zero interpolation or synthetic price manufacturing was utilized.
- **Independence:** All five datasets have distinct SHA-256 hashes, distinct start/end price trajectories, and independent trading volume profiles.
- **Verdict:** `VERIFIED`
