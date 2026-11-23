# ZERO-RETURN FORENSIC REPORT
## Mathematical Verification of Portfolio Holdings, Off-Market Closures, and Overnight Crypto Valuation

**Repository:** `BTC_ML_System`  
**Primary Branch:** `fix/phase-3b-2-data-integrity`  
**Evaluation Universe:** 5 US Equities (`AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`) & 2 Cryptos (`BTCUSDT`, `ETHUSDT`)  
**Timeline:** Jan 2024 – Sep 2026 ($T = 20,424$ hourly bars)  
**Status:** `VERIFIED & RESOLVED`  

---

### 1. Executive Summary & Objective

In Phase 3B.2, synchronizing the multi-asset timeline reduced observations from 43,070 to $T = 20,424$ steps, but the proportion of exact zero returns remained high (92.7% to 98.6% depending on the strategy).

The objective of this forensic investigation is to:
1. Identify the exact mathematical nature of each series in the synchronized candidate return matrix.
2. Verify whether zero returns are an artifact of calculation error or a genuine reflection of portfolio accounting.
3. Determine whether cryptocurrency price movements contribute to portfolio returns during overnight and weekend equity market closures.
4. Independently reconstruct concrete hourly samples of overnight/weekend portfolio valuations using actual holdings, cash balances, and mark-to-market prices.

---

### 2. Candidate Matrix Series Representation

Inspection of `btc_ml_system/src/research/runner.py` (lines 308–334) and `candidate_matrix.py` confirms:
1. **Series Identity:** Each column of the $20,424 \times 9$ candidate return matrix represents **portfolio-level periodic returns** expressed in percentage points (`%`):
   $$R_t = \frac{E_t - E_{t-1}}{E_{t-1}} \times 100$$
2. **Portfolio Valuation Equation:** Total portfolio liquidation equity $E_t$ at step $t$ is defined as:
   $$E_t = \text{cash}_t + \sum_{s \in \text{open\_positions}_t} \left(\text{quantity}_{s, t} \times P_{s, t, \text{close}}\right)$$
3. **What the Series Does NOT Represent:**
   - It is NOT an individual asset return series.
   - It is NOT cash interest returns (risk-free rate is assumed 0.0%).
   - It is the genuine mark-to-market return of an active, multi-asset discretionary portfolio starting at $E_0 = \$100,000.00$.

---

### 3. Market Schedule & Zero Return Accounting

The synchronized timeline spans $T = 20,424$ common hourly steps. Over this timeline, financial markets operate on two radically different schedules:
- **US Equities (AAPL, MSFT, NVDA, TSLA, AMZN):** Open Monday–Friday, 08:00 to 23:00 UTC (16-hour extended session) or 14:00 to 21:00 UTC (7-hour regular session). Completely closed on weekends and US holidays.
- **Cryptocurrencies (BTCUSDT, ETHUSDT):** Trade continuously 24 hours/day, 7 days/week, 365 days/year.

#### 3.1 Timeline Market Schedule Breakdown
- **Equity Closed Hours (Weekends + Night Hours $< 08:00$ or $== 23:00$ UTC):** **9,924 bars** (48.59% of timeline).
- **Equity Open Hours (Extended Sessions 08:00 to 23:00 UTC weekdays):** **10,500 bars** (51.41% of timeline).

#### 3.2 Granular Audit for Top Candidate (`RS_MOM_DONCHIAN_40_V1`)

| Market Condition | Total Bars | Exact Zero Returns ($R_t = 0.0$) | Non-Zero Returns ($R_t \neq 0.0$) | Portfolio State When $R_t = 0.0$ |
| :--- | :---: | :---: | :---: | :--- |
| **When Equities are Closed** | 9,924 bars | **9,775 bars (98.50%)** | **149 bars (1.50%)** | Portfolio is in **100% Cash** ($\text{Open Positions} = 0$) |
| **When Equities are Open** | 10,500 bars | **9,696 bars (92.34%)** | **804 bars (7.66%)** | Portfolio is in cash waiting for signals, or prices flat |
| **Full Historical Timeline** | **20,424 bars** | **19,471 bars (95.33%)** | **953 bars (4.67%)** | Active trading events across all 7 assets |

---

### 4. Verification of Overnight & Weekend Crypto Valuation

A core audit question was: **Do BTC and ETH price movements contribute to portfolio returns when equity markets are closed?**

#### 4.1 Empirical Proof of Crypto Contribution
**YES.** Across `RS_MOM_DONCHIAN_40_V1`, there are **149 non-zero portfolio return bars** during equity market closures. During these hours, equity prices were static, but open cryptocurrency positions were marked-to-market each hour, generating genuine portfolio returns.

