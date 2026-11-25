# BTC-ML SYSTEM V2 — PHASE 3C AUDIT EVIDENCE PACKAGE
## Comprehensive Quantitative Backtest, Mathematical Integrity & Audit Dossier

- **Audit Date:** 2026-11-24
- **Auditor Role:** Senior Quantitative Researcher, Systematic Trading Engineer & Backtesting Auditor
- **Repository:** `BTC_ML_System`
- **Audit Directory:** `docs/research/phase_3c/audit_evidence/`
- **Target Audience:** External Quantitative Reviewers, Risk Committees & Backtesting Auditors
- **Baseline Status:** **`REJECTED — NOT ELIGIBLE FOR PAPER TRADING`**
- **Mandatory Disclosure Statement:**
  > **`HISTORICAL EXPLORATORY EVALUATION — PRIOR DATASET INSPECTION DISCLOSED`**  
  > Market data across the 2024–2026 historical window was previously inspected in Phases 3A, 3B, 3B.1, and 3B.2. Consequently, all findings represent historical exploratory research and must not be represented as uninspected holdout confirmation.

---

## 1. REPOSITORY & REVISION CONTROL LEDGER

| Audit Dimension | Value / Reference | Verification Evidence |
|---|---|---|
| **Git Branch** | `feat/phase-3c-controlled-filter-experiment` | `git branch --show-current` |
| **Starting Commit** | `097952ad52f8eaeea11e0f649f1957041e214ac6` (`097952a`) | Phase 3B.2.4 audit completion commit |
| **Pre-Registration Commit** | `0cc1bafb708307db4ef99eb8a719f9b5b294c735` (`0cc1baf`) | Pre-registration committed *before* backtests |
| **Data Integrity Commit** | `0dae7456dcf9f5e1f0e2133481ba9b35a8286a07` (`0dae745`) | Data audit and execution cost verification |
| **Implementation Commit** | `4729e4878a221f5926510f27c88b7156ae2361df` (`4729e48`) | Strategy filter implementations & safety tests |
| **Completion Commit** | `76f7be8148b3012d909890a887b41639f2857476` (`76f7be8`) | Final reports, validation suite & experiment registry |
| **Working-Tree Status** | Clean (no untracked modifications) | `git status --porcelain` returns 0 entries |

### Complete Change Summary (Commit Diff):
- **Source Code Added:** `btc_ml_system/src/research/strategies/donchian_filters.py` (380 lines) implementing `Donchian40ControlStrategy`, `Donchian40AdxStrategy`, and `Donchian40HtfEmaSlopeStrategy`.
- **Package Registration:** Updated `btc_ml_system/src/research/strategies/__init__.py` and `btc_ml_system/src/research/__init__.py` to export and register the 3 candidate classes.
- **Safety Test Suite:** Created `btc_ml_system/tests/test_phase3c_filters.py` (152 lines, 4 comprehensive unit and boundary tests).
- **Deliverables Created:** 15 comprehensive markdown reports under `docs/research/phase_3c/`.
- **Database Append:** 3 experiment JSONs added in `btc_ml_system/experiments/`, 3 experiments appended to DuckDB `experiment_registry` table (total 22 rows). Exactly 0 modifications to historical trades (1,334 trades intact).
- **Production Isolation:** Zero modifications to `btc_ml_system/configs/` or any production trading code.

---

## 2. BACKGROUND TASK MANIFEST (task-3588 through task-3652)

Every long-running background command executed during Phase 3C is forensically documented below. Full task logs reside in `.system_generated/tasks/`:

