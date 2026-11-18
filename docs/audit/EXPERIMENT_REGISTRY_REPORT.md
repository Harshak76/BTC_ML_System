# BTC-ML SYSTEM V2 — EXPERIMENT REGISTRY REPORT
## Experiment Tracking, Schema Specifications & Reproducibility Audit

**Date:** 2026-11-18  
**Author:** Quantitative Systems Architect  
**Branch:** `phase-2-quant-validation-lab`  
**Engine:** [ExperimentTracker](file:///C:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/btc_ml_system/src/validation/experiment_tracker.py)  
**Registry Storage:** `btc_ml_system/experiments/` & DuckDB `experiment_registry`  

---

### 1. Executive Summary

A critical standard of institutional quantitative research is strict scientific reproducibility. Every validation run, sensitivity surface, and Monte Carlo trial must be versioned, immutable, and reproducible with recorded random seeds, parameters, and dataset boundaries.

The [ExperimentTracker](file:///C:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/btc_ml_system/src/validation/experiment_tracker.py) provides a dual persistence layer:
1. **Human-Readable JSON Artifacts:** Stored in `btc_ml_system/experiments/{experiment_id}.json`.
2. **High-Performance Relational Schema:** Stored in DuckDB (`data/btc_ml_system.duckdb` table `experiment_registry`).

---

### 2. DuckDB Experiment Registry Schema

```sql
CREATE TABLE IF NOT EXISTS experiment_registry (
    experiment_id VARCHAR PRIMARY KEY,
    created_at TIMESTAMP,
    strategy_name VARCHAR,
    strategy_version VARCHAR,
    asset VARCHAR,
    timeframe VARCHAR,
    candidate_configs_count INTEGER,
    completed_trials INTEGER,
    random_seed INTEGER,
    sharpe_ratio DOUBLE,
    total_return_pct DOUBLE,
    max_drawdown_pct DOUBLE,
    pbo DOUBLE,
    dsr DOUBLE,
    gate_status VARCHAR,
    config_json VARCHAR,
    results_json VARCHAR
);
```

---

### 3. Logged Master Validation Experiments

The following formal experiments have been registered during this validation cycle:

| Experiment ID | Timestamp (UTC) | Strategy Version | Asset Universe | Candidate Trials | Observed Sharpe | PBO (%) | DSR (%) | Validation Gate Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`EXP-20261118-171823-104f2f`** | 2026-11-18 17:18:23 | `v5.1_next_bar_open` | `PORTFOLIO_7_ASSETS` | 8 | -0.00 | 80.2% | 8.5% | **REJECTED** |

#### JSON Record Location:
`btc_ml_system/experiments/EXP-20261118-171823-104f2f.json`

---

### 4. Reproducibility Protocol & Resumability

To reproduce any logged experiment:
1. Load the experiment configuration from JSON:
   ```python
   with open("btc_ml_system/experiments/EXP-20261118-171823-104f2f.json") as f:
       exp = json.load(f)
   ```
2. Initialize random number generators using `exp["random_seed"]` (`seed = 42`).
3. Re-run `run_quant_validation_lab.py`.
4. The system produces bit-identical metrics, distributions, and gate decisions.

---

### 5. Research vs Execution Segregation Audit

1. **Zero Broker Interaction:** None of the validation lab modules (`walk_forward.py`, `sensitivity.py`, `bootstrap.py`, `monte_carlo.py`, `pbo_cscv.py`, `deflated_sharpe.py`, `oos_validation.py`, `portfolio_robustness.py`, `validation_gate.py`) contain broker order submission methods or import live trading credentials.
2. **Network Sandbox:** All test suites run fully offline against cached historical Parquet data or synthetic test fixtures.
3. **Execution Safety:** The validation gate explicitly halted automated paper-trading progression, maintaining system safety.
