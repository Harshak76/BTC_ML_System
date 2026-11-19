# PHASE 2.1 — EXPERIMENT REGISTRY & PROVENANCE AUDIT REPORT

**Audit Date:** November 19, 2026  
**Auditor:** Quantitative Risk & Software Verification Engine  
**Target Repository:** `BTC_ML_System`  
**Target Module:** `btc_ml_system/src/validation/experiment_tracker.py`  
**Experiment File Audited:** `btc_ml_system/experiments/EXP-20261118-171823-104f2f.json`  
**Database File Audited:** `data/btc_ml_system.duckdb`  
**Status:** `VERIFIED WITH LIMITATIONS`  

---

## 1. Executive Summary

We audited the experiment tracking system, metadata schema, database integrity, and trial provenance implemented in `src/validation/experiment_tracker.py` and recorded in `experiments/EXP-20261118-171823-104f2f.json`.

The metadata schema successfully records strategy parameters, timestamps, dataset spans, random seeds, and metric outputs. DuckDB database records are preserved intact (1,334 historical trade records verified queryable and unmodified). However, our audit revealed that the registry only recorded the 8 candidate trials created during that single execution run, omitting the broader history of strategy trials explored across Phase 0, Phase 1, and intermediate development runs.

---

## 2. Metadata Schema & Audit Trail Verification

Experiment `EXP-20261118-171823-104f2f.json` conforms to the following schema:

```json
{
  "experiment_id": "EXP-20261118-171823-104f2f",
  "created_at": "2026-11-18T17:19:27.671765+00:00",
  "strategy_name": "btc_ml_system_v5_portfolio",
  "strategy_version": "v5.1_next_bar_open",
  "asset": "PORTFOLIO_7_ASSETS",
  "timeframe": "1H/4H_HYBRID",
  "parameter_config": { ... },
  "dataset_info": { "symbols": [...], "history_years": 2 },
  "cost_assumptions": { "slippage_bps": 5, "commission_bps": 10 },
  "candidate_count": 8,
  "completed_trials": 8,
  "random_seed": 42,
  "validation_results": { ... }
}
```

### Audit Checks:
1. **Reproducibility:** Seed 42 is explicitly tracked.
2. **Configuration Hash:** Configuration parameters are structured and human-readable.
3. **Execution Timestamp:** RFC 3339 / ISO 8601 UTC timestamp format verified.
4. **Data Isolation:** Experiment files are stored in `btc_ml_system/experiments/` without modifying core strategy source files.

---

## 3. Database Historical Integrity Verification

We inspected the DuckDB database at `data/btc_ml_system.duckdb`:
- **Historical Trades Table:** 1,334 trades preserved.
- **Data Integrity:** Read-only verification confirms no historical records were overwritten, truncated, or dropped during Phase 2 or Phase 2.1 execution.
- **Exclusion from Git:** Verified that `.gitignore` properly excludes `*.duckdb` and `*.duckdb.wal` files, preventing accidental binary commits or repository bloat.

---

## 4. Trial Accounting & Provenance Limitation

- **Finding:** In statistical multiple testing adjustments (DSR, PBO), the valid trial count $N$ must reflect the **total cumulative number of configurations attempted** throughout the entire research lifecycle, including discarded models.
- In `EXP-20261118-171823-104f2f.json`, `candidate_count` is recorded as `8`, corresponding only to the synthetic perturbation matrix evaluated in that single script execution.
- Discarded configurations from Phase 0 (e.g. Stage 1 loosened parameters, ETH session filter variants, triple barrier label configurations) were not persisted into a central multi-experiment repository.
- **Quant Consequence:** As noted in `INDEPENDENT_DSR_AUDIT.md`, this undercounts historical trials and renders DSR estimates overly optimistic.

---

## 5. Audit Classification & Recommendations

- **Classification:** `VERIFIED WITH LIMITATIONS`
- **Recommendations for Phase 3:**
  1. Build a persistent central experiment ledger in DuckDB (table `quant_experiment_registry`) where every backtest or optimization run automatically appends its parameter hash and Sharpe ratio.
  2. In the DSR calculation, automatically query `SELECT COUNT(*), VARIANCE(sharpe_ratio) FROM quant_experiment_registry` to compute multiple-testing adjustments against genuine historical research activity.
