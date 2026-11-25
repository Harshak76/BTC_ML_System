# BTC-ML SYSTEM V2 — PHASE 3C TASK RUN MANIFEST
## Forensic Execution Ledger for Background Tasks (task-3588 through task-3652)

- **Audit Date:** 2026-11-24
- **Auditor:** Quantitative Systems & Backtest Verification Auditor
- **Repository:** `BTC_ML_System`
- **Branch:** `feat/phase-3c-controlled-filter-experiment`
- **Starting Commit:** `097952ad52f8eaeea11e0f649f1957041e214ac6` (`097952a`)
- **Completion Commit:** `76f7be8`

---

## 1. TASK EXECUTION INVENTORY & PROVENANCE

Five background tasks were executed during the Phase 3C research cycle. Every task's command, script path, configuration hash, data hash, exit status, and log output is documented below.

| Task ID | Execution Timestamp (UTC) | Target Script / Operation | Exit Code | Status | Primary Purpose |
|---|---|---|---|---|---|
| **`task-3588`** | 2026-11-24 12:40:45 | `scratch/run_phase_3c_simulations.py` | **0** | **SUCCESS** | Full multi-asset simulation (asset-level & portfolio-level for all 3 candidates) |
| **`task-3602`** | 2026-11-24 12:42:34 | `scratch/run_phase_3c_statistical_validation.py` | **1** | **FAILED** | First attempt of statistical validation suite (AttributeError on DSR method name) |
| **`task-3622`** | 2026-11-24 12:44:36 | `scratch/run_phase_3c_statistical_validation.py` | **1** | **FAILED** | Second attempt (TypeError on stationary_bootstrap argument `initial_capital`) |
| **`task-3636`** | 2026-11-24 12:51:00 | `scratch/run_phase_3c_statistical_validation.py` | **1** | **FAILED** | Third attempt (KeyError on Monte Carlo print format key `mean_total_return_pct`) |
| **`task-3652`** | 2026-11-24 12:58:00 | `scratch/run_phase_3c_statistical_validation.py` | **0** | **SUCCESS** | Final statistical validation suite (DSR, Bootstrap, Monte Carlo, Walk-Forward) |

---

## 2. DETAILED TASK RUN RECORDS

### Task 1: `task-3588` (Phase 3C Multi-Asset Simulations)
- **Log Path:** `C:\Users\Harshak\.gemini\antigravity\brain\0da298dc-6e23-4870-b3cb-dfce9b46062d\.system_generated\tasks\task-3588.log`
- **Command:** `python "C:\Users\Harshak\.gemini\antigravity\brain\0da298dc-6e23-4870-b3cb-dfce9b46062d\scratch\run_phase_3c_simulations.py"`
- **Git Commit:** `4729e48`
- **Input Data Hashes:**
  - `aapl_1h.csv`: `7f962cb00edd8daa9ebd7076f26dbfc9efc5ac83b133677bc9cd113920e5f1b5`
  - `msft_1h.csv`: `a31f7da2c646813aedac0d86433fe4ef5cbf0a7aab5bae0870d1064b4b862dc0`
  - `nvda_1h.csv`: `9b6cc86cabe1020e9c8b8b5036acdeaee85b7a1e7766f46b25eaebd1f20b32d7`
  - `tsla_1h.csv`: `35bc0c748b9d642c25a13ad62094f793941e8f0e8b9d5fdd74cfa65ef899471d`
  - `amzn_1h.csv`: `bf9758b3d6976109620fb82cc8c4d331e1c18a28b453b9d83eb0a2f3b57f10c4`
  - `btcusdt_4h.csv`: `30c758838c8c80f6c0666be1a5592d68bca1cf3318a57c4637ea4205f9566cb5`
  - `ethusdt_1h.csv`: `3d00b61122fb6e639ee5be9ac38223000a5a640139a55a70ca5efb0acc00cd98`
- **Output Artifact:** `scratch/phase_3c_simulation_results.json`
- **Log Excerpt:**
  ```
  === STARTING ASSET-LEVEL SIMULATIONS ===
  [RS_MOM_DONCHIAN_40_CONTROL] AAPL: Sharpe=-0.4512, Ret=-3.78%, MaxDD=5.74%, Trades=143
  [RS_MOM_DONCHIAN_40_CONTROL] MSFT: Sharpe=-0.2481, Ret=-2.36%, MaxDD=6.10%, Trades=139
  [RS_MOM_DONCHIAN_40_CONTROL] NVDA: Sharpe=0.2272, Ret=2.12%, MaxDD=3.57%, Trades=137
  [RS_MOM_DONCHIAN_40_CONTROL] TSLA: Sharpe=0.4068, Ret=3.01%, MaxDD=2.14%, Trades=95
  [RS_MOM_DONCHIAN_40_CONTROL] AMZN: Sharpe=-0.3734, Ret=-3.06%, MaxDD=4.73%, Trades=134
  [RS_MOM_DONCHIAN_40_CONTROL] BTCUSDT: Sharpe=-2.9589, Ret=-3.87%, MaxDD=4.65%, Trades=54
  [RS_MOM_DONCHIAN_40_CONTROL] ETHUSDT: Sharpe=-1.2701, Ret=-6.41%, MaxDD=7.39%, Trades=211
  ...
  === STARTING PORTFOLIO-LEVEL MULTI-ASSET SIMULATIONS ===
  [RS_MOM_DONCHIAN_40_CONTROL] PORTFOLIO: Sharpe=-1.1076, Ret=-9.57%, MaxDD=13.22%, Trades=913
  [RS_MOM_DONCHIAN_40_ADX25] PORTFOLIO: Sharpe=-0.7198, Ret=-4.30%, MaxDD=7.18%, Trades=395
  [RS_MOM_DONCHIAN_40_4H_EMA_SLOPE] PORTFOLIO: Sharpe=-1.4398, Ret=-11.32%, MaxDD=12.50%, Trades=813
  ```

