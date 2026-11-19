# PHASE 2.3 — HISTORICAL EXPERIMENT REGISTRY & DSR ACCOUNTING REVIEW

**Audit Date:** November 19, 2026  
**Auditor:** Quantitative Risk Engineer & Senior Algorithmic Verification Engine  
**Repository:** `BTC_ML_System`  
**Base Commit Audited:** `82f061b`  
**Audited Modules:** `btc_ml_system/src/validation/experiment_tracker.py`, `btc_ml_system/src/validation/deflated_sharpe.py`  
**Database File:** `BTC_ML_System/data/btc_ml_system.duckdb`  
**Status:** `VERIFIED WITH LIMITATIONS`

---

## 1. Scope & Objective

This report independently verifies the historical experiment tracking infrastructure and Deflated Sharpe Ratio (DSR) trial accounting.

Specific audit verifications:
1. Schema integrity and immutability of the DuckDB `experiment_registry` table.
2. Uniqueness of experiment IDs and idempotency of JSON-to-DuckDB synchronization.
3. Accounting distinction: Research trials vs. executed trades (rejecting the confusion between 1,334 trades and research trials).
4. Treatment of failed, abandoned, and unrecorded historical trials.
5. Multiple testing correlation assumptions in DSR.
6. Independent calculation and reproduction of Expected Maximum Sharpe and DSR using exact unrounded values.

---

## 2. DuckDB Experiment Registry Schema & Audit

### 2.1. Inspected Schema (`data/btc_ml_system.duckdb`)
Direct database introspection of table `experiment_registry` revealed 24 typed columns:
- Primary Key: `experiment_id VARCHAR`
- Metadata: `git_commit VARCHAR`, `created_at TIMESTAMP`, `strategy_name VARCHAR`, `strategy_version VARCHAR`, `asset VARCHAR`, `timeframe VARCHAR`
- Datasets: `dataset_identity VARCHAR`, `dataset_date_range VARCHAR`
- Trial Accounting: `candidate_configs_count INTEGER`, `completed_trials INTEGER`, `failed_trials INTEGER`, `abandoned_trials INTEGER`, `random_seed INTEGER`
- Execution & Economics: `return_frequency VARCHAR`, `cost_assumptions_json VARCHAR`
- Quantitative Metrics: `sharpe_ratio DOUBLE`, `total_return_pct DOUBLE`, `max_drawdown_pct DOUBLE`, `pbo DOUBLE`, `dsr DOUBLE`, `gate_status VARCHAR`
- Serialized State: `parameter_config_json VARCHAR`, `validation_results_json VARCHAR`

### 2.2. Current Database State
Query:
```sql
SELECT experiment_id, git_commit, created_at, candidate_configs_count, completed_trials, sharpe_ratio, gate_status 
FROM experiment_registry;
```
**Result:** Exactly 1 registered experiment:
- `experiment_id`: `'EXP-20261118-171823-104f2f'`
- `git_commit`: `'aa5ee10487ed9c3753b8d15f4ffa59c6c0f6aa72'`
- `created_at`: `2026-11-18 22:49:27.671765`
- `candidate_configs_count`: `8`
- `completed_trials`: `8`
- `sharpe_ratio`: `-0.0029929478416542985`
- `gate_status`: `'REJECTED'`

### 2.3. Append-Only Immutability & Idempotency
- **Idempotency:** Re-running `tracker.sync_json_to_duckdb()` uses `INSERT OR REPLACE INTO experiment_registry`, safely updating records without creating duplicate rows.
- **Append-Only Violation Guard:** In `ExperimentTracker.log_experiment()`, attempting to log an experiment whose ID already exists in DuckDB raises an explicit `ValueError("Append-only violation: Experiment ... already exists in database")`. Verified by unit test `test_experiment_tracker_append_only_and_trial_completeness`.

---

## 3. Distinction: Executed Trades vs. Research Trials

A fundamental principle of quantitative methodology:
> **1,334 database trade records are NOT 1,334 research trials.**

- **Historical Trades ($1,334$):** Represent realized executions produced by backtesting strategies over historical candles. These populate the `trades` table and constitute the sample observations ($T$) for performance and bootstrap resampling.
- **Research Trials ($N$):** Represent distinct strategy configurations, hyperparameter combinations, feature subsets, or structural variations evaluated during development.
- **Trial Audit:** The registry records exactly $N = 8$ completed candidate trials for experiment `EXP-20261118-171823-104f2f`. The system does **not** mischaracterize the 1,334 trades as trials.

---

## 4. Unrecorded Historical Trials & Disclosure

### 4.1. Unrecorded Historical Explorations
During Phase 0, Phase 1, and early Stage 1 research, multiple exploratory parameter sweeps were conducted (regime volatility thresholds, session filter toggles, ATR stop distances). These runs occurred before the creation of `experiment_registry` and were not captured in DuckDB.

