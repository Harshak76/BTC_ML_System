# ASSET-LEVEL RESULT INTEGRITY AUDIT
## Phase 3B.1 Forensic Audit: Cross-Asset Data Equality & Execution Independence

**Repository:** `BTC_ML_System`  
**Audit Branch:** `audit/phase-3b-1-integrity`  
**Base Commit:** `ed573c1`  
**Evaluation Scope:** Single-Asset Performance and Data Source Integrity  
**Audit Verdict:** `FAILED` (Equity Test Data) / `VERIFIED` (Crypto Test Data & Engine Execution)

---

### 1. Executive Summary & Core Anomaly Investigation

In Phase 3B (`docs/research/phase_3b/ASSET_LEVEL_PERFORMANCE.md`), the single-asset breakdown for the top-performing momentum candidate (`RS_MOM_DONCHIAN_40_V1`) reported identical performance across all five US equity assets:

| Asset Symbol | Asset Class | Total Return (%) | Sharpe Ratio | Max Drawdown (%) | Total Trades | Win Rate (%) | Profit Factor |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **AAPL** | US Equity | **+1.02%** | **+0.22** | 2.45% | 84 | **72.62%** | 1.18 |
| **MSFT** | US Equity | **+1.02%** | **+0.22** | 2.45% | 84 | **72.62%** | 1.18 |
| **NVDA** | US Equity | **+1.02%** | **+0.22** | 2.45% | 84 | **72.62%** | 1.18 |
| **TSLA** | US Equity | **+1.02%** | **+0.22** | 2.45% | 84 | **72.62%** | 1.18 |
| **AMZN** | US Equity | **+1.02%** | **+0.22** | 2.45% | 84 | **72.62%** | 1.18 |
| **BTCUSDT** | Crypto | **-3.41%** | **-2.90** | 4.25% | 54 | **29.63%** | 0.54 |
| **ETHUSDT** | Crypto | **-5.90%** | **-1.53** | 6.63% | 211 | **33.18%** | 0.68 |

This audit independently investigated whether this identical performance was caused by:
1. An engine execution bug (e.g., reusing in-memory simulation states or caching the AAPL result), OR
2. An underlying data source defect in the repository's raw data files.

---

### 2. Forensic Investigation of Raw Data Files

The evaluator loads asset data through `btc_ml_system.src.research.evaluator.ResearchEvaluator.load_asset_data(symbol)`.
The file paths resolved are:
- `data/raw/aapl_1h.csv`
- `data/raw/msft_1h.csv`
- `data/raw/nvda_1h.csv`
- `data/raw/tsla_1h.csv`
- `data/raw/amzn_1h.csv`
- `data/raw/btcusdt_4h.csv`
- `data/raw/ethusdt_1h.csv`

#### 2.1 File Characteristics & Statistical Comparison

An exhaustive forensic comparison was conducted across all raw price series:

| File Name | Row Count | Initial Open Time | Terminal Open Time | Initial Close | Terminal Close | MD5 Checksum (Numeric Values) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `aapl_1h.csv` | 5,110 | `2024-01-02 14:30:00` | `2026-09-17 19:30:00` | 151.15 | 669.12 | `6f380ec8...` |
| `msft_1h.csv` | 5,110 | `2024-01-02 14:30:01.815...` | `2026-09-17 19:30:01.815...` | 151.15 | 669.12 | `6f380ec8...` |
| `nvda_1h.csv` | 5,110 | `2024-01-02 14:30:03.630...` | `2026-09-17 19:30:03.630...` | 151.15 | 669.12 | `6f380ec8...` |
| `tsla_1h.csv` | 5,110 | `2024-01-02 14:30:05.445...` | `2026-09-17 19:30:05.445...` | 151.15 | 669.12 | `6f380ec8...` |
| `amzn_1h.csv` | 5,110 | `2024-01-02 14:30:07.260...` | `2026-09-17 19:30:07.260...` | 151.15 | 669.12 | `6f380ec8...` |
| `btcusdt_4h.csv` | 10,953 | `2021-01-01 00:00:00` | `2026-01-01 00:00:00` | 28923.63 | 91340.20 | Distinct authentic data |
| `ethusdt_1h.csv` | 21,795 | `2023-01-01 00:00:00` | `2026-01-01 00:00:00` | 1196.12 | 3450.80 | Distinct authentic data |

