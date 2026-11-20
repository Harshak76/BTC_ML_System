# BENCHMARK INTEGRITY AUDIT
## Phase 3B.1 Forensic Audit: Buy-and-Hold, Cash Baseline & SMA(50) Trend Divergence

**Repository:** `BTC_ML_System`  
**Audit Branch:** `audit/phase-3b-1-integrity`  
**Base Commit:** `ed573c1`  
**Target Module:** `btc_ml_system.src.research.evaluator.ResearchEvaluator`  
**Audit Verdict:** `VERIFIED`

---

### 1. Executive Summary

In Phase 3B (`docs/research/phase_3b/BENCHMARK_COMPARISON.md`), candidate trading strategies were compared against three reference baselines:
1. **Buy-and-Hold (B&H)**
2. **Cash Baseline (100% Cash)**
3. **SMA(50) Trend Benchmark**

A notable result in the benchmark comparison was observed on AAPL:
- **AAPL Buy-and-Hold:** $+343.03\%$ Total Return, $1.09$ Sharpe, **70.79% Max Drawdown**.
- **AAPL SMA(50) Trend:** $+341.65\%$ Total Return, $1.29$ Sharpe, **37.09% Max Drawdown**.

This audit independently investigated:
1. Why AAPL B&H and SMA(50) achieved almost identical cumulative returns ($+343\%$ vs $+342\%$).
2. Why their maximum drawdowns differed by $33.7$ percentage points ($70.79\%$ vs $37.09\%$).
3. The validity of Cash Baseline dominance over candidate strategies.
4. The performance of active benchmarks on crypto.

---

### 2. Forensic Investigation of the AAPL Return/Drawdown Divergence

#### 2.1 Independent Reproduction of AAPL Benchmark Series
Running `ev.compute_buy_and_hold_benchmark("AAPL", df_aapl)` and `ev.compute_sma_trend_benchmark("AAPL", df_aapl, sma_period=50)` produced:

| Metric | AAPL Buy-and-Hold | AAPL SMA(50) Trend | Absolute Discrepancy |
| :--- | :---: | :---: | :---: |
| **Initial Equity ($)** | $100,000.00 | $100,000.00 | $0.00 |
| **Terminal Equity ($)** | $443,029.84 | $441,652.12 | $1,377.72 (0.31%) |
| **Total Net Return (%)** | **+343.03%** | **+341.65%** | **1.38%** |
| **Annualized Sharpe Ratio** | 1.09 | 1.29 | +0.20 |
| **Maximum Drawdown (%)** | **70.79%** | **37.09%** | **-33.70%** |
| **Market Exposure (%)** | 100.0% | 68.4% | -31.6% |
| **Total Round-Trip Trades** | 1 (buy at open) | 28 trades | 27 trades |

#### 2.2 Mathematical Cause of the Divergence
1. **Trend Capture with Cash Preservation:**
   - The underlying AAPL price series exhibited a strong upward secular trend from $\$151.15$ to $\$669.12$ over 5,110 bars.
   - However, the price trajectory experienced severe intermediate corrections (including sharp $-50\%$ to $-70\%$ market crashes).
   - The Buy-and-Hold strategy remained fully invested through every crash, absorbing the full $-70.79\%$ peak-to-trough collapse.
   - The SMA(50) Trend strategy crossed below its 50-period simple moving average during the onset of the crashes, liquidating to cash at the next-bar open.
2. **Re-entering During Major Expansions:**
   - While out of the market, SMA(50) held 100% cash, preserving capital during deep market corrections.
   - Once price broke back above the 50-period SMA, the benchmark re-entered long.
   - Because it preserved capital during drawdowns, compounding from a higher equity base allowed SMA(50) to achieve essentially the same terminal equity ($+341.65\%$) as Buy-and-Hold ($+343.03\%$) while being invested only $68.4\%$ of the time!
3. **Execution Realism:**
   - The SMA(50) benchmark accounted for 2 bps slippage on every entry and exit ($4\text{ bps}$ round-trip across 28 trades = $112\text{ bps}$ total friction), proving that the performance was not an artifact of zero-friction assumptions.

---

### 3. Cash Baseline Dominance

Across all 9 evaluated candidate strategies at the portfolio level:
- Best candidate (`RS_MOM_DONCHIAN_40_V1`): **-5.46% return**, **10.71% max drawdown**, **Sharpe -0.40**.
- Worst candidate (`RS_MR_BB_RSI_22_STD_V1`): **-15.83% return**, **18.56% max drawdown**, **Sharpe -2.02**.
- **Cash Baseline:** **0.00% return**, **0.00% max drawdown**, **Sharpe 0.00**.

Because every candidate generated negative net expected value, holding 100% cash was strictly superior on both absolute return and risk-adjusted return.

---

### 4. Cryptocurrency Benchmark Integrity

On cryptocurrencies:
- **BTCUSDT:**
  - Buy-and-Hold: $+35.80\%$ return, but **53.45% max drawdown**.
  - SMA(50) Trend: **-20.06% return**, **52.22% max drawdown**, $3.84\times$ turnover.
- **ETHUSDT:**
  - Buy-and-Hold: $+7.71\%$ return, but **69.15% max drawdown**.
  - SMA(50) Trend: **-64.22% return**, **73.97% max drawdown**, $4.12\times$ turnover.

In crypto markets, simple moving average crossovers suffer massive whipsaw losses due to frequent false breakouts and high round-trip friction ($20\text{ bps}$).

---

### 5. Audit Classification

**Audit Verdict:** `VERIFIED`  
- Benchmark calculations are mathematically accurate, realistic, and correctly account for transaction costs.
- The AAPL return/drawdown divergence is fully validated and economically explained.
