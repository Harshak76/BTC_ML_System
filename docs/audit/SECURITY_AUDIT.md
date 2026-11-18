# BTC-ML SYSTEM V2 — SECURITY & CREDENTIAL AUDIT
**Phase 0: Secrets Management, Repository Hygiene & Execution Boundaries**  
**Date:** November 18, 2026  
**Auditors:** Site Reliability Engineer, Senior Python Software Architect  

---

## 1. Security Architecture & Threat Model

The security audit evaluates four primary risk vectors:
1. **Credential Exposure:** Risk of API keys, broker tokens, or private secrets leaking into version control or public repositories.
2. **Execution Boundary Integrity:** Ensuring strict isolation between paper trading endpoints and live-money broker endpoints.
3. **Repository Hygiene:** Verification that temporary databases, binary files, environment definitions, and log outputs are prevented from committing to git.
4. **Environment Isolation:** Network isolation, sandboxing rules, and execution boundary compliance.

---

## 2. Secrets Management & Exposure Matrix

| Component | File Path | Credential Mechanism | Current Status | Vulnerability Level |
| :--- | :--- | :--- | :--- | :---: |
| **Portfolio Config** | `configs/portfolio_paper_v5.yaml` | Plaintext YAML values | Exposed (`PKOJ...MLNN`) | **CRITICAL** |
| **Executor Fallback**| `src/alpaca_executor.py` | Hardcoded Python string | Exposed in source | **CRITICAL** |
| **Data Provider Fallback**| `src/data_provider.py` | Hardcoded Python string | Exposed in source | **CRITICAL** |
| **Environment Variable**| `ALPACA_API_KEY` | OS environment | Supported via resolution | Compliant |
| **Git Ignore Profile** | `.gitignore` | Exclusion patterns | Missing `.env`, `*.duckdb` | **HIGH** |
| **Broker Endpoint** | `configs/portfolio_paper_v5.yaml` | `paper-api.alpaca.markets` | Paper trading endpoint | Compliant (Isolated) |

---

## 3. Security Findings

### Finding SEC-001: Plaintext Alpaca API Credentials in Configuration and Source Files
- **Severity:** CRITICAL
- **Exact File Path:**
  1. `BTC_ML_System/btc_ml_system/configs/portfolio_paper_v5.yaml` (lines 24-25)
  2. `BTC_ML_System/btc_ml_system/src/alpaca_executor.py` (lines 28-29)
  3. `BTC_ML_System/btc_ml_system/src/data_provider.py` (lines 32-33)
- **Function or Class:** `AlpacaExecutor.__init__`, `DataProvider.__init__`, and YAML config file
- **Existing Behavior:** The Alpaca Paper Trading API key (`PKOJ...MLNN`) and Secret Key (`ACKU...GW8k`) are stored in plaintext in tracked configuration files and embedded as hardcoded string fallbacks in production Python source code.
- **Expected Behavior:** No secrets should ever be embedded in code or configuration files. Credentials must be loaded strictly from environment variables (`ALPACA_API_KEY`, `ALPACA_SECRET_KEY`) or an untracked local `.env` file via `python-dotenv`. If credentials are not supplied, the system must either enter `dry_run` mode or raise an explicit `ConfigurationError`.
- **Identified Gap:** The repository was previously pushed to GitHub with these credentials present. Even though this is an Alpaca Paper Trading account (no real funds at risk), having exposed keys violates all institutional security standards and creates automated credential scanner alerts.
- **Recommended Fix:**
  1. In Phase 1, strip all hardcoded fallback keys from `alpaca_executor.py` and `data_provider.py`.
  2. Remove plaintext keys from `portfolio_paper_v5.yaml` and replace them with placeholder references (`"${ALPACA_API_KEY}"`).
  3. Create a template file `.env.example`.
  4. Regenerate / rotate the Alpaca Paper API key pair on the Alpaca Dashboard to revoke the exposed credentials.
- **Required Test:** Add an automated unit test that parses all YAML and Python files in the repository to assert that no string matching the Alpaca API key pattern is committed.

---

### Finding SEC-002: Missing `.env` and `*.duckdb` in `.gitignore`
- **Severity:** HIGH
- **Exact File Path:** `BTC_ML_System/.gitignore`
- **Function or Class:** Git exclusion rules
- **Existing Behavior:** The repository `.gitignore` currently lists:
  `*.duckdb.wal`
  `data/raw/*.csv`
  However, it **omits**:
  - `.env` and `.env.*`
  - `*.duckdb` (the database file itself, which is currently tracked at `data/btc_ml_system.duckdb` and committed to git).
- **Expected Behavior:** Environment configuration files containing developer secrets (`.env`) and local binary database files (`*.duckdb`) must be excluded from version control.
- **Identified Gap:** Creates continuous risk of committing local `.env` files and bloats the git repository history with multi-megabyte binary database updates on every run.
- **Recommended Fix:**
  1. Add `.env`, `.env.*`, and `*.duckdb` to `.gitignore`.
  2. Untrack `data/btc_ml_system.duckdb` from git using `git rm --cached` while preserving the local database on disk.
- **Required Test:** Run `git status` after creating a dummy `.env` file and verify it is completely untracked.

---

### Finding SEC-003: Lack of Mutual Exclusion Guard for Live-Money Alpaca Endpoints
- **Severity:** MEDIUM
- **Exact File Path:** `BTC_ML_System/btc_ml_system/src/alpaca_executor.py`
- **Function or Class:** `AlpacaExecutor.__init__` (line 22)
- **Existing Behavior:** The endpoint is resolved from config:
  `self.endpoint = self.alp_cfg.get("endpoint", "https://paper-api.alpaca.markets/v2")`
  There is no safety assertion preventing an operator from accidentally pointing `endpoint` to the live-money URL (`https://api.alpaca.markets/v2`).
- **Expected Behavior:** In a research and paper-trading platform, an explicit hard safety guard must exist that forcibly aborts execution if a live-money endpoint is configured unless an explicit `--live-trading-confirmed` command-line flag is passed.
- **Identified Gap:** Accidental misconfiguration could route paper trades to a funded live account.
- **Recommended Fix:** Add an explicit assertion in `AlpacaExecutor`:
  ```python
  if "paper" not in self.endpoint.lower() and not self.config.get("allow_live_money_trading", False):
      raise RuntimeError("FATAL: Live trading endpoint detected but live trading is strictly disabled!")
  ```
- **Required Test:** Test initializing `AlpacaExecutor` with `https://api.alpaca.markets/v2`, verifying that `RuntimeError` is immediately raised.
