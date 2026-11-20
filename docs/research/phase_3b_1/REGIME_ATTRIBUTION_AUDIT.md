# REGIME ATTRIBUTION FORENSIC AUDIT
## Phase 3B.1 Forensic Audit: Attribution Code Defect & Volatility Quantile Lookahead

**Repository:** `BTC_ML_System`  
**Audit Branch:** `audit/phase-3b-1-integrity`  
**Base Commit:** `ed573c1`  
**Target Module:** `btc_ml_system.src.research.evaluator.ResearchEvaluator.evaluate_regimes`  
**Audit Verdict:** `FAILED` (Implementation Defect & Lookahead Bias)

---

### 1. Executive Summary

In Phase 3B (`docs/research/phase_3b/REGIME_PERFORMANCE.md`), the regime attribution for `RS_MOM_DONCHIAN_40_V1` reported that:
- In `TRENDING` regimes, the strategy won $75.00\%$ of trades (24 wins out of 32 trades) with **+$336.56 profit**.
- In `RANGING` regimes, the strategy took **543 trades** and lost **-$5,796.69**.

This forensic audit inspected `btc_ml_system/src/research/evaluator.py` and uncovered two critical methodological defects:
1. **Severe Cross-Asset Timestamp Matching Defect:** 491 out of 575 portfolio trades failed timestamp matching and defaulted to `RANGING`.
2. **In-Sample Lookahead in Volatility Percentiles:** Normalized ATR quantiles were computed across the entire historical series rather than rolling windows.

---

### 2. Forensic Investigation of the Attribution Code Defect

#### 2.1 The Faulty Code Path
Inspect `btc_ml_system/src/research/evaluator.py`, lines 514–532:

```python
# Line 514: Extracting sample dataframe
sample_df = list(data_dict.values())[0]  # <-- HARDCODED TO FIRST ASSET IN DICTIONARY (AAPL)

# Line 515-520: Computing ATR and ADX on AAPL ONLY
norm_vol = (atr / sample_df["close"]).dropna()
vol_low = norm_vol.quantile(0.33)
vol_high = norm_vol.quantile(0.67)

# Line 531-536: Building regime lookup dictionaries keyed by AAPL timestamps
for idx, row in sample_df.iterrows():
    ts = str(row["open_time"])
    vol_regime[ts] = ...
    dir_regime[ts] = ...

# Line 550-555: Attributing trades from ALL assets against the AAPL dictionary
for t in trades:
    entry_ts = str(t.get("entry_time"))
    v_reg = vol_regime.get(entry_ts, "NORMAL")    # <-- FALLBACK TO DEFAULT
    d_reg = dir_regime.get(entry_ts, "RANGING")   # <-- FALLBACK TO DEFAULT
```

#### 2.2 Forensic Findings & Trade Count Proof

1. **Dictionary Key Mismatch:**
   `sample_df` was hardcoded to `list(data_dict.values())[0]`, which was `AAPL`.
   The `vol_regime` and `dir_regime` dictionaries were therefore populated **exclusively with AAPL timestamps** (e.g. `2024-01-02 14:30:00`).
2. **Failure of Non-AAPL Trades to Match:**
   - As audited in `ASSET_LEVEL_INTEGRITY_AUDIT.md`, `MSFT`, `NVDA`, `TSLA`, and `AMZN` have timestamps offset by $+1.815$ seconds, $+3.630$ seconds, etc.
   - `BTCUSDT` and `ETHUSDT` trade 24/7 on round-hour timestamps.
   - None of the timestamps from MSFT, NVDA, TSLA, AMZN, BTCUSDT, or ETHUSDT matched the keys in the AAPL dictionary!
3. **The 491 Fallback Trades:**
   An exact trade count audit confirmed:
   - **Total Trades Evaluated:** 575 trades.
   - **Trades matching AAPL timestamps:** Exactly **84 trades** (100% of AAPL trades).
   - **Trades failing to match AAPL timestamps:** Exactly **491 trades** (85.39% of all trades).
   - All 491 unmatched trades automatically evaluated to `.get(entry_ts, "RANGING")` and `.get(entry_ts, "NORMAL")`!

4. **The False "Ranging Regime Drain" Illusion:**
   The reported claim that `RANGING` had 543 trades and lost -$5,796.69 was largely an artifact of this bug:
   - 491 trades from other assets were dumped directly into the `RANGING` bucket regardless of their actual market condition.
   - Only 52 trades from AAPL were genuinely classified by ADX (32 trending, 52 ranging $\rightarrow$ $52 + 491 = 543$ total).

---

### 3. Forensic Investigation of Volatility Quantile Lookahead

#### 3.1 The Quantile Lookahead Defect
In line 519:
```python
vol_low = norm_vol.quantile(0.33)
vol_high = norm_vol.quantile(0.67)
```
- `norm_vol.quantile()` computed the 33rd and 67th percentiles across the **entire multi-year dataset** (2024–2026).
- When classifying a bar in January 2024, the threshold utilized volatility distributions that occurred in late 2025 and 2026.
- This violates the non-negotiable rule against in-sample lookahead bias.

---

### 4. Required Remediation for Phase 3C

Before regime-based strategy filtering is implemented in Phase 3C, `ResearchEvaluator` must be refactored:
1. **Asset-Specific Regime Mapping:**
   Compute regime indicators (`norm_vol` and `ADX`) independently for each asset $A \in \{\text{AAPL}, \dots, \text{ETHUSDT}\}$. When evaluating trade $t$, look up the regime corresponding to trade $t$'s specific asset and entry timestamp:
   ```python
   asset = t["asset"]
   regime = asset_regimes[asset].get(t["entry_time"])
   ```
2. **Expanding or Rolling Quantiles:**
   Compute volatility quantile thresholds using a strictly backward-looking rolling window (e.g., 250-period rolling quantile) to eliminate lookahead bias completely.

---

### 5. Audit Classification

**Audit Verdict:** `FAILED`  
- The reported Phase 3B regime attribution results are corrupted by a dictionary timestamp key mismatch and full-sample quantile lookahead.
- While the high-level qualitative hypothesis (breakouts suffer in ranging chop) remains plausible, the specific quantitative numbers reported in Phase 3B cannot be relied upon.