---

### Task 2: `task-3602` (Statistical Suite Attempt 1)
- **Log Path:** `.../task-3602.log`
- **Exit Code:** `1` (Runtime Error)
- **Root Cause:** Invoked `dsr_engine.compute_deflated_sharpe_ratio(...)` instead of the class's actual public API method `dsr_engine.calculate_dsr(...)`.
- **Log Output:**
  ```
  === COMPUTING DSR ===
  Traceback (most recent call last):
    File ".../run_phase_3c_statistical_validation.py", line 77, in <module>
      dsr_out = dsr_engine.compute_deflated_sharpe_ratio(
  AttributeError: 'DeflatedSharpeEngine' object has no attribute 'compute_deflated_sharpe_ratio'. Did you mean: 'compute_probabilistic_sharpe_ratio'?
  ```

---

### Task 3: `task-3622` (Statistical Suite Attempt 2)
- **Log Path:** `.../task-3622.log`
- **Exit Code:** `1` (Runtime Error)
- **Differences from Run 1:** Updated `dsr_engine.calculate_dsr(...)` with trial accounting across 12 cumulative trials. DSR completed successfully.
- **Root Cause:** In stationary bootstrap block, passed `initial_capital=100000.0` to `BootstrapEngine.stationary_bootstrap(...)`, which only accepts `returns`, `expected_block_size`, `n_iterations`, `random_seed`.
- **Log Output:**
  ```
  === COMPUTING DSR ===
  Total trials accounted for in DSR: 12 (Phase 3B: 9, Phase 3C: 3)
  [RS_MOM_DONCHIAN_40_CONTROL] DSR: 0.0007, PSR: 0.0467, ExpMax: 1.0081
  [RS_MOM_DONCHIAN_40_ADX25] DSR: 0.0044, PSR: 0.1376, ExpMax: 1.0081
  [RS_MOM_DONCHIAN_40_4H_EMA_SLOPE] DSR: 0.0001, PSR: 0.0146, ExpMax: 1.0081

  === RUNNING BOOTSTRAP ===
  Traceback (most recent call last):
    File ".../run_phase_3c_statistical_validation.py", line 115, in <module>
      bs_stat_res = bs_engine.stationary_bootstrap(ret_arr, initial_capital=100000.0)
  TypeError: BootstrapEngine.stationary_bootstrap() got an unexpected keyword argument 'initial_capital'
  ```

---

### Task 4: `task-3636` (Statistical Suite Attempt 3)
- **Log Path:** `.../task-3636.log`
- **Exit Code:** `1` (Runtime Error)
- **Differences from Run 2:** Fixed `stationary_bootstrap` argument and return scaling. Bootstrap completed successfully.
- **Root Cause:** Key mismatch in print statement for Monte Carlo results: accessed `fee_res['mean_total_return_pct']` instead of the engine's actual key `fee_res['mean_return_pct']`.
- **Log Output:**
  ```
  === RUNNING BOOTSTRAP ===
  [RS_MOM_DONCHIAN_40_CONTROL] Trade BS Return 95% CI: [-19.35%, 0.75%], Prob Neg: 96.6%
  [RS_MOM_DONCHIAN_40_CONTROL] Stationary BS Return 95% CI: [-19.82%, 0.83%]
  [RS_MOM_DONCHIAN_40_ADX25] Trade BS Return 95% CI: [-11.50%, 3.26%], Prob Neg: 86.5%
  [RS_MOM_DONCHIAN_40_ADX25] Stationary BS Return 95% CI: [-11.48%, 4.66%]
  [RS_MOM_DONCHIAN_40_4H_EMA_SLOPE] Trade BS Return 95% CI: [-20.41%, -2.25%], Prob Neg: 99.4%
  [RS_MOM_DONCHIAN_40_4H_EMA_SLOPE] Stationary BS Return 95% CI: [-21.41%, -1.20%]

  === RUNNING MONTE CARLO STRESS SUITE ===
  Traceback (most recent call last):
    File ".../run_phase_3c_statistical_validation.py", line 135, in <module>
      print(f"[{sid}] MC 2x Fees: Mean Ret={fee_res['mean_total_return_pct']:.2f}%, 95th MaxDD={fee_res['percentiles']['max_drawdown']['95th']:.2f}%, Ruin Prob={fee_res['prob_ruin_pct']:.2f}%")
  KeyError: 'mean_total_return_pct'
  ```

---

### Task 5: `task-3652` (Final Successful Statistical Validation Run)
- **Log Path:** `.../task-3652.log`
- **Exit Code:** `0` (Success)
- **Differences from Run 3:** Fixed Monte Carlo dictionary key mappings.
- **Output Artifact:** `scratch/phase_3c_statistical_validation.json`
- **Execution Summary:**
  - DSR computed across all 12 cumulative trials ($N_{3B}=9, N_{3C}=3$).
  - Trade-return and Stationary block bootstrap completed (1,000 resamples each).
  - 9 institutional Monte Carlo stress scenarios evaluated.
  - 5-fold rolling chronological walk-forward partitions evaluated.
  - PBO status recorded as `INCOMPLETE — INSUFFICIENT GENUINE CANDIDATE POOL`.