| Task ID | UTC Timestamp | Command Executed | Exit Code | Input Data SHA256 Hash | Primary Outcome |
|---|---|---|---|---|---|
| **`task-3588`** | 12:40:45Z | `python scratch/run_phase_3c_simulations.py` | **0** | Verified authentic (`manifest.json`) | Completed asset-level & portfolio simulations across all 7 assets. Saved `phase_3c_simulation_results.json`. |
| **`task-3602`** | 12:42:34Z | `python scratch/run_phase_3c_statistical_validation.py` | **1** | Verified authentic | Failed with `AttributeError` on `compute_deflated_sharpe_ratio`. |
| **`task-3622`** | 12:44:36Z | `python scratch/run_phase_3c_statistical_validation.py` | **1** | Verified authentic | DSR completed. Failed with `TypeError` on `stationary_bootstrap(initial_capital)`. |
| **`task-3636`** | 12:51:00Z | `python scratch/run_phase_3c_statistical_validation.py` | **1** | Verified authentic | Bootstrap completed. Failed with `KeyError` on Monte Carlo print key. |
| **`task-3652`** | 12:58:00Z | `python scratch/run_phase_3c_statistical_validation.py` | **0** | Verified authentic | **Full success**. Completed DSR ($N=12$), Bootstrap, Monte Carlo, and 5-fold Walk-Forward splits. |

*Detailed run logs, traceback diffs, and exact terminal outputs are cataloged in [`TASK_RUN_MANIFEST.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/audit_evidence/TASK_RUN_MANIFEST.md).*

---

## 3. INVENTORY OF THE 15 PHASE 3C DELIVERABLES

All 15 deliverables are committed and present under `docs/research/phase_3c/`:

1. [`PHASE_3C_PREREGISTRATION.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/PHASE_3C_PREREGISTRATION.md) — Pre-registered hypotheses ($H_A, H_B$), candidate formulas, acceptance gates, and disclosure.
2. [`DATA_INTEGRITY_REPORT.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/DATA_INTEGRITY_REPORT.md) — SHA256 manifest reconciliation, monotonicity, duplicate and null audits across 7 assets.
3. [`EXECUTION_AND_COST_AUDIT.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/EXECUTION_AND_COST_AUDIT.md) — Friction model (30 bps crypto, 4 bps equities), collision rules, and $E = \text{Cash} + \text{MV}$ balance sheet identity audit.
4. [`CONTROL_STRATEGY_REPRODUCTION.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/CONTROL_STRATEGY_REPRODUCTION.md) — Baseline Donchian-40 benchmark evaluation ($-9.57\%$ return, Sharpe $-1.1076$).
5. [`ADX_TREATMENT_REPORT.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/ADX_TREATMENT_REPORT.md) — Evaluation of $ADX_{14} \ge 25$ (drawdown cut to $7.18\%$, return $-4.30\%$).
6. [`4H_EMA_SLOPE_TREATMENT_REPORT.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/4H_EMA_SLOPE_TREATMENT_REPORT.md) — Failure analysis of 4H EMA slope (return degraded to $-11.32\%$).
7. [`ASSET_LEVEL_PERFORMANCE.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/ASSET_LEVEL_PERFORMANCE.md) — Isolated asset-by-asset performance breakdown.
8. [`WALK_FORWARD_REPORT.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/WALK_FORWARD_REPORT.md) — 5 rolling folds cross-validation.
9. [`BOOTSTRAP_REPORT.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/BOOTSTRAP_REPORT.md) — 1,000-run trade and Politis-Romano stationary block bootstrap distributions.
10. [`MONTE_CARLO_REPORT.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/MONTE_CARLO_REPORT.md) — 9 institutional stress scenarios (fees, slippage, latency, dropouts).
11. [`DSR_AND_TRIAL_ACCOUNTING_REPORT.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/DSR_AND_TRIAL_ACCOUNTING_REPORT.md) — Deflated Sharpe Ratio with cumulative $N=12$ trial accounting.
12. [`PBO_STATUS_REPORT.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/PBO_STATUS_REPORT.md) — Formal `PBO: INCOMPLETE` status documentation.
13. [`EXPERIMENT_REGISTRY_REPORT.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/EXPERIMENT_REGISTRY_REPORT.md) — DuckDB persistence audit (22 total experiments, 1,334 trades intact).
14. [`TEST_RESULTS.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/TEST_RESULTS.md) — Unit and lookahead safety test results (10/10 passing).
15. [`PHASE_3C_FINAL_REPORT.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/PHASE_3C_FINAL_REPORT.md) — Master Phase 3C synthesis and gate verdict.

---

## 4. SOURCE CODE IMPLEMENTING ALL THREE CANDIDATES

Implemented in `btc_ml_system/src/research/strategies/donchian_filters.py`:

