# INDEPENDENT AUDIT 5: CANDIDATE PERFORMANCE METRICS RECALCULATION
## Independent Verification of Candidate Performance & Annualization Factors

**Repository:** `BTC_ML_System`  
**Starting Commit:** `2a5ef45`  
**Audit Branch:** `audit/phase-3b-2-1-verification`  
**Audit Verdict:** `VERIFIED`  

---

### 1. Executive Summary & Objective

Phase 3B.2 Workstream 5 re-evaluated all nine pre-registered research candidate strategies across the authentic 7-asset universe (`AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`, `BTCUSDT`, `ETHUSDT`) over the synchronized observation window of $T = 20,424$ hourly bars.

The reported result was that **every candidate generated a negative Sharpe ratio and negative net total return**, failing pre-paper-trading validation thresholds.

This independent audit:
1. Independently recalculates all performance metrics (Sharpe ratio, net return, max drawdown, total trades, win rate, profit factor, annual turnover) directly from the simulation engine.
2. Compares the independent calculations against the values reported in Phase 3B.2.
3. Rigorously audits the annualization factor mathematics ($252 \times 24$ vs $365 \times 24$ vs $252 \times 6.5$) and verifies that the negative verdict is invariant to annualization choices.

---

### 2. Candidate Performance Independent Recalculation Table

Simulation parameters: Initial Capital = \$100,000.00 USD, Max Positions = 4, Risk per Trade = 0.5%, Slippage = 2 bps (equities) / 5 bps (crypto), Commission = 0 bps (equities) / 10 bps (crypto), Next-Bar Open execution.

| Strategy ID | Family | Reported Sharpe | Independently Recalculated Sharpe | Reported Net Return | Recalculated Net Return | Reported Max DD | Recalculated Max DD | Trades | Win Rate | Profit Factor | Status |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `RS_TF_DUAL_EMA_21_55_V1` | Trend | -1.35 | **-1.35** | -8.21% | **-8.21%** | 8.54% | **8.54%** | 557 | 44.3% | 0.78 | **VERIFIED** |
| `RS_TF_DUAL_EMA_20_50_V1` | Trend | -1.44 | **-1.44** | -9.35% | **-9.35%** | 11.56% | **11.56%** | 592 | 41.7% | 0.76 | **VERIFIED** |
| `RS_TF_DUAL_EMA_50_100_V1` | Trend | -1.34 | **-1.34** | -5.94% | **-5.94%** | 7.48% | **7.48%** | 293 | 43.7% | 0.71 | **VERIFIED** |
| `RS_MOM_DONCHIAN_20_V1` | Momentum | -1.64 | **-1.64** | -18.07% | **-18.07%** | 21.35% | **21.35%** | 1,457 | 39.1% | 0.82 | **VERIFIED** |
| `RS_MOM_DONCHIAN_40_V1` | Momentum | -1.11 | **-1.11** | -9.57% | **-9.57%** | 13.22% | **13.22%** | 913 | 41.5% | 0.85 | **VERIFIED** |
| `RS_MOM_DONCHIAN_55_V1` | Momentum | -1.12 | **-1.12** | -8.54% | **-8.54%** | 10.35% | **10.35%** | 735 | 41.6% | 0.83 | **VERIFIED** |
| `RS_MR_BB_RSI_20_STD_V1` | Mean Rev | -2.90 | **-2.90** | -31.47% | **-31.47%** | 33.42% | **33.42%** | 1,680 | 43.1% | 0.70 | **VERIFIED** |
| `RS_MR_BB_RSI_22_STD_V1` | Mean Rev | -2.46 | **-2.46** | -22.48% | **-22.48%** | 23.90% | **23.90%** | 1,152 | 43.8% | 0.70 | **VERIFIED** |
| `RS_MR_BB_RSI_25_STD_V1` | Mean Rev | -1.66 | **-1.66** | -12.58% | **-12.58%** | 14.20% | **14.20%** | 640 | 42.2% | 0.72 | **VERIFIED** |

**Discrepancy Check:**  
Every metric matches to two decimal places ($0.00\%$ discrepancy across all 9 candidate strategies).

---

### 3. Annualization Factor Audit & Mathematical Invariance

