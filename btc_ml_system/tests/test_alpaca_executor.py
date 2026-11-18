"""
Unit and Mock Integration Tests for AlpacaExecutor.
Validates:
- EXE-001: Client Order ID sanitization and formatting
- EXE-002: Order lifecycle polling, fill verification, partial fills, rejections
- EXE-003: Fractional equity order time_in_force enforcement
- SEC-001 / SEC-003: Paper-only isolation and live money guardrail
"""

import os
import re
import pytest
from unittest.mock import patch, MagicMock
from btc_ml_system.src.alpaca_executor import AlpacaExecutor


@pytest.fixture
def base_config():
    return {
        "alpaca": {
            "endpoint": "https://paper-api.alpaca.markets/v2",
            "api_key": "MOCK_KEY_ID_1234",
            "secret_key": "MOCK_SECRET_KEY_5678",
            "dry_run": False
        },
        "portfolio": {
            "risk_limits": {
                "max_position_value_usd": 2500.0,
                "max_position_equity_pct": 0.30
            }
        }
    }


def test_client_order_id_sanitization():
    """EXE-001: Verifies client_order_id formatting matches ^[a-zA-Z0-9_-]+$."""
    raw_sig_ids = [
        "BTCUSDT_2026-11-18 16:00:00+00:00",
        "AAPL_2026-11-18 09:30:00-05:00",
        "TSLA_2026/11/18:14.30.00",
        "ETHUSDT_special!@#$%^&*()_+bar"
    ]
    alpaca_regex = re.compile(r"^[a-zA-Z0-9_-]+$")

    for raw_id in raw_sig_ids:
        sanitized = AlpacaExecutor.sanitize_client_order_id(raw_id)
        assert alpaca_regex.match(sanitized), f"Failed regex for: {sanitized}"
        assert len(sanitized) <= 64
        assert " " not in sanitized
        assert ":" not in sanitized
        assert "+" not in sanitized


def test_fractional_equity_order_time_in_force(base_config):
    """EXE-003: US equities with fractional shares must use time_in_force='day'."""
    executor = AlpacaExecutor(base_config)

    with patch.object(executor, "get_account_equity", return_value=10000.0), \
         patch("requests.post") as mock_post, \
         patch.object(executor, "poll_order_fill", return_value={"status": "filled", "filled_qty": 0.45, "filled_avg_price": 220.0}):

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "mock_order_1", "status": "accepted"}
        mock_post.return_value = mock_resp

        # 1. Fractional stock order (0.45 AAPL) -> Should auto-switch to "day"
        executor.place_paper_order(
            signal_id="sig_frac_aapl",
            symbol="AAPL",
            qty=0.45,
            side="buy",
            time_in_force="gtc",
            estimated_price=220.0,
            verify_fill=False
        )
        payload = mock_post.call_args[1]["json"]
        assert payload["time_in_force"] == "day"
        assert payload["qty"] == "0.45"

        # 2. Whole share stock order (5 MSFT) -> Keeps requested time_in_force
        executor.place_paper_order(
            signal_id="sig_whole_msft",
            symbol="MSFT",
            qty=5.0,
            side="buy",
            time_in_force="gtc",
            estimated_price=400.0,
            verify_fill=False
        )
        payload_msft = mock_post.call_args[1]["json"]
        assert payload_msft["time_in_force"] == "gtc"
        assert payload_msft["qty"] == "5"

        # 3. Fractional crypto order (0.0154 BTC) -> Keeps requested time_in_force
        executor.place_paper_order(
            signal_id="sig_frac_btc",
            symbol="BTCUSDT",
            qty=0.0154,
            side="buy",
            time_in_force="gtc",
            estimated_price=90000.0,
            verify_fill=False
        )
        payload_btc = mock_post.call_args[1]["json"]
        assert payload_btc["time_in_force"] == "gtc"
        assert payload_btc["qty"] == "0.0154"


def test_order_fill_verification_lifecycle(base_config):
    """EXE-002: Bounded polling verifies filled, partially filled, and rejected orders."""
    executor = AlpacaExecutor(base_config)

    # A. Filled order
    with patch.object(executor, "get_order_by_id") as mock_get:
        mock_get.return_value = {
            "id": "ord_123",
            "status": "filled",
            "symbol": "BTC/USD",
            "side": "buy",
            "filled_qty": "0.05",
            "filled_avg_price": "91250.50"
        }
        res = executor.poll_order_fill("ord_123", max_wait_seconds=1.0, poll_interval=0.1)
        assert res["status"] == "filled"
        assert res["filled_qty"] == 0.05
        assert res["filled_avg_price"] == 91250.50

    # B. Partially filled order
    with patch.object(executor, "get_order_by_id") as mock_get:
        mock_get.return_value = {
            "id": "ord_part",
            "status": "partially_filled",
            "symbol": "ETH/USD",
            "side": "buy",
            "qty": "1.0",
            "filled_qty": "0.6",
            "filled_avg_price": "3100.0"
        }
        res_part = executor.poll_order_fill("ord_part", max_wait_seconds=1.0, poll_interval=0.1)
        assert res_part["status"] == "partially_filled"
        assert res_part["filled_qty"] == 0.6

    # C. Rejected order
    with patch.object(executor, "get_order_by_id") as mock_get:
        mock_get.return_value = {
            "id": "ord_rej",
            "status": "rejected",
            "symbol": "AAPL",
            "reject_reason": "insufficient buying power"
        }
        res_rej = executor.poll_order_fill("ord_rej", max_wait_seconds=1.0, poll_interval=0.1)
        assert res_rej["status"] == "rejected"
        assert "insufficient buying power" in res_rej["reason"]


def test_hard_risk_caps_rejection(base_config):
    """RSK: Verifies rejection when order value exceeds hard dollar cap or equity %."""
    executor = AlpacaExecutor(base_config)

    with patch.object(executor, "get_account_equity", return_value=10000.0):
        # 1. Exceeds max position value ($2,500)
        res = executor.place_paper_order(
            signal_id="sig_too_big",
            symbol="BTCUSDT",
            qty=0.1,
            estimated_price=30000.0  # $3,000 > $2,500 limit
        )
        assert res["status"] == "rejected"
        assert "Exceeds max_position_value_usd" in res["reason"]

        # 2. Exceeds max position equity % (30% of $10k = $3,000)
        executor.max_position_value_usd = 5000.0
        res_pct = executor.place_paper_order(
            signal_id="sig_too_heavy",
            symbol="ETHUSDT",
            qty=1.0,
            estimated_price=3500.0  # $3,500 / $10,000 = 35% > 30%
        )
        assert res_pct["status"] == "rejected"
        assert "Exceeds max_position_equity_pct" in res_pct["reason"]


def test_live_money_safety_guard(base_config):
    """SEC-003: Non-paper endpoint must raise RuntimeError unless explicit live trading allowed."""
    bad_config = dict(base_config)
    bad_config["alpaca"] = {
        "endpoint": "https://api.alpaca.markets/v2",  # Live endpoint!
        "api_key": "LIVE_KEY",
        "secret_key": "LIVE_SECRET"
    }

    with pytest.raises(RuntimeError) as exc_info:
        AlpacaExecutor(bad_config)
    assert "CRITICAL SAFETY VIOLATION" in str(exc_info.value)
