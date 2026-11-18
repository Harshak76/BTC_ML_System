# BTC-ML SYSTEM V2 — PHASE 1 SECURITY REPORT
## Credential Sanitization, Secret Management & Broker Isolation

**Date:** 2026-11-18  
**Auditor:** Quantitative Security Engineer  
**Classification:** HIGH / CONFIDENTIAL (All Raw Keys Sanitized)  
**Status:** All Security Deficiencies Remediated Locally  

---

### 1. Security Remediation Overview

During Phase 0, two critical security vulnerabilities were discovered:
1. **SEC-001:** Alpaca Paper Trading API credentials (Key ID and Secret Key) were hardcoded in multiple Python source files (`alpaca_executor.py`, `data_provider.py`) as fallback strings and written in plaintext inside tracked YAML files (`btc_ml_system/configs/portfolio_paper_v5.yaml`).
2. **SEC-002:** The repository lacked `.env` exclusions in `.gitignore`, and the live DuckDB binary file (`data/btc_ml_system.duckdb`) was tracked in the Git index.

Both issues have been remediated on the `phase-1-security-data-execution` branch.

---

### 2. Implementation Specifics

#### 2.1 Complete Credential Removal
- **Source Code Sanitization:** Removed all hardcoded credentials from `alpaca_executor.py` and `data_provider.py`. Both classes now initialize credentials via `python-dotenv` and standard `os.environ.get("ALPACA_API_KEY")` and `os.environ.get("ALPACA_SECRET_KEY")`.
- **Config Sanitization:** Cleared `api_key: ""` and `secret_key: ""` in `portfolio_paper_v5.yaml`. The configuration now documents that credentials must be supplied via environment variables.
- **Automated Secret Scanning:** Added `test_security.py::test_no_hardcoded_credentials_in_source_and_configs`, which scans all `.py` and `.yaml` files in the repository during automated test runs.

#### 2.2 Git Hygiene & Repository Protection
- **`.gitignore` Rules Updated:** Added:
  ```gitignore
  # Environment Variables
  .env
  .env.*
  !.env.example

  # DuckDB Databases & Backups
  *.duckdb
  *.duckdb.wal
  *.duckdb.bak*
  data/*.duckdb
  data/*.duckdb.bak*
  ```
- **`.env.example` Created:** An untracked `.env.example` was created with non-sensitive template placeholders:
  ```bash
  ALPACA_API_KEY=YOUR_ALPACA_API_KEY_HERE
  ALPACA_SECRET_KEY=YOUR_ALPACA_SECRET_KEY_HERE
  ALPACA_ENDPOINT=https://paper-api.alpaca.markets/v2
  ALPACA_DATA_ENDPOINT=https://data.alpaca.markets
  DUCKDB_PATH=data/btc_ml_system.duckdb
  TRADING_MODE=strict
  ALLOW_LIVE_MONEY_TRADING=false
  ```
- **Database Untracking:** Removed `data/btc_ml_system.duckdb` from Git tracking via `git rm --cached data/btc_ml_system.duckdb`. The actual file and all 1,334 historical trade records remain intact on local disk.

#### 2.3 Live Money Safety Guard (SEC-003)
To ensure the system can never accidentally execute real-money orders, an explicit guard was integrated into `AlpacaExecutor.__init__`:
```python
allow_live_trading = (
    os.environ.get("ALLOW_LIVE_MONEY_TRADING", "false").lower() == "true" or
    bool(config.get("allow_live_money_trading", False))
)
if "paper" not in self.endpoint.lower() and not allow_live_trading:
    raise RuntimeError(
        f"CRITICAL SAFETY VIOLATION: Endpoint '{self.endpoint}' does not contain 'paper' "
        "and live-money trading is strictly disabled. Aborting immediately to prevent accidental real-money execution."
    )
```

---

### 3. Required Manual Actions: Key Rotation Notice

> [!WARNING]
> **IMMEDIATE ACTION REQUIRED BY OPERATOR**  
> Because Alpaca API credentials were previously committed to the Git repository in earlier commits on `main`, deleting them from current code does **NOT** revoke them if Git history is pushed to a remote repository.

The user/operator must perform the following manual steps on the Alpaca Dashboard:
1. Log into your Alpaca account: [https://app.alpaca.markets/](https://app.alpaca.markets/).
2. Navigate to **Paper Trading** dashboard -> **API Keys**.
3. Click **Regenerate Key** or **Delete Key** for the compromised key ID.
4. Generate a fresh API Key ID and Secret Key.
5. Paste the new key pair into your local, untracked `.env` file:
   ```bash
   ALPACA_API_KEY=<new_key_id>
   ALPACA_SECRET_KEY=<new_secret_key>
   ```
6. Verify your `.env` remains excluded from Git by running `git status`.

---

### 4. Git History Audit

A forensic scan of the local commit history confirms:
- Commit `32b21762d441f2447788d255c37ea1667ed29c58` on `main` contained plaintext keys in `portfolio_paper_v5.yaml` and `alpaca_executor.py`.
- No credentials have been exposed in logs, reports, or test fixtures.
- Destructive Git history rewriting (`git filter-repo` or `git filter-branch`) was **NOT** performed in Phase 1 to preserve repository stability, in accordance with the preservation rules. Once new keys are generated on Alpaca, old keys are cryptographically invalid and harmless.