```python
class Donchian40ControlStrategy(BaseResearchStrategy):
    """
    Phase 3C Candidate 1 (Control):
    Exact reproduction of Phase 3B RS_MOM_DONCHIAN_40_V1.
    - 40-bar Donchian channel entry.
    - 20-bar Donchian channel exit.
    - 40-bar cumulative momentum filter (> 0).
    - RSI(14) exhaustion ceiling (< 75.0).
    - ATR(14) stops (SL 2.0x, TP 4.5x, trailing 2%).
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.channel_entry_period = int(self.params.get("channel_entry_period", 40))
        self.channel_exit_period = int(self.params.get("channel_exit_period", 20))
        self.mom_period = int(self.params.get("mom_period", 40))
        self.rsi_period = int(self.params.get("rsi_period", 14))
        self.rsi_max_entry = float(self.params.get("rsi_max_entry", 75.0))
        self.atr_period = int(self.params.get("atr_period", 14))
        self.atr_stop_multiplier = float(self.params.get("atr_stop_multiplier", 2.0))
        self.atr_tp_multiplier = float(self.params.get("atr_tp_multiplier", 4.5))
        self.trailing_stop_pct = float(self.params.get("trailing_stop_pct", 0.02))

class Donchian40AdxStrategy(Donchian40ControlStrategy):
    """
    Phase 3C Candidate 2 (ADX Treatment):
    Inherits all core mechanics of Donchian40 Control, with:
    - ADX(14) >= 25.0 filter on completed signal candle close.
    - Entries blocked if ADX < 25.0.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.adx_period = int(self.params.get("adx_period", 14))
        self.adx_threshold = float(self.params.get("adx_threshold", 25.0))

class Donchian40HtfEmaSlopeStrategy(Donchian40ControlStrategy):
    """
    Phase 3C Candidate 3 (4H EMA Slope Treatment):
    Inherits all core mechanics of Donchian40 Control, with:
    - Multi-timeframe trend confirmation from higher timeframe (4H).
    - 20-period EMA calculated strictly on fully completed 4H bars.
    - Slope = EMA_4H[k] - EMA_4H[k-1] > 0.
    - Strict Zero-Lookahead: At 1H candle close t, only completed 4H bars are referenced.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.htf_ema_period = int(self.params.get("htf_ema_period", 20))
```

---

## 5. MATHEMATICAL FORMULATION OF FILTERS

### A. ADX(14) Wilder Smoothing Formulation
For completed candle $t$:
$$TR_t = \max(High_t - Low_t, |High_t - Close_{t-1}|, |Low_t - Close_{t-1}|)$$
$$+DM_t = (High_t - High_{t-1}) \quad \text{if } High_t - High_{t-1} > Low_{t-1} - Low_t \text{ and } > 0, \text{ else } 0$$
$$-DM_t = (Low_{t-1} - Low_t) \quad \text{if } Low_{t-1} - Low_t > High_t - High_{t-1} \text{ and } > 0, \text{ else } 0$$
Using Wilder's exponential smoothing ($\alpha = 1 / 14$):
$$\overline{TR}_t = \overline{TR}_{t-1} \cdot \frac{13}{14} + TR_t \cdot \frac{1}{14}, \quad \overline{+DM}_t = \overline{+DM}_{t-1} \cdot \frac{13}{14} + +DM_t \cdot \frac{1}{14}$$
$$+DI_{14, t} = 100 \times \frac{\overline{+DM}_t}{\overline{TR}_t + 10^{-12}}, \quad -DI_{14, t} = 100 \times \frac{\overline{-DM}_t}{\overline{TR}_t + 10^{-12}}$$
$$DX_t = 100 \times \frac{|+DI_{14, t} - -DI_{14, t}|}{+DI_{14, t} + -DI_{14, t} + 10^{-12}}, \quad ADX_{14, t} = \overline{DX}_{14, t}$$
**Filter Condition:** $Signal_t = 1 \iff Breakout_t = 1 \land ADX_{14, t} \ge 25.0$.

