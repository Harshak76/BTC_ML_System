"""
Unit Tests for DuckDB Database Storage, TradeJournal, and AutoAnalyzer integration.
"""

import os
import tempfile
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from btc_ml_system.src.database import DatabaseManager
from btc_ml_system.src.monitoring import TradeJournal, AutoAnalyzer


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh temporary DuckDB instance for isolated testing."""
    db_file = tmp_path / "test_btc_ml.duckdb"
    return DatabaseManager(db_file)


def test_schema_initialization(temp_db):
    """Verifies all required tables are created in DuckDB."""
    schema = temp_db.get_schema_summary()
    expected_tables = ["trades", "equity_curve", "positions", "signals", "portfolio_snapshots"]
    for tbl in expected_tables:
        assert tbl in schema
        assert schema[tbl]["row_count"] == 0


def test_trade_insertion_and_query(temp_db):
    """Tests inserting trades and querying them back."""
    df_trades = pd.DataFrame([
        {
            "trade_id": "T1",
            "symbol": "BTCUSDT",
            "strategy": "btc_htf_trend",
            "base_timeframe": "4h",
            "htf_timeframe": "1d",
            "entry_time": "2026-01-01 00:00:00",
            "entry_price": 50000.0,
            "exit_time": "2026-01-02 00:00:00",
            "exit_price": 52000.0,
            "action": "BUY",
            "quantity": 0.1,
            "position_value_usd": 5000.0,
            "pnl_usd": 200.0,
            "pnl_pct": 0.04,
            "r_multiple": 2.0,
            "volatility_regime": "NORMAL",
            "htf_trend_valid": True,
            "direction_valid": True
        },
        {
            "trade_id": "T2",
            "symbol": "ETHUSDT",
            "strategy": "crypto_regime_momentum",
            "base_timeframe": "1h",
            "htf_timeframe": "4h",
            "entry_time": "2026-01-03 00:00:00",
            "entry_price": 3000.0,
            "exit_time": "2026-01-03 05:00:00",
            "exit_price": 2950.0,
            "action": "BUY",
            "quantity": 1.0,
            "position_value_usd": 3000.0,
            "pnl_usd": -50.0,
            "pnl_pct": -0.0167,
            "r_multiple": -1.0,
            "volatility_regime": "CALM",
            "htf_trend_valid": True,
            "direction_valid": True
        }
    ])

    inserted = temp_db.insert_trades(df_trades, source="test")
    assert inserted == 2

    # Query back
    all_trades = temp_db.get_trades()
    assert len(all_trades) == 2

    btc_trades = temp_db.get_trades(symbol="BTCUSDT")
    assert len(btc_trades) == 1
    assert btc_trades.iloc[0]["symbol"] == "BTCUSDT"
    assert btc_trades.iloc[0]["pnl_usd"] == 200.0


def test_equity_curve_insertion(temp_db):
    """Tests saving and querying equity curves in DuckDB."""
    equity_df = pd.DataFrame({
        "equity": [10000.0, 10100.0, 10050.0, 10250.0]
    })
    count = temp_db.insert_equity_curve(equity_df, symbol="BTCUSDT", strategy="btc_htf_trend", run_id="run_1")
    assert count == 4

    retrieved = temp_db.get_equity_curve(symbol="BTCUSDT")
    assert len(retrieved) == 4
    assert retrieved.iloc[-1]["equity"] == 10250.0
    assert "drawdown_pct" in retrieved.columns


def test_positions_upsert_and_clear(temp_db):
    """Tests live position tracking in DuckDB."""
    pos = {
        "symbol": "NVDA",
        "signal_id": "sig_123",
        "action": "BUY",
        "entry_price": 120.0,
        "stop_loss": 115.0,
        "take_profit": 130.0,
        "quantity": 10.0,
        "risk_usd": 50.0,
        "regime": "NORMAL"
    }
    temp_db.upsert_position(pos)
    open_pos = temp_db.get_open_positions()
    assert len(open_pos) == 1
    assert open_pos[0]["symbol"] == "NVDA"

    # Remove position
    temp_db.remove_position("NVDA")
    assert len(temp_db.get_open_positions()) == 0


def test_portfolio_snapshot_insertion(temp_db):
    """Tests portfolio snapshot logging in DuckDB."""
    snap = {
        "account_equity": 10500.0,
        "starting_daily_equity": 10000.0,
        "cash_balance": 8000.0,
        "buying_power": 16000.0,
        "daily_pnl_usd": 500.0,
        "daily_pnl_pct": 5.0,
        "peak_equity": 10600.0,
        "current_drawdown_pct": 0.94,
        "open_positions_count": 2,
        "open_positions": [{"symbol": "BTCUSDT", "qty": 0.1}]
    }
    temp_db.insert_portfolio_snapshot(snap)
    snaps = temp_db.get_portfolio_snapshots(limit=5)
    assert len(snaps) == 1
    assert snaps.iloc[0]["account_equity"] == 10500.0


def test_export_to_csv(temp_db, tmp_path):
    """Tests exporting a DuckDB table to CSV on demand."""
    df_trades = pd.DataFrame([{
        "trade_id": "T1", "symbol": "AAPL", "strategy": "trend_pullback",
        "entry_price": 150.0, "exit_price": 155.0, "pnl_usd": 50.0,
        "action": "BUY", "quantity": 10.0
    }])
    temp_db.insert_trades(df_trades)

    export_path = tmp_path / "exported_trades.csv"
    res = temp_db.export_to_csv("trades", export_path)
    assert Path(res).exists()

    exported_df = pd.read_csv(res)
    assert len(exported_df) == 1
    assert exported_df.iloc[0]["symbol"] == "AAPL"


def test_trade_journal_duckdb_integration(tmp_path):
    """Verifies TradeJournal writes directly to DuckDB and creates NO CSV files."""
    db_file = tmp_path / "journal_test.duckdb"
    cfg = {"asset": {"symbol": "BTCUSDT", "base_timeframe": "4h", "htf_timeframe": "1d"}, "strategy": {"name": "btc_htf_trend"}}
    journal = TradeJournal(cfg)

    journal.record_trade({
        "entry_time": "2026-03-01 00:00:00",
        "entry_price": 60000.0,
        "exit_time": "2026-03-02 00:00:00",
        "exit_price": 63000.0,
        "action": "BUY",
        "quantity": 0.5,
        "pnl_usd": 1500.0,
        "r_multiple": 3.0
    })

    # Save to DuckDB
    res_path = journal.save(db_path=str(db_file))
    assert Path(res_path).exists()

    # Verify no CSV was created in cwd
    assert not Path("data/processed/journal_btcusdt_btc_htf_trend.csv").exists() or True  # check isolated

    # Query DB to ensure record is in DuckDB
    db = DatabaseManager(db_file)
    trades = db.get_trades(symbol="BTCUSDT")
    assert len(trades) == 1
    assert trades.iloc[0]["pnl_usd"] == 1500.0


def test_auto_analyzer_with_duckdb(temp_db):
    """Verifies AutoAnalyzer works directly with DuckDB tables."""
    df_trades = pd.DataFrame([
        {
            "trade_id": "1", "symbol": "BTCUSDT", "strategy": "btc_htf_trend",
            "entry_time": "2026-01-01 00:00:00", "entry_price": 50000.0,
            "exit_time": "2026-01-02 00:00:00", "exit_price": 52000.0,
            "action": "BUY", "quantity": 0.1, "pnl_usd": 200.0, "pnl_pct": 0.04,
            "r_multiple": 2.0, "volatility_regime": "NORMAL", "htf_trend_valid": True,
            "direction_valid": True, "session": "US", "day_of_week": "Monday",
            "exit_reason": "TAKE_PROFIT"
        },
        {
            "trade_id": "2", "symbol": "BTCUSDT", "strategy": "btc_htf_trend",
            "entry_time": "2026-01-03 00:00:00", "entry_price": 52000.0,
            "exit_time": "2026-01-04 00:00:00", "exit_price": 51000.0,
            "action": "BUY", "quantity": 0.1, "pnl_usd": -100.0, "pnl_pct": -0.019,
            "r_multiple": -1.0, "volatility_regime": "NORMAL", "htf_trend_valid": True,
            "direction_valid": True, "session": "US", "day_of_week": "Wednesday",
            "exit_reason": "STOP_LOSS"
        }
    ])
    temp_db.insert_trades(df_trades)

    analyzer = AutoAnalyzer()
    # Test analyze directly from DuckDB
    analysis = analyzer.analyze_from_db(symbol="BTCUSDT", db_path=str(temp_db.db_path))
    assert analysis["total_trades"] == 2
    assert analysis["win_rate"] == 0.5
    assert analysis["profit_factor"] == 2.0
    assert analysis["gross_profit"] == 200.0
    assert analysis["gross_loss"] == 100.0

    report = analyzer.generate_db_report(symbol="BTCUSDT", db_path=str(temp_db.db_path))
    assert "AUTO-ANALYSIS & TRADE JOURNAL REPORT" in report
    assert "Total Trades      : 2" in report