#### 4.2 Independent Reconstructed Sample 1: Active Weekend Holding (October 7, 2024)
Between Sunday night and Monday pre-market, October 7, 2024, US equity markets were completely closed. The portfolio held 1 open position in `ETHUSDT` (Quantity = 10.1554 ETH):

| Timestamp (UTC) | Equity Market Status | Open Positions | Cash ($) | Mark-to-Market Equity ($) | Calculated $R_t$ (%) | Attribution |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `2024-10-07 00:00:00` | **CLOSED** | 1 (`ETHUSDT`) | 73,611.34 | 98,148.52 | - | Entry established |
| `2024-10-07 01:00:00` | **CLOSED** | 1 (`ETHUSDT`) | 73,611.34 | 98,215.51 | **+0.0683%** | ETH price rose \$2,416.14 $\to$ \$2,422.74 |
| `2024-10-07 02:00:00` | **CLOSED** | 1 (`ETHUSDT`) | 73,611.34 | 98,293.56 | **+0.0795%** | ETH price rose \$2,422.74 $\to$ \$2,430.42 |
| `2024-10-07 03:00:00` | **CLOSED** | 0 (Exited) | 98,164.00 | 98,164.00 | **-0.1318%** | Trailing stop triggered, realized trade |

**Mathematical Proof:**
$$R_{01:00} = \frac{98215.51 - 98148.52}{98148.52} \times 100 = \frac{+66.99}{98148.52} \times 100 = \mathbf{+0.06825\%}$$
$$\text{ETH Value Change} = 10.1554 \times (2422.74 - 2416.14) = 10.1554 \times 6.60 = \mathbf{+\$67.02} \approx \Delta E$$
This proves that when crypto is held, price movements contribute to portfolio returns during equity market closures.

#### 4.3 Independent Reconstructed Sample 2: 100% Cash State (January 2–3, 2024)
When strategy rules generate zero entry signals, the portfolio holds zero positions ($\text{cash} = \$100,000.00$):

| Timestamp (UTC) | Equity Market Status | Open Positions | Cash ($) | Total Equity ($) | Calculated $R_t$ (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `2024-01-02 23:00:00` | **CLOSED** | 0 | 100,000.00 | 100,000.00 | **0.0000%** |
| `2024-01-03 00:00:00` | **CLOSED** | 0 | 100,000.00 | 100,000.00 | **0.0000%** |
| `2024-01-03 01:00:00` | **CLOSED** | 0 | 100,000.00 | 100,000.00 | **0.0000%** |

Because $\text{cash}_t \equiv \text{cash}_{t-1}$, $E_t - E_{t-1} = 0$, yielding exact mathematical zeros.

---

### 5. Multi-Strategy Breakdown Across the 9 Candidates

| Strategy ID | Family | Total Observations | Zero Returns | Zero Ratio (%) | Non-Zero Bars During Equity Closures | Active Crypto Trade Events |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `RS_TF_DUAL_EMA_21_55_V1` | Trend | 20,424 | 19,931 | 97.59% | 79 bars | 493 active events |
| `RS_TF_DUAL_EMA_20_50_V1` | Trend | 20,424 | 19,896 | 97.41% | 96 bars | 528 active events |
| `RS_TF_DUAL_EMA_50_100_V1` | Trend | 20,424 | 20,147 | 98.64% | 46 bars | 277 active events |
| `RS_MOM_DONCHIAN_20_V1` | Momentum | 20,424 | 18,940 | 92.73% | 274 bars | 1,484 active events |
| `RS_MOM_DONCHIAN_40_V1` | Momentum | 20,424 | 19,471 | 95.33% | 149 bars | 953 active events |
| `RS_MOM_DONCHIAN_55_V1` | Momentum | 20,424 | 19,630 | 96.11% | 119 bars | 794 active events |
| `RS_MR_BB_RSI_20_STD_V1` | Mean Rev | 20,424 | 18,971 | 92.89% | 274 bars | 1,453 active events |
| `RS_MR_BB_RSI_22_STD_V1` | Mean Rev | 20,424 | 19,458 | 95.27% | 183 bars | 966 active events |
| `RS_MR_BB_RSI_25_STD_V1` | Mean Rev | 20,424 | 19,888 | 97.38% | 100 bars | 536 active events |

---

### 6. Forensic Conclusion & Status

1. **Portfolio-Level Nature Confirmed:** The synchronized matrix represents genuine mark-to-market portfolio percentage returns.
2. **Zero-Return Causality Proven:** High zero-return percentages stem from genuine portfolio cash allocations during non-signal periods and closed equity sessions.
3. **Overnight Crypto Contribution Confirmed:** Cryptocurrency positions actively generate non-zero portfolio returns during nights and weekends when held.
4. **Zero Missing Values:** All 20,424 bars across all 9 candidate strategies are 100% complete and accounted for.
