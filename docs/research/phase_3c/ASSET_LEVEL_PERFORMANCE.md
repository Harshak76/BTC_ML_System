# BTC-ML SYSTEM V2 — PHASE 3C ASSET-LEVEL PERFORMANCE REPORT
## Comprehensive Multi-Asset Breakdown & Cross-Asset Robustness Evaluation

- **Date:** 2026-11-24
- **Auditor:** Senior Quantitative Researcher & Backtesting Auditor
- **Repository Branch:** `feat/phase-3c-controlled-filter-experiment`
- **Scope:** AAPL, MSFT, NVDA, TSLA, AMZN (US Equities 1H), BTCUSDT (Crypto 4H), ETHUSDT (Crypto 1H).
- **Mandatory Disclosure:**
  > **`HISTORICAL EXPLORATORY EVALUATION — PRIOR DATASET INSPECTION DISCLOSED`**  
  > Evaluated on historical data with prior inspection disclosed.

---

## 1. CROSS-ASSET PERFORMANCE MATRIX

All asset-level tests were conducted under isolated single-asset conditions ($100,000 capital, 1 position max) with realistic friction (Crypto: 30 bps round-trip; Equities: 4 bps round-trip):

| Candidate Strategy | Asset | Total Return | Ann. Return | Sharpe Ratio | Max Drawdown | Trades | Win Rate | Profit Factor | Final Equity |
|---|---|---|---|---|---|---|---|---|---|
| **CONTROL** | AAPL | $-3.78\%$ | $0.00\%$ | $-0.4512$ | $5.74\%$ | 143 | $42.7\%$ | 0.76 | $\$96,221.61$ |
| **CONTROL** | MSFT | $-2.36\%$ | $0.00\%$ | $-0.2481$ | $6.10\%$ | 139 | $41.7\%$ | 0.86 | $\$97,641.84$ |
| **CONTROL** | NVDA | **$+2.12\%$** | $0.00\%$ | **$+0.2272$** | $3.57\%$ | 137 | $47.4\%$ | 1.14 | $\$102,119.68$ |
| **CONTROL** | TSLA | **$+3.01\%$** | $0.00\%$ | **$+0.4068$** | $2.14\%$ | 95 | $52.6\%$ | 1.34 | $\$103,009.04$ |
| **CONTROL** | AMZN | $-3.06\%$ | $0.00\%$ | $-0.3734$ | $4.73\%$ | 134 | $44.0\%$ | 0.80 | $\$96,936.83$ |
| **CONTROL** | BTCUSDT | $-3.87\%$ | $0.00\%$ | $-2.9589$ | $4.65\%$ | 54 | $29.6\%$ | 0.46 | $\$96,129.94$ |
| **CONTROL** | ETHUSDT | $-6.41\%$ | $0.00\%$ | $-1.2701$ | $7.39\%$ | 211 | $33.2\%$ | 0.69 | $\$93,589.50$ |
| **ADX25** | AAPL | **$-1.09\%$** | $0.00\%$ | **$-0.1734$** | **$3.61\%$** | 64 | $43.8\%$ | 0.86 | $\$98,907.37$ |
| **ADX25** | MSFT | **$-1.14\%$** | $0.00\%$ | **$-0.2038$** | **$2.93\%$** | 53 | $45.3\%$ | 0.82 | $\$98,858.00$ |
| **ADX25** | NVDA | **$+0.12\%$** | $0.00\%$ | **$+0.0256$** | **$2.52\%$** | 54 | $46.3\%$ | 1.02 | $\$100,121.55$ |
| **ADX25** | TSLA | **$+2.65\%$** | $0.00\%$ | **$+0.4853$** | **$1.66\%$** | 47 | $59.6\%$ | 1.63 | $\$102,649.78$ |
| **ADX25** | AMZN | **$-0.50\%$** | $0.00\%$ | **$-0.0962$** | **$2.37\%$** | 55 | $41.8\%$ | 0.91 | $\$99,498.42$ |
| **ADX25** | BTCUSDT | **$-2.05\%$** | $0.00\%$ | **$-2.1407$** | **$2.37\%$** | 30 | $23.3\%$ | 0.46 | $\$97,947.62$ |
| **ADX25** | ETHUSDT | **$-3.09\%$** | $0.00\%$ | **$-0.9005$** | **$3.76\%$** | 92 | $38.0\%$ | 0.68 | $\$96,911.36$ |
| **4H EMA** | AAPL | $-3.80\%$ | $0.00\%$ | $-0.5040$ | $5.66\%$ | 125 | $42.4\%$ | 0.72 | $\$96,197.66$ |
| **4H EMA** | MSFT | $-2.56\%$ | $0.00\%$ | $-0.3029$ | $4.98\%$ | 126 | $40.5\%$ | 0.83 | $\$97,443.28$ |
| **4H EMA** | NVDA | $-0.85\%$ | $0.00\%$ | $-0.0921$ | $3.25\%$ | 124 | $43.5\%$ | 0.94 | $\$99,150.57$ |
| **4H EMA** | TSLA | **$+1.72\%$** | $0.00\%$ | **$+0.2457$** | $2.12\%$ | 86 | $53.5\%$ | 1.21 | $\$101,718.91$ |
| **4H EMA** | AMZN | $-1.96\%$ | $0.00\%$ | $-0.2423$ | $4.37\%$ | 118 | $44.9\%$ | 0.86 | $\$98,042.86$ |
| **4H EMA** | BTCUSDT | $-3.87\%$ | $0.00\%$ | $-2.9589$ | $4.65\%$ | 54 | $29.6\%$ | 0.46 | $\$96,129.94$ |
| **4H EMA** | ETHUSDT | $-6.50\%$ | $0.00\%$ | $-1.4512$ | $6.66\%$ | 180 | $32.2\%$ | 0.63 | $\$93,497.68$ |

