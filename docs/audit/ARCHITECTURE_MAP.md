# BTC-ML SYSTEM V2 — ARCHITECTURE MAP
**Phase 0: Technical Architecture Reconstruction & Component Topology**  
**Date:** November 18, 2026  
**Auditors:** Senior Python Software Architect, Principal Quantitative Developer  

---

## 1. System Architecture Overview

The **btc-ml-system** repository contains two distinct architectural generations:
1. **The Machine Learning Research Pipeline (V1 / V2):** An offline research stack developed for cryptocurrency triple-barrier labeling, feature engineering, ensemble modeling (LightGBM, XGBoost, Logistic Regression, Stacking), probability calibration, and continuous bet sizing.
2. **The Multi-Asset Quantitative Trading System (V3 - V5):** A production-oriented quantitative framework featuring rule-based regime filters, multi-timeframe moving averages, momentum breakouts, pairwise cross-asset correlation control, portfolio-level risk budgets, and live Alpaca REST execution.

---

## 2. High-Level Component Topology

```mermaid
flowchart TD
    subgraph Data Layer
        AlpacaData[Alpaca Data API v2 / v1beta3]
        BinanceData[Binance Public REST API]
        LocalCache[(Local CSV Raw Storage)]
        DP[DataProvider / DataIngestion]
    end

    subgraph Analytical & Feature Layer
        VRC[Volatility Regime Classifier]
        MTF[Multi-Timeframe Filter]
        SF[Session Filter]
        FE[Feature Engineer / Signal Engine]
    end

    subgraph Quantitative Strategy Core
        StratEquities[Equity V4.3 Trend Pullback]
        StratBTC[BTC 4H HTF Trend Strategy]
        StratETH[ETH 1H Regime Momentum Strategy]
        SFac[StrategyFactory]
    end

    subgraph Portfolio & Risk Management
        PM[PortfolioManager - Backtest Mode]
        PPT[PortfolioPaperTrader - Live Mode]
        RE[RiskEngine - DD, Daily Loss, Cooldown]
        CorrCtrl[Rolling Return Correlation Filter]
        PosSizer[Position Sizer - 0.5% Risk]
    end

    subgraph Execution & Persistence
        AlpacaExec[AlpacaExecutor - REST v2]
        AlpacaBroker[(Alpaca Paper Trading Account)]
        DuckDB[(DuckDB - data/btc_ml_system.duckdb)]
    end

    AlpacaData --> DP
    BinanceData -.-> DP
    LocalCache --> DP
    DP --> VRC
    DP --> MTF
    DP --> SF
    VRC --> SFac
    MTF --> SFac
    SF --> SFac
    SFac --> StratEquities
    SFac --> StratBTC
    SFac --> StratETH
    StratEquities --> PPT
    StratBTC --> PPT
    StratETH --> PPT
    PPT --> CorrCtrl
    PPT --> RE
    PPT --> PosSizer
    PosSizer --> AlpacaExec
    AlpacaExec --> AlpacaBroker
    PPT --> DuckDB
    AlpacaExec -.-> DuckDB
```

---

## 3. End-to-End Execution Flow (Live Paper Trading)

The primary live production runner is `run_paper_portfolio_v5.py`, invoking `PortfolioPaperTrader.run_paper_tick()` on an event loop:

```mermaid
sequenceDiagram
    autonumber
    participant Runner as run_paper_portfolio_v5
    participant PPT as PortfolioPaperTrader
    participant Alpaca as AlpacaExecutor
    participant Data as DataProvider
    participant Strat as Strategy Pipelines
    participant DB as DatabaseManager (DuckDB)

    Runner->>PPT: Initialize with portfolio_paper_v5.yaml
    PPT->>Alpaca: get_account_details()
    PPT->>Alpaca: get_open_positions()
    PPT->>DB: get_open_positions()
    PPT->>PPT: _sync_positions_on_startup()
    
    loop Every Poll Interval (30s / 60s)
        Runner->>PPT: run_paper_tick()
        PPT->>Alpaca: Fetch current account equity & buying power
        PPT->>PPT: Evaluate Circuit Breakers (Daily Loss >= 2%, DD >= 10%)
        
        alt Active Open Positions Exist
            PPT->>Data: fetch_live_data(sym, interval)
            PPT->>PPT: Mark-to-market & Evaluate Trailing SL / Take Profit
            opt Exit Hit
                PPT->>Alpaca: close_position(sym, qty)
                PPT->>DB: insert_trade_record(exit_data)
                PPT->>DB: remove_position(sym)
            end
        end

        loop For Each Asset (AAPL, MSFT, NVDA, TSLA, AMZN, BTC, ETH)
            PPT->>Data: fetch_live_data(LTF & HTF)
            PPT->>Strat: Predict Regimes, Apply Filters, Evaluate Strategy
            opt Entry Signal == 1
                PPT->>Strat: Calculate ATR, Stop Loss, Take Profit
                PPT->>PPT: Stage 1 Loosening Tagging (BTC CALM regime)
            end
        end

        PPT->>PPT: Check Rolling Pairwise Correlation (< 0.70 or < 0.80)
        PPT->>PPT: Check Aggregate Portfolio Open Risk (< 3.0%)
        
        opt Approved Signals
            PPT->>Alpaca: place_paper_order(market buy)
            PPT->>DB: insert_trade_record(order_placed)
            PPT->>DB: upsert_position(position_state)
        end
    end
```