### B. Completed 4H EMA Slope Formulation
Let $k$ index completed 4-hour bars on UTC boundaries `00:00, 04:00, 08:00, 12:00, 16:00, 20:00`:
$$EMA_{4H, 20}[k] = \alpha \cdot Close_{4H}[k] + (1 - \alpha) \cdot EMA_{4H, 20}[k-1], \quad \alpha = \frac{2}{20 + 1}$$
$$Slope_{4H}[k] = EMA_{4H, 20}[k] - EMA_{4H, 20}[k-1]$$
**Filter Condition:** $Signal_t = 1 \iff Breakout_t = 1 \land Slope_{4H}[k_{completed}] > 0$.

---

## 6. MULTI-TIMEFRAME ZERO-LOOKAHEAD EVIDENCE

At 1-hour bar close $T_{close, 1H} = T_{open, 1H} + 1\text{ hour}$, the strategy executes `pd.merge_asof(direction='backward')`:
$$k_{completed} = \max \{ k \mid T_{close, 4H, k} \le T_{close, 1H} \}$$

### Empirical Timestamp Boundary Audit:
| 1H Bar Open Time | 1H Bar Close Time | 4H Bar in Progress | Completed 4H Bar Referenced | `htf_ema_slope` Value | Status |
|---|---|---|---|---|---|
| `2024-01-01 07:00 UTC` | `08:00 UTC` | 04:00–08:00 | **04:00–08:00 (just closed)** | `+2.836879` | Updated on close |
| `2024-01-01 08:00 UTC` | `09:00 UTC` | 08:00–12:00 (forming) | **04:00–08:00** | `+2.836879` | **Zero Lookahead** |
| `2024-01-01 09:00 UTC` | `10:00 UTC` | 08:00–12:00 (forming) | **04:00–08:00** | `+2.836879` | **Zero Lookahead** |
| `2024-01-01 10:00 UTC` | `11:00 UTC` | 08:00–12:00 (forming) | **04:00–08:00** | `+2.836879` | **Zero Lookahead** |
| `2024-01-01 11:00 UTC` | `12:00 UTC` | 08:00–12:00 | **08:00–12:00 (just closed)** | `+4.728132` | Updated on close |

Unit test `test_4h_ema_slope_zero_lookahead_boundary` asserts $Slope_{08:00} == Slope_{09:00} == Slope_{10:00}$ and passes with 100% precision.

---

## 7. RAW SIMULATION PERFORMANCE OUTPUTS

### Unified Portfolio Results ($100,000 Initial Capital):
- **`RS_MOM_DONCHIAN_40_CONTROL`:**  
  Return: $-9.5714\%$, Sharpe: $-1.1076$, Sortino: $-0.3736$, Calmar: $-0.3196$, MaxDD: $13.2159\%$, Trades: 913, Win Rate: $41.51\%$, Profit Factor: 0.8453, Final Equity: $\$90,428.59$.
- **`RS_MOM_DONCHIAN_40_ADX25`:**  
  Return: $-4.3009\%$, Sharpe: $-0.7198$, Sortino: $-0.1676$, Calmar: $-0.2602$, MaxDD: $7.1781\%$, Trades: 395, Win Rate: $43.04\%$, Profit Factor: 0.8535, Final Equity: $\$95,699.07$.
- **`RS_MOM_DONCHIAN_40_4H_EMA_SLOPE`:**  
  Return: $-11.3198\%$ Sharpe: $-1.4398$, Sortino: $-0.4527$, Calmar: $-0.4018$, MaxDD: $12.5005\%$, Trades: 813, Win Rate: $40.71\%$, Profit Factor: 0.7942, Final Equity: $\$88,680.19$.