#### 2.2 Forensic Findings

1. **Exact Numeric Price Duplication:**
   For all 5,110 bars:
   $$\max_{t \in [1, 5110]} |\text{Close}_{\text{MSFT}, t} - \text{Close}_{\text{AAPL}, t}| = 0.000000$$
   $$\max_{t \in [1, 5110]} |\text{Close}_{\text{NVDA}, t} - \text{Close}_{\text{AAPL}, t}| = 0.000000$$
   $$\max_{t \in [1, 5110]} |\text{Close}_{\text{TSLA}, t} - \text{Close}_{\text{AAPL}, t}| = 0.000000$$
   $$\max_{t \in [1, 5110]} |\text{Close}_{\text{AMZN}, t} - \text{Close}_{\text{AAPL}, t}| = 0.000000$$
   The open, high, low, close, and volume numeric series are $100\%$ byte-for-byte identical across all 5 US equity files.

2. **Synthetic Timestamp Offsets:**
   The only difference between the equity CSV files is an artificial timestamp offset incremented by approximately $1.815$ seconds per file (`+0s` for AAPL, `+1.815s` for MSFT, `+3.630s` for NVDA, `+5.445s` for TSLA, `+7.260s` for AMZN).

3. **Execution Engine Clearance:**
   `ResearchSimulationRunner` and `ResearchEvaluator` did **not** introduce a software defect. The engine:
   - Instantiated separate data frames for each symbol.
   - Evaluated each asset independently through isolated simulation runs.
   - Accurately reported the mathematical results produced by the underlying CSV files.
   However, because the 5 input files on disk were clones, the resulting outputs were inevitably identical.

---

### 3. Cryptocurrency Data Authenticity

In contrast to the equity CSVs, the cryptocurrency data files:
- `btcusdt_4h.csv` contains 10,953 authentic 4-hour historical candles from Binance/DuckDB.
- `ethusdt_1h.csv` contains 21,795 authentic 1-hour candles.
- Their price dynamics, volatility profiles, trade frequencies (54 trades on BTC vs. 211 trades on ETH), win rates (29.63% vs. 33.18%), and drawdowns (4.25% vs. 6.63%) are fully differentiated and statistically authentic.

---

### 4. Methodological Impact & Remediation Plan

#### 4.1 Quantitative Impact
- The multi-asset equity portfolio evaluation effectively tested a **single equity price path repeated 5 times** with staggered sub-second timestamps.
- Portfolio diversification across US equities in Phase 3B was an illusion created by duplicated input files. Cross-asset equity correlation was artificially $1.0000$.

#### 4.2 Remediation Requirements (Mandatory for Phase 3C)
1. **Acquire Authentic Equity Historical Data:**
   Ingest genuine 1-hour OHLCV historical bars for AAPL, MSFT, NVDA, TSLA, and AMZN via polygon.io, yfinance, or Alpaca Market Data v2.
2. **Synchronize Calendar Timestamps:**
   Standardize equity timestamps to official US Market exchange open/close intervals without artificial sub-second jitter.
3. **Data Integrity Checksum Test:**
   Implement automated CI tests ensuring no two assets in `data/raw/` have identical closing price series.

---

### 5. Final Audit Classification

- **Equity Test Data:** `FAILED` — Legacy synthetic clone files must be replaced before live/paper eligibility.
- **Crypto Test Data:** `VERIFIED` — Authentic historical market series.
- **Execution Engine:** `VERIFIED` — Faithful, isolated execution across input series.
