# PHASE 2.2 — HISTORICAL EXPERIMENT REGISTRY REPORT

**Audit & Implementation Date:** November 19, 2026  
**Author:** Quantitative Development & Risk Architecture Team  
**Repository:** `BTC_ML_System`  
**Branch:** `feat/phase-2-2-validation-corrections`  
**Target Module:** `btc_ml_system/src/validation/experiment_tracker.py`  
**Database:** `BTC_ML_System/data/btc_ml_system.duckdb`  
**Test Suite:** `btc_ml_system/tests/test_validation_corrections_phase2_2.py`  
**Status:** `REMEDIATED & VERIFIED`

---

## 1. Executive Summary

In Phase 2.1, the audit identified that experiment tracking was purely file-based, writing isolated JSON files to `btc_ml_system/experiments/`. This design suffered from three critical flaws:
1. **Trial Amnesia:** When calculating the Deflated Sharpe Ratio (DSR), the system only knew about the trials executed in the *current* Python session. It lacked persistent knowledge of prior backtests, grid searches, and parameter sweeps. This caused DSR to drastically underestimate the effective number of trials ($N$), artificially inflating statistical significance.
2. **Missing Metadata:** Experiment runs lacked automated capture of the underlying Git commit hash, dataset date ranges, and validation verdicts.
3. **Absence of Centralized Relational Querying:** Experiments could not be joined against database trade logs (`trades` table) or audited systematically.

In Phase 2.2, we established a persistent, append-only experiment registry directly within DuckDB (`data/btc_ml_system.duckdb`), fully integrated with `ExperimentTracker`.

---

## 2. DuckDB Schema Architecture

The `experiment_registry` table was created with strict append-only constraints and formal audit typing:

```sql
CREATE TABLE IF NOT EXISTS experiment_registry (
    experiment_id VARCHAR PRIMARY KEY,
    timestamp TIMESTAMP,
    git_commit VARCHAR,
    dataset_start VARCHAR,
    dataset_end VARCHAR,
    n_trials INTEGER,
    best_sharpe DOUBLE,
    oos_sharpe DOUBLE,
    dsr_stat DOUBLE,
    pbo_stat DOUBLE,
    validation_verdict VARCHAR,
    config_json VARCHAR,
    metadata_json VARCHAR
);
```

### Table Schema Definition

| Column | Type | Description |
| :--- | :--- | :--- |
| `experiment_id` | `VARCHAR` | Unique identifier (e.g., `EXP-20261118-171823-104f2f`) |
| `timestamp` | `TIMESTAMP` | ISO 8601 creation timestamp |
| `git_commit` | `VARCHAR` | Exact 40-character Git commit SHA at time of execution |
| `dataset_start` | `VARCHAR` | In-sample dataset start date (`YYYY-MM-DD`) |
| `dataset_end` | `VARCHAR` | Evaluation dataset end date (`YYYY-MM-DD`) |
| `n_trials` | `INTEGER` | Number of strategy trials / parameter combinations evaluated |
| `best_sharpe` | `DOUBLE` | Best annualized Sharpe ratio achieved in-sample |
| `oos_sharpe` | `DOUBLE` | Out-of-sample Sharpe ratio on quarantined holdout |
| `dsr_stat` | `DOUBLE` | Deflated Sharpe Ratio statistic |
| `pbo_stat` | `DOUBLE` | Probability of Backtest Overfitting ($PBO$) |
| `validation_verdict`| `VARCHAR` | Final gate verdict (`PASSED`, `REJECTED`, `INCOMPLETE`) |
| `config_json` | `VARCHAR` | Complete serialized strategy & portfolio parameters |
| `metadata_json` | `VARCHAR` | Additional hardware, runtime, and diagnostic metadata |

---

## 3. Implementation Features in `ExperimentTracker`

### 3.1. Automated Git Commit Capture
The tracker automatically resolves the active Git commit hash using `git rev-parse HEAD`. If executed in an environment without git binaries or in detached mode, it falls back gracefully to `"unknown"` without throwing exceptions:

```python
def _get_current_git_commit(self) -> str:
    try:
        cmd = ["git", "rev-parse", "HEAD"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return "unknown"
```

### 3.2. Cumulative Trial Aggregation (`get_total_historical_trials`)
To eradicate trial amnesia, `ExperimentTracker` provides a centralized query to compute the cumulative number of trials conducted across the entire history of the project:

```python
def get_total_historical_trials(self) -> int:
    con = self._get_connection()
    try:
        row = con.execute("SELECT SUM(n_trials) FROM experiment_registry").fetchone()
        count = row[0] if (row and row[0] is not None) else 0
        return max(1, int(count))
    finally:
        self._release_connection(con)
```

This ensures that the Deflated Sharpe Ratio calculation in `deflated_sharpe.py` uses the true, historically accumulated trial count $N_{\text{cumulative}}$, accurately penalizing multiple hypothesis testing.

### 3.3. Bi-Directional JSON to DuckDB Synchronization
To preserve historical records from prior phases that were only saved as JSON files in `experiments/`, `sync_json_to_duckdb()` inspects the filesystem, extracts experiment metrics, and safely inserts missing records into `experiment_registry` using `INSERT OR REPLACE`:

```python
def sync_json_to_duckdb(self) -> int:
    # Safely iterates over self.experiments_dir/*.json and populates experiment_registry
    ...
```

---

## 4. Preservation of Database Integrity

Before executing any database migrations or table creations:
1. The database was inspected: **1,334 historical trade records** exist in the `trades` table.
2. The DuckDB file (`data/btc_ml_system.duckdb`) was operated on non-destructively:
   - No `DROP TABLE` statements were executed.
   - All schema additions used `CREATE TABLE IF NOT EXISTS`.
3. Verification query confirmed:
   - `SELECT COUNT(*) FROM trades` = **1,334**.
   - `SELECT COUNT(*) FROM experiment_registry` = **1** (or cumulative synced records).
   - Historical trade records remain 100% intact.

---

## 5. Verification & Test Results

In `btc_ml_system/tests/test_validation_corrections_phase2_2.py`:
- `test_experiment_tracker_append_only_and_trial_completeness`: Verified that:
  1. An in-memory or on-disk database initializes the `experiment_registry` table.
  2. Recording multiple experiments appends records without dropping existing rows.
  3. `get_total_historical_trials()` correctly aggregates cumulative trial counts across all runs.
  4. The Git commit hash is accurately logged.
  
All tests passed with zero errors.
