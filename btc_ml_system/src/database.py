"""
DuckDB Database Manager Module for btc_ml_system.
Provides institutional-grade, embedded analytical storage for:
- Trade Journal (historical backtests and live executions)
- Paper Trading orders and positions
- Equity curve timeseries
- Portfolio risk and balance snapshots
- Trade signals and regime audits
Includes fast on-demand CSV export functionality.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import datetime
import pandas as pd
import duckdb

logger = logging.getLogger("btc_ml_system.database")


def get_db_path(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolves the canonical database path.
    Precedence:
    1. Explicit custom_path argument
    2. DUCKDB_PATH environment variable
    3. 'data/btc_ml_system.duckdb' relative to project root or current working dir.
    """
    if custom_path:
        if str(custom_path) == ":memory:":
            return ":memory:"
        p = Path(custom_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    env_path = os.environ.get("DUCKDB_PATH")
    if env_path:
        p = Path(env_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # Canonical base is project root
    # __file__ is btc_ml_system/src/database.py
    # src -> btc_ml_system -> BTC_ML_System
    src_dir = Path(__file__).resolve().parent
    btc_ml_system_pkg = src_dir.parent
    project_root = btc_ml_system_pkg.parent

    # If running from inside BTC_ML_System or parent workspace
    target_data_dir = project_root / "data"
    target_data_dir.mkdir(parents=True, exist_ok=True)
    return target_data_dir / "btc_ml_system.duckdb"


class DatabaseManager:
    """
    Institutional DuckDB Storage Manager.
    Manages connections, schema initialization, high-performance batched writes,
    safe migrations, queries, and CSV exports.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None):
        self.db_path = get_db_path(db_path)
        self.init_schema()

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Opens a DuckDB connection to the database file."""
        return duckdb.connect(str(self.db_path))

    def init_schema(self):
        """Initializes all database tables with strict schema definitions."""
        with self.get_connection() as con:
            # 1. TRADES TABLE (Backtest & Paper Trading Journal)
            con.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id VARCHAR,
                    symbol VARCHAR,
                    strategy VARCHAR,
                    base_timeframe VARCHAR,
                    htf_timeframe VARCHAR,
                    entry_idx BIGINT,
                    entry_time TIMESTAMP,
                    entry_price DOUBLE,
                    exit_idx BIGINT,
                    exit_time TIMESTAMP,
                    exit_price DOUBLE,
                    action VARCHAR,
                    quantity DOUBLE,
                    position_value_usd DOUBLE,
                    pnl_usd DOUBLE,
                    pnl_pct DOUBLE,
                    r_multiple DOUBLE,
                    duration_bars INTEGER,
                    duration_hours DOUBLE,
                    volatility_regime VARCHAR,
                    htf_trend_valid BOOLEAN,
                    direction_valid BOOLEAN,
                    risk_pct_used DOUBLE,
                    atr_at_entry DOUBLE,
                    rsi_at_entry DOUBLE,
                    session VARCHAR,
                    day_of_week VARCHAR,
                    hour_of_day INTEGER,
                    entry_reason VARCHAR,
                    exit_reason VARCHAR,
                    source VARCHAR DEFAULT 'backtest',
                    trading_mode VARCHAR DEFAULT 'strict',
                    is_loosened_trade BOOLEAN DEFAULT FALSE,
                    loosening_reason VARCHAR DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Ensure columns exist on legacy tables
            con.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS trading_mode VARCHAR DEFAULT 'strict';")
            con.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS is_loosened_trade BOOLEAN DEFAULT FALSE;")
            con.execute("ALTER TABLE trades ADD COLUMN IF NOT EXISTS loosening_reason VARCHAR DEFAULT '';")

            # 2. EQUITY CURVE TABLE
            con.execute("""
                CREATE TABLE IF NOT EXISTS equity_curve (
                    step_idx BIGINT,
                    timestamp TIMESTAMP,
                    equity DOUBLE,
                    drawdown_pct DOUBLE,
                    symbol VARCHAR,
                    strategy VARCHAR,
                    run_id VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 3. POSITIONS TABLE (Live Open Positions)
            con.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol VARCHAR PRIMARY KEY,
                    signal_id VARCHAR,
                    action VARCHAR,
                    entry_price DOUBLE,
                    stop_loss DOUBLE,
                    take_profit DOUBLE,
                    quantity DOUBLE,
                    risk_usd DOUBLE,
                    regime VARCHAR,
                    opened_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 4. SIGNALS TABLE (Signal Engine Audits)
            con.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id VARCHAR,
                    timestamp TIMESTAMP,
                    symbol VARCHAR,
                    action VARCHAR,
                    close_price DOUBLE,
                    stop_loss DOUBLE,
                    take_profit DOUBLE,
                    quantity DOUBLE,
                    risk_usd DOUBLE,
                    regime VARCHAR,
                    direction_valid BOOLEAN,
                    htf_valid BOOLEAN,
                    allowed_trade BOOLEAN,
                    rejection_reason VARCHAR,
                    strategy VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 5. PORTFOLIO SNAPSHOTS TABLE (Account Health & Daily Summaries)
            con.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    timestamp TIMESTAMP,
                    account_equity DOUBLE,
                    starting_daily_equity DOUBLE,
                    cash_balance DOUBLE,
                    buying_power DOUBLE,
                    daily_pnl_usd DOUBLE,
                    daily_pnl_pct DOUBLE,
                    peak_equity DOUBLE,
                    current_drawdown_pct DOUBLE,
                    open_positions_count INTEGER,
                    positions_json VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        logger.debug(f"DuckDB schema initialized at {self.db_path}")

    # =========================================================================
    # TRADES OPERATIONS
    # =========================================================================

    def insert_trades(self, df: pd.DataFrame, source: str = "backtest") -> int:
        """
        Inserts a DataFrame of trade records into the 'trades' table.
        Automatically casts and validates columns.
        """
        if df.empty:
            return 0

        clean_df = df.copy()

        # Ensure all required columns exist with appropriate defaults
        col_defaults = {
            "trade_id": lambda d: [str(i + 1) for i in range(len(d))],
            "symbol": "UNKNOWN",
            "strategy": "UNKNOWN",
            "base_timeframe": "1h",
            "htf_timeframe": "4h",
            "entry_idx": 0,
            "entry_time": pd.Timestamp.utcnow(),
            "entry_price": 0.0,
            "exit_idx": 0,
            "exit_time": pd.Timestamp.utcnow(),
            "exit_price": 0.0,
            "action": "BUY",
            "quantity": 0.0,
            "position_value_usd": 0.0,
            "pnl_usd": 0.0,
            "pnl_pct": 0.0,
            "r_multiple": 0.0,
            "duration_bars": 0,
            "duration_hours": 0.0,
            "volatility_regime": "NORMAL",
            "htf_trend_valid": True,
            "direction_valid": True,
            "risk_pct_used": 0.005,
            "atr_at_entry": 0.0,
            "rsi_at_entry": 0.0,
            "session": "UNKNOWN",
            "day_of_week": "UNKNOWN",
            "hour_of_day": 0,
            "entry_reason": "Approved",
            "exit_reason": "EXIT",
            "trading_mode": "strict",
            "is_loosened_trade": False,
            "loosening_reason": ""
        }

        for col, default_val in col_defaults.items():
            if col not in clean_df.columns:
                if callable(default_val):
                    clean_df[col] = default_val(clean_df)
                else:
                    clean_df[col] = default_val

        # Ensure datetime parsing with mixed format support
        clean_df["entry_time"] = pd.to_datetime(clean_df["entry_time"], format="mixed")
        clean_df["exit_time"] = pd.to_datetime(clean_df["exit_time"], format="mixed")
        clean_df["trade_id"] = clean_df["trade_id"].astype(str)
        clean_df["source"] = source
        clean_df["created_at"] = pd.Timestamp.utcnow()

        # Select columns in exact order
        cols = [
            "trade_id", "symbol", "strategy", "base_timeframe", "htf_timeframe",
            "entry_idx", "entry_time", "entry_price", "exit_idx", "exit_time", "exit_price",
            "action", "quantity", "position_value_usd", "pnl_usd", "pnl_pct", "r_multiple",
            "duration_bars", "duration_hours", "volatility_regime", "htf_trend_valid",
            "direction_valid", "risk_pct_used", "atr_at_entry", "rsi_at_entry",
            "session", "day_of_week", "hour_of_day", "entry_reason", "exit_reason",
            "source", "trading_mode", "is_loosened_trade", "loosening_reason", "created_at"
        ]
        clean_df = clean_df[cols]

        with self.get_connection() as con:
            con.register("df_trades_insert", clean_df)
            con.execute("INSERT INTO trades SELECT * FROM df_trades_insert")

        count = len(clean_df)
        logger.info(f"Inserted {count} trades into DuckDB trades table (source={source}).")
        return count

    def insert_trade_record(self, record: Dict[str, Any], source: str = "paper_trade"):
        """Inserts a single trade record dict into DuckDB."""
        df = pd.DataFrame([record])
        self.insert_trades(df, source=source)

    def get_trades(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[str] = None,
        source: Optional[str] = None
    ) -> pd.DataFrame:
        """Queries trades from DuckDB with optional filtering."""
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)
        if source:
            query += " AND source = ?"
            params.append(source)
        query += " ORDER BY entry_time ASC"

        with self.get_connection() as con:
            df = con.execute(query, params).df()
        return df

    # =========================================================================
    # EQUITY CURVE OPERATIONS
    # =========================================================================

    def insert_equity_curve(
        self,
        equity_df: pd.DataFrame,
        symbol: str = "",
        strategy: str = "",
        run_id: str = ""
    ) -> int:
        """Inserts backtest or portfolio equity curve into DuckDB."""
        if equity_df.empty:
            return 0

        df = pd.DataFrame()
        if "step_idx" in equity_df.columns:
            df["step_idx"] = equity_df["step_idx"]
        else:
            df["step_idx"] = list(range(len(equity_df)))

        if "timestamp" in equity_df.columns:
            df["timestamp"] = pd.to_datetime(equity_df["timestamp"])
        else:
            df["timestamp"] = pd.Timestamp.utcnow()

        df["equity"] = equity_df["equity"].astype(float)

        # Calculate drawdown if not provided
        if "drawdown_pct" in equity_df.columns:
            df["drawdown_pct"] = equity_df["drawdown_pct"].astype(float)
        else:
            cummax = df["equity"].cummax()
            df["drawdown_pct"] = ((cummax - df["equity"]) / cummax).fillna(0.0)

        df["symbol"] = symbol
        df["strategy"] = strategy
        df["run_id"] = run_id or f"run_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        df["created_at"] = pd.Timestamp.utcnow()

        with self.get_connection() as con:
            con.register("df_equity_insert", df)
            con.execute("INSERT INTO equity_curve SELECT * FROM df_equity_insert")

        return len(df)

    def get_equity_curve(self, run_id: Optional[str] = None, symbol: Optional[str] = None) -> pd.DataFrame:
        """Queries equity curve records from DuckDB."""
        query = "SELECT * FROM equity_curve WHERE 1=1"
        params = []
        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        query += " ORDER BY step_idx ASC"

        with self.get_connection() as con:
            return con.execute(query, params).df()

    # =========================================================================
    # POSITIONS OPERATIONS
    # =========================================================================

    def upsert_position(self, pos: Dict[str, Any]):
        """Upserts a live paper position."""
        sym = pos["symbol"]
        with self.get_connection() as con:
            con.execute("""
                DELETE FROM positions WHERE symbol = ?;
            """, [sym])
            con.execute("""
                INSERT INTO positions (
                    symbol, signal_id, action, entry_price, stop_loss, take_profit,
                    quantity, risk_usd, regime, opened_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, [
                sym,
                pos.get("signal_id", ""),
                pos.get("action", "BUY"),
                float(pos.get("entry_price", pos.get("close_price", 0.0))),
                float(pos.get("stop_loss", 0.0)),
                float(pos.get("take_profit", 0.0)),
                float(pos.get("quantity", 0.0)),
                float(pos.get("risk_usd", 0.0)),
                str(pos.get("regime", "NORMAL")),
                pd.to_datetime(pos.get("opened_at", datetime.datetime.utcnow()))
            ])

    def remove_position(self, symbol: str):
        """Removes a closed position from positions table."""
        with self.get_connection() as con:
            con.execute("DELETE FROM positions WHERE symbol = ?", [symbol])

    def clear_positions(self):
        """Clears all positions (e.g., kill-switch / emergency flatten)."""
        with self.get_connection() as con:
            con.execute("DELETE FROM positions;")

    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Retrieves list of currently active open positions."""
        with self.get_connection() as con:
            df = con.execute("SELECT * FROM positions").df()
        return df.to_dict(orient="records")

    # =========================================================================
    # SIGNALS OPERATIONS
    # =========================================================================

    def insert_signal(self, sig: Dict[str, Any]):
        """Logs a strategic signal evaluation into DuckDB."""
        with self.get_connection() as con:
            con.execute("""
                INSERT INTO signals (
                    signal_id, timestamp, symbol, action, close_price, stop_loss,
                    take_profit, quantity, risk_usd, regime, direction_valid,
                    htf_valid, allowed_trade, rejection_reason, strategy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, [
                str(sig.get("signal_id", "")),
                pd.to_datetime(sig.get("timestamp", datetime.datetime.utcnow())),
                str(sig.get("symbol", "")),
                str(sig.get("action", "HOLD")),
                float(sig.get("close_price", sig.get("entry_price", 0.0))),
                float(sig.get("stop_loss", 0.0)),
                float(sig.get("take_profit", 0.0)),
                float(sig.get("quantity", 0.0)),
                float(sig.get("risk_usd", 0.0)),
                str(sig.get("regime", sig.get("volatility_regime", "NORMAL"))),
                bool(sig.get("direction_valid", True)),
                bool(sig.get("htf_valid", True)),
                bool(sig.get("allowed_trade", False)),
                str(sig.get("rejection_reason", "None")),
                str(sig.get("strategy", ""))
            ])

    # =========================================================================
    # PORTFOLIO SNAPSHOTS
    # =========================================================================

    def insert_portfolio_snapshot(self, snap: Dict[str, Any]):
        """Records an account state snapshot into DuckDB."""
        positions_raw = snap.get("open_positions", [])
        pos_json = json.dumps(positions_raw) if isinstance(positions_raw, (list, dict)) else str(positions_raw)

        with self.get_connection() as con:
            con.execute("""
                INSERT INTO portfolio_snapshots (
                    timestamp, account_equity, starting_daily_equity, cash_balance,
                    buying_power, daily_pnl_usd, daily_pnl_pct, peak_equity,
                    current_drawdown_pct, open_positions_count, positions_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, [
                pd.to_datetime(snap.get("timestamp", datetime.datetime.utcnow())),
                float(snap.get("account_equity", 0.0)),
                float(snap.get("starting_daily_equity", 0.0)),
                float(snap.get("cash_balance", 0.0)),
                float(snap.get("buying_power", 0.0)),
                float(snap.get("daily_pnl_usd", 0.0)),
                float(snap.get("daily_pnl_pct", 0.0)),
                float(snap.get("peak_equity", 0.0)),
                float(snap.get("current_drawdown_pct", 0.0)),
                int(snap.get("open_positions_count", 0)),
                pos_json
            ])

    def get_portfolio_snapshots(self, limit: int = 100) -> pd.DataFrame:
        """Retrieves recent portfolio snapshots."""
        with self.get_connection() as con:
            return con.execute(f"SELECT * FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT {limit}").df()

    # =========================================================================
    # UTILITIES & CSV EXPORT
    # =========================================================================

    def export_to_csv(self, table_name: str, output_csv_path: Union[str, Path]) -> str:
        """
        Exports any DuckDB table directly to a CSV file.
        Provides a clean, instant export mechanism on demand.
        """
        valid_tables = ["trades", "equity_curve", "positions", "signals", "portfolio_snapshots"]
        if table_name not in valid_tables:
            raise ValueError(f"Table '{table_name}' is not a recognized system table. Allowed: {valid_tables}")

        out_path = Path(output_csv_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as con:
            con.execute(f"COPY {table_name} TO '{str(out_path).replace(os.sep, '/')}' (HEADER, DELIMITER ',');")

        logger.info(f"Successfully exported table '{table_name}' to {out_path}")
        return str(out_path)

    def get_schema_summary(self) -> Dict[str, Any]:
        """Returns row counts and column schemas for all managed tables."""
        summary = {}
        tables = ["trades", "equity_curve", "positions", "signals", "portfolio_snapshots"]
        with self.get_connection() as con:
            for t in tables:
                count = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                cols = con.execute(f"PRAGMA table_info({t})").fetchall()
                col_list = [{"name": c[1], "type": c[2]} for c in cols]
                summary[t] = {
                    "row_count": count,
                    "columns": col_list
                }
        return summary


def main():
    """CLI utility for database inspection and export."""
    import argparse
    parser = argparse.ArgumentParser(description="DuckDB Database Management CLI for btc-ml-system")
    parser.add_argument("--summary", action="store_true", help="Print schema and table row counts")
    parser.add_argument("--export", nargs=2, metavar=("TABLE", "CSV_PATH"), help="Export a table to CSV")
    parser.add_argument("--db-path", type=str, default=None, help="Custom database path")

    args = parser.parse_args()
    db = DatabaseManager(args.db_path)

    if args.export:
        tbl, path = args.export
        res = db.export_to_csv(tbl, path)
        print(f"Exported table '{tbl}' to {res}")
        return

    # Default to summary
    print("=" * 80)
    print(f"   BTC-ML-SYSTEM DUCKDB DATABASE: {db.db_path}")
    print("=" * 80)
    schema = db.get_schema_summary()
    for tbl, info in schema.items():
        print(f"\nTable: {tbl} (Total Rows: {info['row_count']})")
        col_names = [f"{c['name']} ({c['type']})" for c in info['columns']]
        print(f"  Columns: {', '.join(col_names)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
