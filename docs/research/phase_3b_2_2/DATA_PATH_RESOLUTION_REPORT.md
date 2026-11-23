# DATA PATH RESOLUTION & DATASET VALIDATION REPORT
## Phase 3B.2.2 Infrastructure Hardening: Authentic Data Path Integrity

**Repository:** `BTC_ML_System`  
**Primary Branch:** `fix/phase-3b-2-data-integrity`  
**Modified Module:** `btc_ml_system/src/research/evaluator.py`  
**Test Suite:** `btc_ml_system/tests/test_authentic_data_path_resolution.py`  
**Status:** `VERIFIED & RESOLVED`  

---

### 1. Executive Summary & Problem Diagnosis

During the Phase 3B.2.1 independent verification audit (Audit 1), an infrastructural path-resolution defect was uncovered in `ResearchEvaluator.__init__` around lines 52–65:

```python
# Defective code prior to Phase 3B.2.2
base_dir = Path(__file__).resolve().parent.parent.parent
if data_dir:
  self.data_dir = Path(data_dir)
else:
  auth_dir = base_dir / "data" / "authentic_raw"
  if auth_dir.exists() and any(auth_dir.glob("*.csv")):
    self.data_dir = auth_dir
  elif (base_dir / "data" / "raw").exists():
    self.data_dir = base_dir / "data" / "raw"
  elif (base_dir.parent / "data" / "raw").exists():
    self.data_dir = base_dir.parent / "data" / "raw"
```

**Diagnostic Analysis:**
1. `__file__` resolves to `.../BTC_ML_System/btc_ml_system/src/research/evaluator.py`.
2. Three `.parent` traversals (`parent.parent.parent`) set `base_dir` to `.../BTC_ML_System/btc_ml_system` (the package directory), not `.../BTC_ML_System` (the repository root).
3. The authentic datasets were stored at `.../BTC_ML_System/data/authentic_raw/`. Thus, `base_dir / "data" / "authentic_raw"` evaluated to `False`.
4. Line 61 then checked `(base_dir.parent / "data" / "raw").exists()`, which evaluated to `True` (`.../BTC_ML_System/data/raw`).
5. As a consequence, whenever `ResearchEvaluator()` was instantiated without an explicit `data_dir` argument, it silently fell back to the legacy synthetic clone data in `data/raw`.

---

### 2. Remediation Architecture & Implementation

`btc_ml_system/src/research/evaluator.py` was remediated with narrow scope and zero disruption to production code:

#### 2.1 Precedence & Reliable Root Discovery
1. **Explicit Precedence:** If `data_dir` is passed explicitly, it is resolved to its absolute path and validated. If non-existent, an explicit `FileNotFoundError` is raised immediately.
2. **Reliable Authentic Data Resolution:** When `data_dir` is `None`, the evaluator searches for `data/authentic_raw` containing `.csv` files across:
   - `Path.cwd()` (Current working directory).
   - `evaluator_path.parents[3]` (The repository root: `BTC_ML_System`).
   - `evaluator_path.parent.parent.parent` (Package root: `btc_ml_system`).
   - Upward parent hierarchy traversal.
3. **Strict Prohibition of Silent Fallback:** Legacy `data/raw` is **never** checked or selected by default. If `data/authentic_raw` cannot be located, an explicit `FileNotFoundError` is raised:
   ```
   FileNotFoundError: Authentic data directory 'data/authentic_raw' could not be resolved from working directory (...) or repository structure. Silent fallback to legacy cloned data in 'data/raw' is strictly forbidden.
   ```
4. **Audit Logging:** The resolved absolute path is logged at `INFO` level:
   ```python
   logger.info(f"Resolved authentic data directory: {self.data_dir.resolve()}")
   ```

#### 2.2 Universe Dataset Pre-Simulation Validation
A new validation method `validate_dataset` was added to `ResearchEvaluator`:
- **Expected Universe Validation:** Verifies that all expected assets (`AAPL`, `MSFT`, `NVDA`, `TSLA`, `AMZN`, `BTCUSDT`, `ETHUSDT`) are present in `data_dict`. Missing assets raise `ValueError`.
- **Required Column Validation:** Verifies that every asset's DataFrame contains `["open_time", "open", "high", "low", "close", "volume"]`. Missing columns raise `ValueError`.
- **Zero Null Toleration:** Verifies that OHLCV columns contain zero null/NaN values. Any missing value raises `ValueError`.
- **Simulation Gate:** `run_all_evaluations` executes `self.validate_dataset(data_dict, expected_symbols=target_assets)` prior to running benchmarks or simulations.

---

### 3. Verification Test Suite Execution

A dedicated unit test module was authored and executed:  
`btc_ml_system/tests/test_authentic_data_path_resolution.py`

| Test Case | Description | Result |
| :--- | :--- | :---: |
| `test_explicit_data_dir_takes_precedence` | Verifies explicit `data_dir` takes precedence and non-existent path raises `FileNotFoundError` | **PASSED** |
| `test_default_resolves_to_authentic_raw` | Verifies default `ResearchEvaluator()` resolves to `authentic_raw` and loads 10,871 bars | **PASSED** |
| `test_execution_from_another_working_directory` | Verifies resolution succeeds when `cwd` is changed to temp directory | **PASSED** |
| `test_missing_authentic_data_cannot_silently_fallback_to_raw` | Verifies `FileNotFoundError` is raised and legacy `data/raw` is blocked when authentic data is missing | **PASSED** |
| `test_dataset_validation_checks_expected_symbols` | Verifies `validate_dataset` raises `ValueError` on missing universe symbols | **PASSED** |
| `test_dataset_validation_checks_required_columns_and_nulls` | Verifies `validate_dataset` raises `ValueError` on missing columns or NaN values | **PASSED** |

**Execution Result:** 6 passed in 4.28s. Zero regressions across the full 122-test regression suite.

---

### 4. Conclusion & Status

The authentic data path resolution is hardened, deterministic, and proven to prevent silent legacy fallback under all execution contexts.
