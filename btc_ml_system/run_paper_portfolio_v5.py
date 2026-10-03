"""
Continuous Alpaca Paper Trading Runner Script for Portfolio Mode V5.0.
Connects to Alpaca REST API v2, monitors 7 assets continuously,
enforces portfolio risk limits, cross-asset correlation rules,
and provides graceful shutdown and emergency kill-switch handling.
"""

import os
import sys
import time
import signal
import argparse
import logging
from pathlib import Path
import yaml

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from btc_ml_system.src.portfolio_paper_trader import PortfolioPaperTrader

# Setup Console + File Logging
LOG_DIR = Path(__file__).resolve().parent / "reports"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "paper_trader.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)
logger = logging.getLogger("btc_ml_system.paper_runner")

# Global flag for graceful shutdown
running = True


def handle_shutdown(signum, frame):
    global running
    logger.info("Shutdown signal received (SIGINT/SIGTERM). Gracefully stopping paper trading loop...")
    running = False


def load_config(config_path: str) -> dict:
    full_path = Path(__file__).resolve().parent / config_path
    if not full_path.exists():
        full_path = Path(config_path)
    with open(full_path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Alpaca Paper Trading Runner - Portfolio V5.0")
    parser.add_argument("--config", type=str, default="configs/portfolio_paper_v5.yaml", help="Path to portfolio paper config file")
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run mode (no live HTTP orders to Alpaca)")
    parser.add_argument("--flatten", action="store_true", help="EMERGENCY KILL SWITCH: Flatten all open positions and cancel orders immediately")
    parser.add_argument("--summary", action="store_true", help="Generate and print daily portfolio summary report, then exit")
    parser.add_argument("--poll-interval", type=int, default=None, help="Override poll loop interval in seconds")

    args = parser.parse_args()

    # Register Graceful Shutdown Handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print("=" * 115)
    print("      ALPACA PAPER TRADING RUNNER: PORTFOLIO MODE V5.0 (PRODUCTION READY)      ")
    print("=" * 115)

    main_cfg = load_config(args.config)
    poll_interval = args.poll_interval or main_cfg.get("alpaca", {}).get("poll_interval_seconds", 60)
    dry_run_override = True if args.dry_run else None

    # Instantiate Paper Trader Engine
    paper_trader = PortfolioPaperTrader(main_cfg, dry_run_override=dry_run_override)

    # 1. Kill Switch Mode
    if args.flatten:
        print("\n[!] EXECUTING EMERGENCY KILL SWITCH...")
        res = paper_trader.activate_kill_switch()
        print(f"Kill switch result: {res}")
        sys.exit(0)

    # 2. Daily Summary Mode
    if args.summary:
        paper_trader.get_daily_summary()
        sys.exit(0)

    # 3. Startup Verification Banner
    print("\n  LOCKED PORTFOLIO STRATEGY CONFIGURATION:")
    print("   • Total Portfolio Capital Weight Allocations:")
    print("     - Equity V4.3 Basket (AAPL, MSFT, NVDA, TSLA, AMZN) : 50% Total (10% each)")
    print("     - BTCUSDT 4H Strategy                              : 25%")
    print("     - ETHUSDT 1H Strategy                              : 25%")
    print("   • Strategy Parameter Baseline Locks:")
    print("     - Equity V4.3                                      : Frozen")
    print("     - BTC 4H                                           : MTF Medium + NORMAL Volatility Regime Only")
    print("     - ETH 1H                                           : Clean Version (No MTF, No Session Filter)")
    print("     - Dynamic Risk Sizing                              : DISABLED")
    print("     - Early Loss Cut & Profit Runner                   : DISABLED")
    print("   • Alpaca Connection:")
    print(f"     - Endpoint                                         : {paper_trader.alpaca.endpoint}")
    print(f"     - Mode                                             : {'DRY-RUN (Mock Orders)' if paper_trader.alpaca.dry_run else 'ALPACA PAPER TRADING (REST API)'}")
    print(f"     - Log File                                         : {LOG_FILE}")
    print(f"     - Poll Frequency                                   : Every {poll_interval} seconds")
    print("=" * 115 + "\n")

    logger.info("Starting continuous live market monitoring loop. Press Ctrl+C to stop.\n")

    tick_count = 0
    while running:
        tick_count += 1
        start_time = time.time()
        
        try:
            logger.info(f"--- Poll Tick #{tick_count} ---")
            status = paper_trader.run_paper_tick()
            logger.info(f"Tick #{tick_count} completed | Equity: ${status.get('equity', 0):,.2f} | Orders Placed: {status.get('orders_placed', 0)}")
            
            # Print periodic summary every 15 ticks
            if tick_count % 15 == 0:
                paper_trader.get_daily_summary()
                
        except Exception as e:
            logger.error(f"Error in paper trader poll loop tick #{tick_count}: {e}", exc_info=True)

        # Sleep for poll interval with responsive interrupt check
        elapsed = time.time() - start_time
        sleep_needed = max(1, poll_interval - elapsed)
        
        sleep_step = 1.0
        slept = 0.0
        while slept < sleep_needed and running:
            time.sleep(min(sleep_step, sleep_needed - slept))
            slept += sleep_step

    logger.info("Paper trading runner successfully shut down.")
    print("\nPaper trading process stopped cleanly.")


if __name__ == "__main__":
    main()