### Standalone Asset-Level Matrix:
```
CONTROL:
  AAPL:    Ret=-3.78%, Sharpe=-0.4512, MaxDD=5.74%, Trades=143, WinRate=42.7%, PF=0.76, FinalEq=$96,221.61
  MSFT:    Ret=-2.36%, Sharpe=-0.2481, MaxDD=6.10%, Trades=139, WinRate=41.7%, PF=0.86, FinalEq=$97,641.84
  NVDA:    Ret=+2.12%, Sharpe=+0.2272, MaxDD=3.57%, Trades=137, WinRate=47.4%, PF=1.14, FinalEq=$102,119.68
  TSLA:    Ret=+3.01%, Sharpe=+0.4068, MaxDD=2.14%, Trades=95,  WinRate=52.6%, PF=1.34, FinalEq=$103,009.04
  AMZN:    Ret=-3.06%, Sharpe=-0.3734, MaxDD=4.73%, Trades=134, WinRate=44.0%, PF=0.80, FinalEq=$96,936.83
  BTCUSDT: Ret=-3.87%, Sharpe=-2.9589, MaxDD=4.65%, Trades=54,  WinRate=29.6%, PF=0.46, FinalEq=$96,129.94
  ETHUSDT: Ret=-6.41%, Sharpe=-1.2701, MaxDD=7.39%, Trades=211, WinRate=33.2%, PF=0.69, FinalEq=$93,589.50

ADX25:
  AAPL:    Ret=-1.09%, Sharpe=-0.1734, MaxDD=3.61%, Trades=64,  WinRate=43.8%, PF=0.86, FinalEq=$98,907.37
  MSFT:    Ret=-1.14%, Sharpe=-0.2038, MaxDD=2.93%, Trades=53,  WinRate=45.3%, PF=0.82, FinalEq=$98,858.00
  NVDA:    Ret=+0.12%, Sharpe=+0.0256, MaxDD=2.52%, Trades=54,  WinRate=46.3%, PF=1.02, FinalEq=$100,121.55
  TSLA:    Ret=+2.65%, Sharpe=+0.4853, MaxDD=1.66%, Trades=47,  WinRate=59.6%, PF=1.63, FinalEq=$102,649.78
  AMZN:    Ret=-0.50%, Sharpe=-0.0962, MaxDD=2.37%, Trades=55,  WinRate=41.8%, PF=0.91, FinalEq=$99,498.42
  BTCUSDT: Ret=-2.05%, Sharpe=-2.1407, MaxDD=2.37%, Trades=30,  WinRate=23.3%, PF=0.46, FinalEq=$97,947.62
  ETHUSDT: Ret=-3.09%, Sharpe=-0.9005, MaxDD=3.76%, Trades=92,  WinRate=38.0%, PF=0.68, FinalEq=$96,911.36

4H EMA SLOPE:
  AAPL:    Ret=-3.80%, Sharpe=-0.5040, MaxDD=5.66%, Trades=125, WinRate=42.4%, PF=0.72, FinalEq=$96,197.66
  MSFT:    Ret=-2.56%, Sharpe=-0.3029, MaxDD=4.98%, Trades=126, WinRate=40.5%, PF=0.83, FinalEq=$97,443.28
  NVDA:    Ret=-0.85%, Sharpe=-0.0921, MaxDD=3.25%, Trades=124, WinRate=43.5%, PF=0.94, FinalEq=$99,150.57
  TSLA:    Ret=+1.72%, Sharpe=+0.2457, MaxDD=2.12%, Trades=86,  WinRate=53.5%, PF=1.21, FinalEq=$101,718.91
  AMZN:    Ret=-1.96%, Sharpe=-0.2423, MaxDD=4.37%, Trades=118, WinRate=44.9%, PF=0.86, FinalEq=$98,042.86
  BTCUSDT: Ret=-3.87%, Sharpe=-2.9589, MaxDD=4.65%, Trades=54,  WinRate=29.6%, PF=0.46, FinalEq=$96,129.94
  ETHUSDT: Ret=-6.50%, Sharpe=-1.4512, MaxDD=6.66%, Trades=180, WinRate=32.2%, PF=0.63, FinalEq=$93,497.68
```

---

## 8. ACCOUNTING & BALANCE SHEET RECONCILIATION

At every discrete step $t$:
$$\text{Equity}_t = \text{Cash}_t + \sum_{i} \text{Quantity}_{i, t} \times \text{ClosePrice}_{i, t}$$
- Across all 17,519 continuous hourly timestamps in the multi-asset simulation:
  - $\max |\text{Equity}_t - (\text{Cash}_t + \text{PositionsValue}_t)| = \mathbf{0.00000000\text{ USD}}$.
  - Position Sizing: Risk per trade $= 0.005 \times \text{Equity}_t$. Position dollar size $= \frac{\text{RiskUSD}}{\text{StopDistancePct}}$, capped at $\frac{\text{Equity}}{4}$.
  - Fills: Orders queue on signal at close $t$, fill on open $t+1$ with slippage. Stops anchor to fill price.

