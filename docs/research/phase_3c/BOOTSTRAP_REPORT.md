# BTC-ML SYSTEM V2 — PHASE 3C BOOTSTRAP REPORT
## Non-Parametric Trade & Stationary Block Bootstrap Resampling Analysis

- **Date:** 2026-11-24
- **Auditor:** Senior Quantitative Researcher & Backtesting Auditor
- **Repository Branch:** `feat/phase-3c-controlled-filter-experiment`
- **Iterations:** 1,000 synthetic histories per candidate (Random Seed: 42)
- **Engines:** IID Trade Bootstrap & Politis-Romano Stationary Block Bootstrap
- **Mandatory Disclosure:**
  > **`HISTORICAL EXPLORATORY EVALUATION — PRIOR DATASET INSPECTION DISCLOSED`**  
  > Evaluated on historical data with prior inspection disclosed.

---

## 1. RESAMPLING METHODOLOGY

1. **Trade-Return Bootstrap (IID):** Resamples the empirical PnL dollars of completed trades with replacement over 1,000 synthetic sequences, evaluating path-independent total returns, win rates, and maximum drawdowns.
2. **Stationary Block Bootstrap (Politis & Romano 1994):** Resamples periodic continuous returns with geometrically distributed random block lengths (expected block size $L=24$ bars), strictly preserving serial autocorrelation, volatility clustering, and regime stationarity.

---

## 2. EMPIRICAL BOOTSTRAP DISTRIBUTIONS

```
                               BOOTSTRAP RETURN DISTRIBUTIONS (95% CI)
    CONTROL:      [========================|===========] (Mean: -9.56%)
                  -19.35%                 0.0%       +0.75%

    ADX25:                 [===============|=====]       (Mean: -4.25%)
                           -11.50%        0.0%  +3.26%

    4H EMA:       [========================]             (Mean: -11.36%)
                  -20.41%          -2.25% 0.0%
```

### Detailed Numerical Summary:

| Candidate Strategy | Original Trades | Trade BS Mean Return | Trade BS 95% CI | Prob. Negative Return | 95th Percentile MaxDD | Stationary BS 95% CI |
|---|---|---|---|---|---|---|
| **CONTROL** | 913 | **$-9.56\%$** | **$[-19.35\%, +0.75\%]$** | **$96.60\%$** | **$19.19\%$** | **$[-19.82\%, +0.83\%]$** |
| **ADX25** | 395 | **$-4.25\%$** | **$[-11.50\%, +3.26\%]$** | **$86.50\%$** | **$11.46\%$** | **$[-11.48\%, +4.66\%]$** |
| **4H EMA SLOPE** | 813 | **$-11.36\%$** | **$[-20.41\%, -2.25\%]$** | **$99.40\%$** | **$20.20\%$** | **$[-21.41\%, -1.20\%]$** |

---

## 3. PROBABILITY OF NEGATIVE RETURN & CAPITAL AT RISK

### 1. Control Candidate (`DONCHIAN_40`)
- **Probability of Negative Return:** **$96.60\%$** under trade resampling.
- Only $3.4\%$ of bootstrap resamples finished with positive equity.
- 95th percentile maximum drawdown reached **$19.19\%$**, nearly breaching the 20% institutional risk threshold.

### 2. ADX Treatment (`ADX25`)
- **Probability of Negative Return:** **$86.50\%$**.
- While superior to Control (reducing negative outcome frequency from $96.6\%$ to $86.5\%$), the overwhelming majority of paths still produce capital losses.
- 95th percentile maximum drawdown was significantly compressed to **$11.46\%$** (a $40.3\%$ risk reduction).

### 3. 4H EMA Slope Treatment
- **Probability of Negative Return:** **$99.40\%$**.
- The 95% confidence interval is entirely negative ($[-20.41\%, -2.25\%]$), indicating near-certain capital depletion under stationary resampling.
- 95th percentile maximum drawdown breached the portfolio risk limit at **$20.20\%$**.

---

## 4. GATE 5 EVALUATION: STATIONARY BOOTSTRAP 95% CI LOWER BOUND > 0

- **Requirement:** 95% CI lower bound must be strictly greater than 0 ($CI_{lower} > 0.00\%$).
- **Control:** Lower bound = **$-19.35\%$** $\to$ **FAILED**.
- **ADX25:** Lower bound = **$-11.50\%$** $\to$ **FAILED**.
- **4H EMA SLOPE:** Lower bound = **$-20.41\%$** $\to$ **FAILED**.

All candidates decisively fail Acceptance Gate 5.