---

## 4. Architectural Analysis & Findings

### Finding ARC-001: Disconnected Prototype Package (`crypto_ml_trader`)
- **Severity:** Medium
- **Exact File Path:** `BTC_ML_System/crypto_ml_trader/`
- **Function or Class:** Entire directory tree
- **Existing Behavior:** The directory `crypto_ml_trader/` contains a duplicate implementation of the entire ML and backtesting pipeline (features, labels, models, regimes, risk, splits), complete with its own isolated virtual environment (`venv/`). It is never referenced or imported by `btc_ml_system`.
- **Expected Behavior:** Research prototypes should either be maintained as modular sub-packages within the primary library, archived in a designated `archive/` or `research/` directory, or integrated cleanly into unified test suites.
- **Identified Gap:** Creates severe cognitive overhead, redundancy, and developer confusion regarding which modules are authoritative.
- **Recommended Fix:** Safely archive `crypto_ml_trader/` into `archive/crypto_ml_trader_v2/` after verifying no unique research weights or data are lost.
- **Required Test:** Run `pytest BTC_ML_System/btc_ml_system/tests` to guarantee zero dependency breakage.

---

### Finding ARC-002: Redundant Legacy Paper Trader Module
- **Severity:** Low
- **Exact File Path:** `BTC_ML_System/btc_ml_system/src/paper_trader.py`
- **Function or Class:** `PaperTrader`
- **Existing Behavior:** `paper_trader.py` contains a single-asset mock runner that queries Binance klines and runs `LiveInferencePipeline`. It does not interface with Alpaca, does not use DuckDB, and is superseded by `portfolio_paper_trader.py`.
- **Expected Behavior:** Single-asset paper trading should use the unified `DataProvider` and `AlpacaExecutor` architecture, or be clearly marked as deprecated.
- **Identified Gap:** Two files named `paper_trader.py` and `portfolio_paper_trader.py` exist in the same source directory, creating ambiguity.
- **Recommended Fix:** Deprecate `paper_trader.py` with explicit module-level warnings or refactor it into a single-asset adapter of `PortfolioPaperTrader`.
- **Required Test:** Inspect runner scripts to ensure no active V5 scripts invoke legacy `PaperTrader`.

---

### Finding ARC-003: Disjoint Machine Learning Pipeline from V5 Live Execution
- **Severity:** Medium
- **Exact File Path:** `BTC_ML_System/btc_ml_system/src/models.py`, `features.py`, `labels.py`, `meta_labeler.py`
- **Function or Class:** `EnsembledModel`, `FeatureEngineer`, `TripleBarrierLabeler`, `MetaLabeler`
- **Existing Behavior:** The machine learning components (trained models in `models/lightgbm_model.joblib`, `models/calibrator.joblib`) are completely bypassed during V4/V5 strategy evaluation. Signals are generated exclusively via deterministic rules (RSI, EMA, Donchian, Bollinger Bandwidth).
- **Expected Behavior:** Either the system is explicitly documented as a hybrid rule-based + ML platform where ML acts as a meta-labeling filter, or the ML layer is integrated into the `StrategyFactory` / `SignalEngine` pipeline.
- **Identified Gap:** The repository name is `BTC_ML_System`, but active production paper trading operates 100% on heuristic technical strategies without ML inference.
- **Recommended Fix:** In Phase 3, connect `MetaLabeler` as an optional secondary stage filter inside `SignalEngine.generate_signal()`, allowing ML probability thresholds to gate or scale positions.
- **Required Test:** Add unit tests validating that `MetaLabeler` can score live incoming feature vectors from `DataProvider`.