---

## 9. DEFLATED SHARPE RATIO (DSR) & TRIAL ACCOUNTING

- Total historical trials accounted for: $N = 12$ ($N_{3B} = 9$ variants $+ N_{3C} = 3$ candidates).
- Variance of trial Sharpes: $\sigma^2_{trials} = 0.3475$.
- Expected Maximum Sharpe under Null ($E[\max_{12}]$): **$+1.0081$**.

| Strategy Candidate | Observed Sharpe | Return Skewness | Pearson Kurtosis | Mertens SE | DSR | DSR $p$-value |
|---|---|---|---|---|---|---|
| `RS_MOM_DONCHIAN_40_CONTROL` | $-1.1076$ | $+0.9749$ | $112.06$ | $0.00760$ | **$0.0007$** | **$0.9993$** |
| `RS_MOM_DONCHIAN_40_ADX25` | $-0.7198$ | $+1.4811$ | $227.36$ | $0.00764$ | **$0.0044$** | **$0.9956$** |
| `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE` | $-1.4398$ | $+0.6162$ | $128.77$ | $0.00761$ | **$0.0001$** | **$0.9999$** |

*Conclusion:* All candidates have $p > 0.99$. Zero statistical significance over random noise.

---

## 10. BOOTSTRAP & MONTE CARLO DISTRIBUTIONS

1. **Trade IID Bootstrap (1,000 resamples):**
   - Control: Mean return $-9.56\%$, $95\%\text{ CI} = [-19.35\%, +0.75\%]$, Prob Negative $= 96.6\%$, 95th MaxDD $= 19.19\%$.
   - ADX25: Mean return $-4.25\%$, $95\%\text{ CI} = [-11.50\%, +3.26\%]$, Prob Negative $= 86.5\%$, 95th MaxDD $= 11.46\%$.
   - 4H EMA: Mean return $-11.36\%$, $95\%\text{ CI} = [-20.41\%, -2.25\%]$, Prob Negative $= 99.4\%$, 95th MaxDD $= 20.20\%$.
2. **Stationary Block Bootstrap (Politis & Romano 1994, geometric blocks $L=24$):**
   - Control 95% CI: $[-19.82\%, +0.83\%]$
   - ADX25 95% CI: $[-11.48\%, +4.66\%]$
   - 4H EMA 95% CI: $[-21.41\%, -1.20\%]$
3. **Monte Carlo Institutional Stress Suite:**
   - 2x Transaction Costs: Control mean return $-18.36\%$; ADX25 mean return $-8.10\%$; 4H EMA mean return $-19.14\%$.
   - Trade Sequence Shuffling (Worst MaxDD): Control $16.86\%$; ADX25 $10.25\%$; 4H EMA $17.27\%$.
   - Catastrophic Ruin Events (Equity $< 50\%$): 0 observed across all 1,000 runs (Gate 6 Passed).

---

## 11. WALK-FORWARD PARTITIONS & OUT-OF-SAMPLE STABILITY

| Fold | Out-of-Sample Window | Control OOS Return / Sharpe | ADX25 OOS Return / Sharpe | 4H EMA OOS Return / Sharpe |
|---|---|---|---|---|
| **Fold 1** | 2024-10-13 to 2025-03-04 | $-2.62\%$ / $-1.6522$ | **$-2.08\%$ / $-1.8517$** | $-2.34\%$ / $-1.5694$ |
| **Fold 2** | 2024-12-23 to 2025-05-14 | $-2.49\%$ / $-1.7011$ | **$-2.93\%$ / $-3.3872$** | $-2.00\%$ / $-1.4670$ |
| **Fold 3** | 2025-03-04 to 2025-07-24 | $-5.76\%$ / $-4.1513$ | **$-0.86\%$ / $-1.1724$** | $-4.58\%$ / $-3.4399$ |
| **Fold 4** | 2025-05-14 to 2025-10-03 | $-4.31\%$ / $-3.2224$ | **$-0.10\%$ / $-0.1058$** | $-3.57\%$ / $-2.8141$ |
| **Fold 5** | 2025-07-24 to 2025-12-12 | $-1.32\%$ / $-1.0060$ | **$-0.99\%$ / $-1.3022$** | $-0.95\%$ / $-0.7526$ |
| **Mean** | — | **$-3.30\%$ / $-2.3466$** | **$-1.39\%$ / $-1.5639$** | **$-2.69\%$ / $-2.0086$** |

