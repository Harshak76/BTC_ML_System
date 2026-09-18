# btc-ml-system V2.0: Research-Grade Extended Non-Repainting ML Trading System

## Executive Overview
**btc-ml-system** (Version 2.0.0) is a research-grade, non-repainting machine-learning trading system designed for **BTCUSDT** on Binance Spot. Built strictly under quantitative rigor, it prioritizes capital preservation, statistical validity, zero lookahead bias, and zero future leakage.

---

## Core V2 Architectural Enhancements

1. **Triple-Barrier Labeling & Meta-Labeling**:
   - Primary model predicts directional side (`+1` profit target, `-1` stop loss, `0` vertical horizon).
   - Secondary LightGBM Meta-Labeler filters false positives and scales position sizes dynamically.
   - Sample weighting applied via volatility and return magnitude scaling.

2. **Purged Walk-Forward & CPCV Validation**:
   - Strict temporal purging (removing horizon overlap) and embargoing (1% post-test buffer).
   - Combinatorial Purged Cross-Validation (CPCV) evaluating model performance across non-contiguous sub-periods.

3. **Multi-Timeframe Regime Detection**:
   - Classifies market conditions into `BULLISH_TREND`, `BEARISH_TREND`, `RANGING_NEUTRAL`, and `HIGH_VOLATILITY`.
   - Adjusts prediction probability thresholds (e.g., 0.50 in Bullish vs 0.70 in Bearish) and position size multipliers dynamically.

4. **Multi-Model Stacking Ensemble**:
   - Blends **LightGBM**, **XGBoost**, and **Logistic Regression** base models via Ridge stacking meta-learner.
   - Rejects trades if model disagreement exceeds 20%.

5. **Dynamic Volatility Targeting & 10-Rule Risk Engine**:
   - Scales positions inversely to 24h volatility targeting 15% annualized portfolio volatility.
   - Enforces max daily loss circuit breaker (1.0%), max total drawdown (10.0%), and trade cooldown periods.

6. **Robustness Verification**:
   - Monte Carlo 1,000-path equity resampling.
   - Cost stress testing under 1.0x, 2.0x, and 3.0x transaction cost multipliers.

---

## Directory Structure

```
btc_ml_system/
├── configs/
│   └── btcusdt_1h_v2.yaml     # Complete system configuration
├── src/
│   ├── __init__.py
│   ├── data_ingestion.py       # Binance REST & Apify API client
│   ├── data_quality.py         # Integrity, gap & anomaly checks
│   ├── features.py             # Multi-timeframe, technical & microstructural features
│   ├── labels.py               # Triple-barrier labeling & sample weighting
│   ├── meta_labeling.py        # Secondary meta-classifier & bet sizing
│   ├── splits.py               # Purged Walk-Forward & CPCV splitter
│   ├── regimes.py              # 4-state regime detector & dynamic thresholds
│   ├── models.py               # LightGBM + XGBoost + Logistic ensemble
│   ├── calibration.py          # Isotonic probability calibrator
│   ├── risk.py                 # 10-rule risk engine & vol-targeting
│   ├── backtester.py           # Event-driven backtester & Monte Carlo
│   ├── inference.py            # Live real-time inference pipeline
│   ├── monitoring.py           # PSI & KS-test feature drift monitoring
│   └── paper_trader.py         # Mock live paper trading engine
├── tests/
│   ├── test_features.py
│   ├── test_labels.py
│   ├── test_leakage.py
│   ├── test_pipeline.py
│   └── test_risk.py
├── data/                       # Local raw & processed CSV storage
├── models/                     # Saved model artifacts
└── requirements.txt
```

---

## How to Run

### 1. Installation
```bash
pip install -r btc_ml_system/requirements.txt
```

### 2. Run Test Suite
```bash
python -m pytest btc_ml_system/tests/ -v
```

### 3. Run Live Paper Trader Tick

Run directly from terminal:
```bash
python -c "import yaml; from btc_ml_system.src.paper_trader import PaperTrader; cfg = yaml.safe_load(open('btc_ml_system/configs/btcusdt_1h_v2.yaml')); print(PaperTrader(cfg).run_tick())"
```

Or in a Python script:
```python
import yaml
from btc_ml_system.src.paper_trader import PaperTrader

with open("btc_ml_system/configs/btcusdt_1h_v2.yaml") as f:
    config = yaml.safe_load(f)

trader = PaperTrader(config)
result = trader.run_tick()
print(result)
```
