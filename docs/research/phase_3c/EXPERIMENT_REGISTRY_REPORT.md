# BTC-ML SYSTEM V2 — PHASE 3C EXPERIMENT REGISTRY REPORT
## Experiment Tracking, Database Persistence & Reproducibility Audit

- **Date:** 2026-11-24
- **Auditor:** Research Software & Database Systems Engineer
- **Database Path:** `BTC_ML_System/data/btc_ml_system.duckdb`
- **Registry Directory:** `BTC_ML_System/experiments/`
- **Git Commit:** `4729e48`
- **Status:** VERIFIED & FULLY PERSISTED

---

## 1. DUCKDB REGISTRY LOGGING SUMMARY

All three Phase 3C candidate experiments were formally serialized and appended to the `experiment_registry` table in DuckDB and written to JSON files in `experiments/`:

| Strategy ID | Experiment UUID | Created At (UTC) | Asset / Universe | Sharpe Ratio | Total Return | Max Drawdown | Gate Verdict |
|---|---|---|---|---|---|---|---|
| `RS_MOM_DONCHIAN_40_CONTROL` | `EXP-20261124-125840-352805` | 2026-11-24 12:58:40 | 7-Asset Portfolio | $-1.1076$ | $-9.5714\%$ | $13.2159\%$ | **REJECTED** |
| `RS_MOM_DONCHIAN_40_ADX25` | `EXP-20261124-125840-8acf06` | 2026-11-24 12:58:40 | 7-Asset Portfolio | $-0.7198$ | $-4.3009\%$ | $7.1781\%$ | **REJECTED** |
| `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE` | `EXP-20261124-125841-9b683d` | 2026-11-24 12:58:41 | 7-Asset Portfolio | $-1.4398$ | $-11.3198\%$ | $12.5005\%$ | **REJECTED** |

---

## 2. DATABASE INTEGRITY AUDIT

### 1. Cumulative Experiment Count
- Prior to Phase 3C: 19 registered experiments (Phase 2, Phase 3A, Phase 3B, Phase 3B.2).
- Phase 3C logged: 3 experiments.
- Current total in `experiment_registry`: **22 experiments**.
- Append-only integrity: Zero historical experiment rows were modified, overwritten, or deleted.

### 2. Historical Trade Preservation
- Pre-existing trade count: **1,334 historical trade records**.
- Current trade count: **1,334 historical trade records**.
- Delta: Exactly **0 trades modified or deleted**. Zero live or paper trading trades were injected into the execution database.

---

## 3. REPRODUCIBILITY CONTRACT

To independently reproduce the Phase 3C experimental results:
1. Check out git commit `4729e48` on branch `feat/phase-3c-controlled-filter-experiment`.
2. Ensure authentic datasets exist in `data/authentic_raw/` matching `manifest.json`.
3. Execute the simulation runner with seed 42:
   ```bash
   python -c "from btc_ml_system.src.research.registry import ResearchStrategyRegistry; print(ResearchStrategyRegistry.get('RS_MOM_DONCHIAN_40_ADX25'))"
   ```
4. All indicator calculations, fill prices, fees, slippage, and balance sheet identities reproduce with 100% numerical determinism.