### 4.2. Forensic Disclosure
`ExperimentTracker.get_total_historical_trials()` explicitly acknowledges this reality rather than fabricating synthetic historical records:
```python
"missing_historical_trials_documented": True,
"documentation": (
    "Phase 0 and Phase 1 exploratory runs (estimated 25-40 parameter combinations across "
    "Stage 1 loosened, regime threshold variations, and session filter tests) were executed "
    "prior to the creation of the persistent registry and are not recorded in DuckDB. "
    "These historical trials are documented as MISSING_HISTORICAL_EXPERIMENTS. "
    "Never invent fabricated trial records; DSR calculations using only registry records "
    "represent a lower bound on trial count."
)
```
This conservative posture is methodologically sound: treating $N = 8$ provides a mathematical *lower bound* on selection bias. If the estimated 25–40 missing trials were included, DSR would be even lower, confirming the strategy's failure.

---

## 5. Independent Deflated Sharpe Ratio (DSR) Calculation

Using the Bailey & López de Prado (2014) framework and Mertens standard error under non-normal returns:

### 5.1. Input Parameters from Audited Baseline
- Observed Annualized Sharpe Ratio: $SR = -0.0029929478416542985$
- Sample Size: $T = 628$ trades / steps
- Annualization Factor: $A = 252 \times 24 = 6,048$
- Observed Skewness: $\gamma_3 = 0.5631611954866087$
- Observed Kurtosis: $\gamma_4 = 110.1896716332217$ (extreme fat tails)
- Candidate Trials Evaluated: $N = 8$

### 5.2. Independent Numerical Results (Unrounded)

$$\text{Periodic Sharpe: } SR_{\text{periodic}} = \frac{SR}{\sqrt{A}} = \frac{-0.00299295}{\sqrt{6048}} = \mathbf{-0.00003848485}$$

$$\text{Mertens Standard Error: } \sigma_{SR} = \sqrt{\frac{1 - \gamma_3 SR + \frac{\gamma_4 - 1}{4} SR^2}{T - 1}} = \mathbf{0.039936586771555406}$$

$$\text{Expected Maximum Annualized Sharpe } (N=8): E[\max_8] = \mathbf{4.25687916770204}$$

$$\text{Expected Maximum Periodic Sharpe } (N=8): E[\max_{8, \text{periodic}}] = \mathbf{0.05473755966335554}$$

$$\text{Standardized Score } Z: z = \frac{-0.00003848 - 0.05473756}{0.03993659} = \mathbf{-1.371575}$$

$$\text{Deflated Sharpe Ratio (DSR): } \Phi(z) = \mathbf{0.08509780923947302\ (8.51\%)}$$

$$\text{Probabilistic Sharpe Ratio (PSR vs 0): } \Phi\left(\frac{SR_{\text{periodic}}}{\sigma_{SR}}\right) = \mathbf{0.49961555668703284\ (49.96\%)}$$

### 5.3. Evaluation Against Institutional Validation Gate
- Required Gate Hurdle: $\text{DSR} \ge 0.9500\ (95.0\%)$
- Observed Value: $\mathbf{0.0851\ (8.51\%)}$
- Status: **FAILED (Statistically Insignificant)**
- Conclusion: Under $N=8$ trials, there is a $91.49\%$ probability that the observed performance is a product of multiple testing selection bias rather than true trading skill.

---

## 6. Audit Summary

| Item | Verified Value | Assessment |
| :--- | :--- | :--- |
| **Unique Experiment ID** | `'EXP-20261118-171823-104f2f'` | VERIFIED |
| **Git Commit Hash Logged** | `'aa5ee10487ed9c3753b8d15f4ffa59c6c0f6aa72'` | VERIFIED |
| **Trades vs Trials Distinction** | 1,334 trades in `trades` table; 8 trials in `experiment_registry` | VERIFIED |
| **Idempotency** | Duplicate IDs rejected with `ValueError`; sync is idempotent | VERIFIED |
| **Missing Historical Trials** | Documented honestly; no synthetic records fabricated | VERIFIED |
| **Mertens Standard Error** | $0.03993658677$ | VERIFIED |
| **Expected Max Sharpe ($N=8$)** | $4.25687916770$ | VERIFIED |
| **Deflated Sharpe Ratio** | $0.08509780924$ ($8.51\%$) vs $\ge 95.0\%$ threshold | FAILED (Correctly rejected) |

**Verdict:** `VERIFIED WITH LIMITATIONS`. The database experiment registry and DSR calculations are mathematically rigorous, append-only, and accurately enforce selection bias penalties. Unrecorded Phase 0/1 trials are documented as a lower-bound limitation.