---

## 2. CROSS-ASSET BREADTH & CONCENTRATION

### Acceptance Gate 3: Multi-Asset Breadth ($\ge 4$ of 7 Assets Profitable)
- **Control Strategy:** 2 of 7 assets profitable (NVDA $+2.12\%$, TSLA $+3.01\%$). **FAILED** (2/7).
- **ADX25 Strategy:** 2 of 7 assets profitable (NVDA $+0.12\%$, TSLA $+2.65\%$). **FAILED** (2/7).
- **4H EMA Strategy:** 1 of 7 assets profitable (TSLA $+1.72\%$). **FAILED** (1/7).

All three candidates fail the multi-asset robustness criterion. Profitability is entirely concentrated in single megacap momentum leaders (NVDA, TSLA) undergoing powerful macroeconomic trends, while the remaining 5 assets consistently bleed capital.

---

## 3. ASSET CLASS COMPARISON: CRYPTO VS. EQUITIES

1. **Equities Performance:**
   - Equities experienced lower drawdown ($1.66\%$ to $6.10\%$) due to milder volatility and minimal friction (4 bps round-trip).
   - TSLA was consistently profitable across all 3 candidates (Control: $+3.01\%$, ADX: $+2.65\%$, 4H EMA: $+1.72\%$), indicating that strong idiosyncratic trending assets can support breakout mechanics.
2. **Crypto Degradation:**
   - Both BTCUSDT and ETHUSDT experienced negative returns across all three candidates.
   - Crypto is heavily penalized by the 30 bps round-trip cost model (10 bps commission each side + 5 bps slippage each side).
   - In ETHUSDT, 211 trades in the Control generated $-6.41\%$ net loss, with an average trade expectancy of $-\$30.38$. Even with ADX filtering (reducing trades to 92), ETHUSDT lost $-3.09\%$.

---

## 4. ASSET-LEVEL AUDIT VERDICT

The asset-level breakdown confirms that neither filter resolves the fundamental lack of statistical edge across the broad asset universe. Both filters remain **REJECTED** under Gate 3.
