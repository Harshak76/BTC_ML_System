"""
Migration Script: Migrate Legacy CSV Trade Journals to DuckDB.
Safely extracts historical trade journals from data/processed and reports directories,
deduplicates rows, validates integrity, and writes them into btc_ml_system.duckdb.
"""

import os
import sys
import glob
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
import pandas as pd

from btc_ml_system.src.database import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("btc_ml_system.migration")


def find_journal_csv_files() -> List[Path]:
    """Locates all legacy journal CSV files across project and workspace directories."""
    patterns = [
        "data/processed/journal_*.csv",
        "reports/journal_*.csv",
        "BTC_ML_System/data/processed/journal_*.csv",
        "BTC_ML_System/reports/journal_*.csv",
        "**/*paper_trade*.csv"
    ]
    found_files = []
    seen = set()
    for pat in patterns:
        for f in glob.glob(pat, recursive=True):
            resolved = Path(f).resolve()
            if resolved not in seen and resolved.is_file():
                seen.add(resolved)
                found_files.append(resolved)
    return sorted(found_files)


def run_migration(db: DatabaseManager, dry_run: bool = False) -> Dict[str, Any]:
    """
    Reads all legacy journal CSV files, deduplicates across directories,
    and loads them cleanly into DuckDB.
    """
    csv_files = find_journal_csv_files()
    if not csv_files:
        logger.warning("No legacy CSV journal files found to migrate.")
        return {"migrated_trades": 0, "files_scanned": 0, "files": []}

    logger.info(f"Discovered {len(csv_files)} legacy CSV files for migration:")
    for f in csv_files:
        logger.info(f"  • {f}")

    dfs = []
    file_trade_counts = {}
    for f in csv_files:
        try:
            df = pd.read_csv(f)
            file_trade_counts[str(f)] = len(df)
            if not df.empty:
                df["_origin_file"] = str(f)
                dfs.append(df)
        except Exception as e:
            logger.error(f"Error reading {f}: {e}")

    if not dfs:
        logger.warning("All discovered CSV files were empty.")
        return {"migrated_trades": 0, "files_scanned": len(csv_files), "files": [str(f) for f in csv_files]}

    combined = pd.concat(dfs, ignore_index=True)
    total_raw_rows = len(combined)

    # Deduplicate based on trade uniqueness
    dedup_cols = ["symbol", "strategy", "entry_time", "exit_price"]
    deduped = combined.drop_duplicates(subset=dedup_cols).copy()
    total_unique_trades = len(deduped)

    logger.info(f"Raw rows read across all files: {total_raw_rows}")
    logger.info(f"Unique trades after deduplication: {total_unique_trades}")

    # Remove temporary origin column before inserting
    clean_trades_df = deduped.drop(columns=["_origin_file"], errors="ignore")

    symbol_breakdown = clean_trades_df["symbol"].value_counts().to_dict()
    logger.info("Unique Trades Breakdown by Symbol:")
    for sym, cnt in symbol_breakdown.items():
        logger.info(f"  -> {sym:<8}: {cnt} trades")

    if not dry_run:
        # Check current count in DB
        with db.get_connection() as con:
            existing_count = con.execute("SELECT count(*) FROM trades WHERE source = 'migrated'").fetchone()[0]
            if existing_count > 0:
                logger.info(f"Cleaning previously migrated {existing_count} trades before fresh migration...")
                con.execute("DELETE FROM trades WHERE source = 'migrated';")

        inserted = db.insert_trades(clean_trades_df, source="migrated")
        logger.info(f"Successfully migrated {inserted} trades into DuckDB!")
    else:
        logger.info("Dry-run mode: no database writes performed.")
        inserted = 0

    return {
        "migrated_trades": inserted if not dry_run else total_unique_trades,
        "total_raw_rows": total_raw_rows,
        "files_scanned": len(csv_files),
        "files": [str(f) for f in csv_files],
        "symbol_breakdown": symbol_breakdown
    }


def verify_migration(db: DatabaseManager) -> bool:
    """Verifies that migrated data in DuckDB matches expectations."""
    with db.get_connection() as con:
        total_in_db = con.execute("SELECT count(*) FROM trades").fetchone()[0]
        symbols = con.execute("SELECT symbol, count(*) FROM trades GROUP BY symbol ORDER BY symbol").fetchall()
        pnl_stats = con.execute("SELECT sum(pnl_usd), avg(pnl_pct), avg(win_rate) FROM (SELECT pnl_usd, pnl_pct, CASE WHEN pnl_usd > 0 THEN 1.0 ELSE 0.0 END as win_rate FROM trades)").fetchone()

    logger.info("=" * 70)
    logger.info(f"DUCKDB MIGRATION VERIFICATION: {db.db_path}")
    logger.info(f"Total Trades in Database : {total_in_db}")
    logger.info(f"Total Net PnL ($)        : ${pnl_stats[0]:,.2f}")
    logger.info(f"Average Win Rate         : {pnl_stats[2]:.2%}")
    logger.info("Breakdown by Symbol in DuckDB:")
    for sym, cnt in symbols:
        logger.info(f"  - {sym:<8} : {cnt} trades")
    logger.info("=" * 70)

    # Check that core symbols are present
    found_syms = set(s[0] for s in symbols)
    expected_syms = {"AAPL", "AMZN", "MSFT", "NVDA", "TSLA", "BTCUSDT", "ETHUSDT"}
    if not expected_syms.issubset(found_syms):
        logger.error(f"Missing symbols in migrated database! Found: {found_syms}, Expected: {expected_syms}")
        return False

    return total_in_db >= 690


if __name__ == "__main__":
    db = DatabaseManager()
    res = run_migration(db)
    ok = verify_migration(db)
    if ok:
        print("\n>>> MIGRATION SUCCESSFUL & VERIFIED <<<")
    else:
        print("\n>>> MIGRATION VERIFICATION FAILED <<<")
        sys.exit(1)
