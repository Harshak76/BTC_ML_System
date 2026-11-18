"""
Tests for SEC-001 and SEC-002: Security, Credential Hygiene, and Git Exclusions.
Validates:
- No hardcoded Alpaca API keys or secrets in source code and tracked configs
- .gitignore excludes .env files and *.duckdb database files
- DuckDB historical database is preserved intact on disk and queryable
"""

import os
import re
import subprocess
from pathlib import Path
import duckdb


def test_no_hardcoded_credentials_in_source_and_configs():
    """SEC-001: Scans tracked Python and YAML files to verify no raw Alpaca API keys are hardcoded."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    src_dir = repo_root / "btc_ml_system"

    # Pattern for potential Alpaca key formats (PK..., AK..., etc. 20+ chars)
    # Exclude placeholders like MOCK_KEY, YOUR_API_KEY, etc.
    secret_pattern = re.compile(r'["\'](PK[A-Z0-9]{18,30}|AK[A-Z0-9]{18,30})["\']')

    suspicious_files = []
    for ext in ["*.py", "*.yaml", "*.yml"]:
        for file_path in src_dir.rglob(ext):
            if "tests" in file_path.parts:
                continue
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                matches = secret_pattern.findall(content)
                if matches:
                    suspicious_files.append((str(file_path), len(matches)))

    assert len(suspicious_files) == 0, f"Found hardcoded API keys in tracked source files: {suspicious_files}"


def test_gitignore_exclusions():
    """SEC-002: Verifies .gitignore properly excludes .env and duckdb database files."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    gitignore_path = repo_root / ".gitignore"

    assert gitignore_path.exists(), ".gitignore must exist in repository root"
    content = gitignore_path.read_text(encoding="utf-8")

    assert ".env" in content, ".gitignore must exclude .env"
    assert "*.duckdb" in content, ".gitignore must exclude *.duckdb"


def test_duckdb_database_preserved_and_intact():
    """SEC-002: Verifies DuckDB file exists on disk with historical records intact."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    db_path = repo_root / "data" / "btc_ml_system.duckdb"

    assert db_path.exists(), f"Historical DuckDB file must exist at: {db_path}"

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        assert "trades" in tables, "Table 'trades' must exist in database"
        assert "equity_curve" in tables, "Table 'equity_curve' must exist in database"

        trade_count = con.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        assert trade_count >= 1300, f"Historical trades must be preserved (expected >= 1300, got: {trade_count})"
    finally:
        con.close()