*Finding:* Exactly zero out-of-sample folds across all three candidates produced a positive return.

---

## 12. UNIT TEST EXECUTION & REGRESSION PROOF

```
============================= test session starts =============================
platform win32 -- Python 3.12.1, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\Harshak\OneDrive\Desktop\BTC_ML\BTC_ML_System
collected 10 items

btc_ml_system/tests/test_phase3c_filters.py::test_phase3c_registry_and_metadata PASSED [ 10%]
btc_ml_system/tests/test_phase3c_filters.py::test_adx_filter_blocking_and_permission PASSED [ 20%]
btc_ml_system/tests/test_phase3c_filters.py::test_4h_ema_slope_zero_lookahead_boundary PASSED [ 30%]
btc_ml_system/tests/test_phase3c_filters.py::test_simulation_balance_sheet_identity_and_risk_bounds PASSED [ 40%]
btc_ml_system/tests/test_authentic_data_path_resolution.py::test_explicit_data_dir_takes_precedence PASSED [ 50%]
btc_ml_system/tests/test_authentic_data_path_resolution.py::test_default_resolves_to_authentic_raw PASSED [ 60%]
btc_ml_system/tests/test_authentic_data_path_resolution.py::test_execution_from_another_working_directory PASSED [ 70%]
btc_ml_system/tests/test_authentic_data_path_resolution.py::test_missing_authentic_data_cannot_silently_fallback_to_raw PASSED [ 80%]
btc_ml_system/tests/test_authentic_data_path_resolution.py::test_dataset_validation_checks_expected_symbols PASSED [ 90%]
btc_ml_system/tests/test_authentic_data_path_resolution.py::test_dataset_validation_checks_required_columns_and_nulls PASSED [100%]

============================= 10 passed in 2.77s ==============================
```

---

## 13. DRAWDOWN LIMIT DISCREPANCY AUDIT (10% VS. 20%)

- **The Discrepancy:** Production configurations (`portfolio_paper_v5.yaml`) specify an operational stop-out limit of **$10.0\%$ MaxDD**. In contrast, research Gate 2 was set to **$20.0\%$ MaxDD**.
- **Audit Findings:**
  1. `RS_MOM_DONCHIAN_40_CONTROL` ($13.22\%$ MaxDD) and `RS_MOM_DONCHIAN_40_4H_EMA_SLOPE` ($12.50\%$ MaxDD) breached the $10.0\%$ production limit and would have triggered emergency halts in live trading.
  2. `RS_MOM_DONCHIAN_40_ADX25` was the **ONLY** candidate that stayed within the $10.0\%$ production limit ($7.18\%$ MaxDD).
  3. However, because ADX25 produced a negative return ($-4.30\%$) and failed 5 other acceptance gates, the discrepancy has **zero impact on the final decision**: all candidates remain **REJECTED**.
  - *Full quantitative study is in [`DRAWDOWN_DISCREPANCY_ANALYSIS.md`](file:///c:/Users/Harshak/OneDrive/Desktop/BTC_ML/BTC_ML_System/docs/research/phase_3c/audit_evidence/DRAWDOWN_DISCREPANCY_ANALYSIS.md).*

---

## 14. CONFIRMATION OF FROZEN PRODUCTION & DATABASE INTEGRITY

1. **Production Configurations:** Unaltered. Zero edits to `btc_ml_system/configs/` or any production YAML.
2. **Database Trades:** Exactly 1,334 historical trade records preserved in DuckDB.
3. **Baseline Classification:** The production baseline remains firmly:
   > **`REJECTED — NOT ELIGIBLE FOR PAPER TRADING`**
4. **Broker Isolation:** Zero live or paper orders routed; offline research boundaries maintained.
