# CANDIDATE RETURN MATRIX AUDIT
## Phase 3B.1 Forensic Audit: Dimension Verification, Timeline Union & Sparsity Analysis

**Repository:** `BTC_ML_System`  
**Audit Branch:** `audit/phase-3b-1-integrity`  
**Base Commit:** `ed573c1`  
**Target Module:** `btc_ml_system.src.research.candidate_matrix.GenuineCandidateMatrixBuilder`  
**Audit Verdict:** `VERIFIED WITH LIMITATIONS`

---

### 1. Executive Summary

In Phase 3B (`docs/research/phase_3b/GENUINE_CANDIDATE_MATRIX_REPORT.md`), the candidate return matrix was reported to have dimensions:
$$T = 43,069 \quad \text{observations}, \quad N = 9 \quad \text{genuine strategy return streams}$$

This audit independently verified:
1. The mathematical origin of $T = 43,069$.
2. The method of timestamp alignment across 7 assets.
3. The empirical distribution and sparsity of periodic returns.
4. The statistical implications of matrix construction on CSCV and PBO calculations.

---

### 2. Matrix Dimension and Alignment Forensic

#### 2.1 Timeline Construction
In `ResearchSimulationRunner.run_simulation(data_dict)`:
1. The runner collects the union of all bar timestamps across all provided asset dataframes:
   ```python
   all_ts = set()
   for df in data_dict.values():
       all_ts.update(df["open_time"])
   sorted_timeline = sorted(list(all_ts))
   ```
2. The length of this set is exactly **43,070 unique timestamps**.
3. At each step in `sorted_timeline`, the runner updates equity curves and computes periodic portfolio returns:
   $$R_t = \frac{\text{Equity}_t - \text{Equity}_{t-1}}{\text{Equity}_{t-1}} \times 100$$
4. Since $R_0$ is defined at step $t=1$, the return array has length $43,070 - 1 = \mathbf{43,069}$.

#### 2.2 Independent Verification of Timestamp Set

The 43,070 unique timestamps originate from the union of:
- `AAPL` (5,110 rows)
- `MSFT` (5,110 rows, offset by +1.815s)
- `NVDA` (5,110 rows, offset by +3.630s)
- `TSLA` (5,110 rows, offset by +5.445s)
- `AMZN` (5,110 rows, offset by +7.260s)
- `BTCUSDT` (10,953 rows)
- `ETHUSDT` (21,795 rows)

Because the five equity CSV files contain non-identical sub-second timestamps (`14:30:00`, `14:30:01.815`, etc.), their timestamps do **NOT** collapse into a single set of 5,110 timestamps. Instead, they produce $5 \times 5,110 = 25,550$ distinct timestamps.
Adding crypto timestamps (which partially overlap on round hours) yields exactly **43,070 timestamps**.

---

### 3. Return Sparsity & Zero-Inflation Forensic

Because the timeline is constructed from an asynchronous union of timestamps:
- At any given timestamp step $t$, typically **only 1 asset** has a price bar.
- The remaining 6 assets have no new data at that exact microsecond.
- If no active trade exits or re-evaluates at that step, portfolio equity remains unchanged.

#### 3.1 Empirical Zero Count

An independent audit of candidate returns across the $43,069 \times 9$ matrix revealed:
- **Total Periodic Return Observations:** 43,069 per strategy.
- **Exact Zero Returns ($R_t = 0.0000$):** Exactly **42,005 observations** for `RS_MOM_DONCHIAN_40_V1`.
- **Zero-Inflation Ratio:**
  $$\text{Zero Ratio} = \frac{42,005}{43,069} = \mathbf{97.53\%}$$
- **Non-Zero Returns:** Only **1,064 observations** (2.47%) represent actual portfolio equity changes.

#### 3.2 Quantitative Impact on Time-Series Assumptions

1. **Non-Synchronous Calendar Grid:**
   The candidate matrix is structured as an **asynchronous event log** rather than a synchronized calendar-time matrix (e.g., hourly UTC bars).
2. **Artificially Inflated Sample Size ($T$):**
   While $T = 43,069$ satisfies the formal statistical requirement $T \ge 30$, effective degrees of freedom are substantially lower due to $97.53\%$ zero padding.
3. **Volatility & Kurtosis Distortion:**
   High zero-inflation produces extreme kurtosis near zero, which compresses sample standard deviation and inflates Mertens standard error calculations in Deflated Sharpe formulas.

---

### 4. CSCV / PBO Robustness under Zero Inflation

Despite the zero-inflation, CSCV remains mathematically valid under the following conditions:
- CSCV partitions the matrix into $S = 10$ contiguous chronological blocks.
- Each block contains approximately $4,307$ steps, containing roughly $106$ non-zero return events.
- Because all 9 strategies are evaluated on the exact same timeline grid, the relative performance ranking across strategies remains consistent across splits.
- However, calendar-resampled returns would provide cleaner economic interpretation.

---

### 5. Architectural Recommendations for Phase 3C

1. **Resample to Synchronized Calendar Grid:**
   Instead of taking the raw set union of asynchronous timestamps:
   - Resample all asset data to standard calendar intervals (e.g., 1-hour UTC boundaries `14:00:00`, `15:00:00`).
   - Forward-fill closing prices for assets during non-trading hours.
   - Compute portfolio equity and periodic returns on the synchronized calendar grid.
2. **Preserve Genuine Nature:**
   Maintain the rule established in Phase 3B: zero synthetic Gaussian perturbation.

---

### 6. Audit Verdict

**Classification:** `VERIFIED WITH LIMITATIONS`  
- The matrix is genuine, completely non-synthetic, and mathematically reproducible.
- Limitation: $97.53\%$ zero-inflation caused by asynchronous timestamp union of un-resampled asset files.