A critical question in multi-asset systems combining equities and crypto is the choice of annualization factor $A$ in the Sharpe ratio formula:
$$\text{Sharpe}_{\text{ann}} = \frac{\mu_r}{\sigma_r} \cdot \sqrt{A}$$

#### 3.1 Potential Annualization Factors for Hourly Data
1. **Continuous 24/7/365 Crypto Standard:**
   $$A_{\text{crypto}} = 365 \times 24 = \mathbf{8,760 \text{ hours/year}} \implies \sqrt{A} \approx 93.59$$
2. **Standard Trading Days $\times$ 24 Hours:**
   $$A_{252 \times 24} = 252 \times 24 = \mathbf{6,048 \text{ hours/year}} \implies \sqrt{A} \approx 77.77$$
3. **Extended Hours US Equities Standard:**
   $$A_{\text{extended}} = 252 \times 16 = \mathbf{4,032 \text{ hours/year}} \implies \sqrt{A} \approx 63.50$$
4. **Regular Trading Hours (RTH) Equity Standard:**
   $$A_{\text{RTH}} = 252 \times 6.5 = \mathbf{1,638 \text{ hours/year}} \implies \sqrt{A} \approx 40.47$$

#### 3.2 Sensitivity of Top Candidate (`RS_MOM_DONCHIAN_40_V1`) to Annualization Choice
The mean periodic hourly return $\mu_r = -0.0004685\%$ and periodic standard deviation $\sigma_r = 0.032896\%$, giving an unannualized periodic Sharpe of:
$$\text{Sharpe}_{\text{periodic}} = \frac{\mu_r}{\sigma_r} = \mathbf{-0.01424176}$$

Scaling this periodic Sharpe across all candidate annualization factors:

| Annualization Convention | Formula | Factor ($A$) | Scaling Factor ($\sqrt{A}$) | Resulting Annualized Sharpe | Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Full Continuous Year** | $365 \times 24$ | 8,760 | 93.59 | **-1.33** | **NEGATIVE** |
| **Standard Evaluation Engine** | $252 \times 24$ | 6,048 | 77.77 | **-1.11** | **NEGATIVE** |
| **Extended Session Year** | $252 \times 16$ | 4,032 | 63.50 | **-0.90** | **NEGATIVE** |
| **Regular Hours Year** | $252 \times 6.5$ | 1,638 | 40.47 | **-0.58** | **NEGATIVE** |

#### 3.3 The Invariance Proof
Because the mean periodic return is negative ($\mu_r < 0$):
$$\text{sgn}(\text{Sharpe}_{\text{ann}}) = \text{sgn}(\mu_r) = -1, \quad \forall A > 0$$
No choice of annualization factor can convert a negative mean return into a positive Sharpe ratio. The failure of every candidate strategy to achieve the minimum validation threshold ($\text{Sharpe} \ge 1.0$) is mathematically invariant to the annualization factor.

---

### 4. Qualitative Performance Review Across Strategy Families

1. **Trend-Following Family (`RS_TF_DUAL_EMA_*`):**
   - Suffered drawdowns between 7.48% and 11.56%.
   - Fast EMA combinations (21/55 and 20/50) churned excessively during consolidation regimes, realizing win rates of ~41.7% - 44.3%.
   - The slow variant (50/100) limited trading to 293 trades and reduced turnover to 0.95x, but still failed to overcome friction (-5.94% net return).
2. **Momentum Breakout Family (`RS_MOM_DONCHIAN_*`):**
   - Donchian 40 achieved the best Sharpe ratio among all 9 candidates (-1.11), but generated a net loss of -9.57%.
   - Donchian 20 traded 1,457 times, incurring severe slippage friction (-18.07% net return).
3. **Mean Reversion Family (`RS_MR_BB_RSI_*`):**
   - Severe failure across all variants (-12.58% to -31.47% net return).
   - In trending markets (especially NVDA's parabolic expansion), counter-trend mean-reversion entries triggered repeated stop-outs.

---

### 5. Audit 5 Verdict & Status

**Verdict:** `VERIFIED`

1. 100% of candidate performance metrics are reproduced with zero discrepancy.
2. The negative Sharpe ratio verdict is proven mathematically invariant to annualization conventions.
3. Every candidate strategy fails validation thresholds.
