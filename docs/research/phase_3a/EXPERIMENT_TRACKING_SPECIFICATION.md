# PHASE 3A — EXPERIMENT TRACKING SPECIFICATION

**Module:** `btc_ml_system.src.validation.experiment_tracker`  
**Database:** `BTC_ML_System/data/btc_ml_system.duckdb`  
**Specification Version:** 2.0.0  
**Status:** `MANDATORY QUANTITATIVE GOVERNANCE`

---

## 1. Overview & Institutional Mandates

Every quantitative research simulation, parameter variation, and strategy test executed within BTC-ML System V2 must be persistently recorded in an append-only relational database.

The objectives of the experiment tracking specification:
1. **Prevent Data-Mining Selection Bias:** Ensure all evaluated configurations are counted towards multiple-testing corrections in the Deflated Sharpe Ratio (DSR).
2. **Audit Reproducibility:** Pin every experiment run to an exact Git commit hash, dataset timestamp range, and hyperparameter configuration.
3. **Immutability:** Prohibit overwriting or silently deleting historical experiment records.
4. **Authentic PBO Candidates:** Enforce that candidate return streams fed to CSCV are genuine strategy simulations rather than synthetic Gaussian noise.

---

## 2. DuckDB `experiment_registry` Relational Schema

All experiments are logged directly into table `experiment_registry` in `data/btc_ml_system.duckdb`:

```sql
CREATE TABLE IF NOT EXISTS experiment_registry (
    experiment_id VARCHAR PRIMARY KEY,
    git_commit VARCHAR,
    created_at TIMESTAMP,
    strategy_name VARCHAR,
    strategy_version VARCHAR,
    asset VARCHAR,
    timeframe VARCHAR,
    dataset_identity VARCHAR,
    dataset_date_range VARCHAR,
    candidate_configs_count INTEGER,
    completed_trials INTEGER,
    failed_trials INTEGER,
    abandoned_trials INTEGER,
    random_seed INTEGER,
    return_frequency VARCHAR,
    cost_assumptions_json VARCHAR,
    sharpe_ratio DOUBLE,
    total_return_pct DOUBLE,
    max_drawdown_pct DOUBLE,
    pbo DOUBLE,
    dsr DOUBLE,
    gate_status VARCHAR,
    parameter_config_json VARCHAR,
    validation_results_json VARCHAR
);
```

---

## 3. Append-Only Immutability & Duplicate Prevention

### 3.1. Append-Only Rule
In `ExperimentTracker.log_experiment()`:
- Before insertion, the engine queries `SELECT COUNT(*) FROM experiment_registry WHERE experiment_id = ?`.
- If a record with the identical `experiment_id` already exists, execution raises:
  `ValueError: Append-only violation: Experiment ... already exists in database.`
- Historical backtest records cannot be overwritten, modified, or scrubbed.

### 3.2. Idempotent Synchronization (`sync_json_to_duckdb`)
- Filesystem JSON files stored in `experiments/*.json` can be synchronized into DuckDB using `INSERT OR REPLACE INTO experiment_registry`.
- The synchronization process is idempotent and creates zero duplicate rows.

---

## 4. Multiple-Testing Trial Accounting for DSR

### 4.1. Cumulative Trial Aggregation
In `ExperimentTracker.get_total_historical_trials()`:
- Cumulative research trials ($N_{\text{cumulative}}$) are aggregated across all registered experiments in DuckDB:
  $$N_{\text{cumulative}} = \sum \text{candidate\_configs\_count}$$
- When calculating DSR in `DeflatedSharpeEngine`, $N_{\text{cumulative}}$ is supplied as the trial count hurdle, ensuring historical multiple-testing is properly penalized.

### 4.2. Disclosure of Unrecorded Historical Trials
- Exploratory runs from Phase 0 and Phase 1 (estimated 25–40 trials) that predated the persistent registry are documented as `MISSING_HISTORICAL_EXPERIMENTS`.
- The system never fabricates synthetic historical records. The DuckDB trial count serves as a verified lower bound.

---

## 5. Candidate Matrix Protocol for CSCV / PBO

### 5.1. Prohibition of Synthetic Gaussian Noise
- During the Phase 2.3 audit, it was discovered that `run_quant_validation_lab.py` previously generated candidates by adding random Gaussian noise to baseline returns (`base_rets + rng.normal(...)`).
- **Phase 3A Standard:** Synthetic Gaussian perturbations are **strictly prohibited**.
- The candidate return matrix $M_{T \times N}$ must be constructed using `GenuineCandidateMatrixBuilder` from the actual periodic return streams of distinct research strategy runs.

### 5.2. Minimum Candidate Threshold & Incomplete Flag
- If fewer than 4 genuine candidate return streams are available ($N < 4$), CSCV lacks sufficient combinatorial combinations to evaluate relative rank overfitting reliably.
- In this scenario, `GenuineCandidateMatrixBuilder` automatically sets:
  ```json
  {
    "is_sufficient_for_pbo": false,
    "status": "INCOMPLETE",
    "reason": "Candidate pool contains fewer than 4 genuine candidates. PBO must be marked INCOMPLETE."
  }
  ```
- The validation gate treats this as `INCOMPLETE`, preventing unverified metrics from passing the gate.
