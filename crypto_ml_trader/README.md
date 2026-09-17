# `crypto_ml_trader`: Production-Grade Non-Repainting BTCUSDT ML Trading System

A research-grade, non-repainting machine learning trading system for **BTCUSDT** on Binance Spot, built in pure Python.

Developed under strict quantitative principles: **zero lookahead bias**, **zero repainting**, **capital preservation first**, **event-driven next-bar execution**, and **purged cross-validation**.

---

## Key Features

1. **Zero Lookahead & Zero Repainting Architecture**:
   - Features computed strictly from information available at or before candle close $t$.
   - Confirmed 4-hour (4h) higher timeframe features resampled and shifted by 1 step so that a 4h candle closing at timestamp $T$ is only accessible to 1h candles closing at or after $T$.
   - Preprocessing scalers (`RobustScaler` / `StandardScaler`) fitted strictly inside training folds.

2. **Data Ingestion & Point-in-Time Quality**:
   - Downloads historical 1h and 4h OHLCV klines from Binance Public REST API (`https://api.binance.com/api/v3/klines`) without requiring API keys.
   - Automatic missing candle gap detection, duplicate handling, and checksum manifest generation (`data/manifests/`).

3. **Triple-Barrier Labeling & Purged Walk-Forward CV**:
   - Marcos Lopez de Prado's **Triple-Barrier Method**:
     - Upper barrier (Profit Take): $P_t (1 + \text{pt} \cdot \sigma_t)$
     - Lower barrier (Stop Loss): $P_t (1 - \text{sl} \cdot \sigma_t)$
     - Vertical barrier: $t + 12$ candles ($H=12$)
   - **Purged Walk-Forward Cross-Validation**:
     - Chronological splits with purging of overlapping label horizons between train and validation folds.
     - Embargo period after validation sets to prevent serial correlation spillover.

4. **Calibrated Machine Learning Models**:
   - LightGBM (preferred), XGBoost, Logistic Regression, and Majority-Class baselines.
   - Probability calibration (`IsotonicRegression` / Platt scaling) fitted on validation folds.
   - Ensemble meta-model combining calibrated probabilities and calculating model disagreement standard deviation.

5. **Multi-Layer Risk Management & Decision Engine**:
   - Fixed-fractional position sizing: $\text{Size} = \frac{\text{Equity} \times 0.005}{\text{Stop Loss Distance in USDT}}$.
   - **Daily Loss Lock**: Halts trading if daily loss (realized + open PnL) exceeds 1.0% of start-of-day equity.
   - **Max Drawdown Shutdown**: Ceases execution if equity drops 10.0% below high-water mark (requires explicit manual reset).
   - **10 Hard Trade Entry Validation Checks**: Trade executed only when ALL 10 checks pass; otherwise returns `HOLD` with exact rejection reason.

6. **Realistic Event-Driven Backtesting**:
   - Next-bar open execution modeling.
   - Full transaction cost modeling (10 bps commission + 5 bps slippage per side = 30 bps round trip).
   - Conservative intrabar execution (assumes stop-loss hit first if both SL and TP touched in same bar).
   - Metrics: Net Return, CAGR, Max Drawdown, Sharpe, Sortino, Calmar, Profit Factor, Expectancy, Win Rate, and Buy-and-Hold benchmark comparison.

7. **Continuous Inference & Paper Trading Engine**:
   - On-demand / continuous Python runner.
   - State persistence (`reports/paper_trading_state.json`).
   - Detailed JSON log of accepted signals and rejected decisions.

---

## Directory Structure

```
crypto_ml_trader/
├── configs/
│   └── btcusdt_1h.yaml       # System configuration parameters
├── data/
│   ├── raw/                  # Downloaded raw Binance kline CSVs
│   ├── processed/            # Cleaned point-in-time features & labels
│   └── manifests/            # Download manifests with SHA256 hashes
├── models/                   # Persisted model, scaler, and calibrator artifacts
├── reports/                  # Backtest JSON reports & paper trading state
├── src/
│   ├── data_ingestion.py     # Binance Public REST API data fetcher
│   ├── data_quality.py       # Timestamp integrity & point-in-time alignment
│   ├── features.py           # Point-in-time feature engineering & leakage detector
│   ├── labels.py             # Triple barrier method & regression targets
│   ├── splits.py             # Purged walk-forward cross validation
│   ├── regimes.py            # 4h HTF market regime classifier
│   ├── models.py             # LightGBM / XGBoost / Logistic models & baselines
│   ├── calibration.py        # Isotonic probability calibration & ensemble
│   ├── risk.py               # Risk manager, kill switches & 10-rule decision engine
│   ├── backtester.py         # Event-driven backtesting engine & performance metrics
│   ├── inference.py          # Continuous inference pipeline
│   └── paper_trader.py       # Paper trading runner & state logger
├── tests/
│   ├── test_features.py      # Feature calculation & HTF shift non-leakage tests
│   ├── test_labels.py        # Triple barrier label hit tests
│   ├── test_leakage.py       # Automated point-in-time target leakage tests
│   └── test_risk.py          # Position sizing & risk limit unit tests
├── requirements.txt
└── README.md
```

---

## Getting Started

### 1. Installation

Create a virtual environment and install dependencies:
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r crypto_ml_trader/requirements.txt
```

### 2. Running Unit Tests

If running from the workspace root (`BTC_ML_System`):
```bash
python -m pytest crypto_ml_trader/tests/ -v
```

If running from inside the `crypto_ml_trader/` directory:
```bash
python -m pytest tests/ -v
```

### 3. Step-by-Step Pipeline Execution

#### Step A: Download Binance Historical Klines
From the workspace root (`BTC_ML_System`):
```bash
python -m crypto_ml_trader.src.data_ingestion --symbol BTCUSDT --days 365 --use_apify
```
Or from inside `crypto_ml_trader/`:
```bash
python -m src.data_ingestion --symbol BTCUSDT --days 365 --use_apify
```

#### Step B: Run Event-Driven Backtest
Run backtest simulation:
```bash
python -c "
import yaml
from crypto_ml_trader.src.data_ingestion import BinanceDataIngestor
from crypto_ml_trader.src.data_quality import DataQualityChecker
from crypto_ml_trader.src.features import FeatureEngineer
from crypto_ml_trader.src.labels import TripleBarrierLabeler
from crypto_ml_trader.src.regimes import RegimeDetector
from crypto_ml_trader.src.models import ModelFactory
from crypto_ml_trader.src.calibration import ModelCalibrator
from crypto_ml_trader.src.backtester import EventDrivenBacktester

with open('crypto_ml_trader/configs/btcusdt_1h.yaml') as f:
    cfg = yaml.safe_load(f)

# Load data
df_1h_raw = pd.read_csv('data/raw/btcusdt_1h.csv')
df_4h_raw = pd.read_csv('data/raw/btcusdt_4h.csv')

df_1h, _ = DataQualityChecker.inspect_and_clean(df_1h_raw, timeframe='1h')
df_4h, _ = DataQualityChecker.inspect_and_clean(df_4h_raw, timeframe='4h')

# Features & Labels
fe = FeatureEngineer(cfg['features'])
df_1h_feat = fe.create_1h_features(df_1h)
df_merged = fe.merge_confirmed_4h_features(df_1h_feat, df_4h)
regime_det = RegimeDetector(cfg['regimes'])
df_annotated = regime_det.annotate_dataframe(df_merged)

labeler = TripleBarrierLabeler()
df_full = labeler.generate_labels(df_annotated)

# Fit LightGBM model
ignore = ['open_time', 'close_time', 'open', 'high', 'low', 'close', 'volume', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'market_regime', 'htf_permits_long', 'label_tb', 'target_buy', 'fwd_return_12h', 'mfe_12h', 'mae_12h', 'barrier_touch_type', 'barrier_touch_bars']
feat_cols = [c for c in df_full.columns if c not in ignore]

X = df_full[feat_cols].fillna(0).values
y = df_full['target_buy'].values

mf = ModelFactory(cfg['models'])
model = mf.train_model(X[:int(len(X)*0.7)], y[:int(len(y)*0.7)])

calibrator = ModelCalibrator()
probs_val = model.predict_proba(X[int(len(X)*0.5):int(len(X)*0.7)])[:, 1]
calibrator.fit(probs_val, y[int(len(y)*0.5):int(len(y)*0.7)])

# Save artifacts
mf.save_artifact(model, 'models/lightgbm_model.joblib')
mf.save_artifact(calibrator, 'models/calibrator.joblib')

# Run backtest on test set
X_test = X[int(len(X)*0.7):]
df_test = df_full.iloc[int(len(df_full)*0.7):].reset_index(drop=True)
probs_test = calibrator.calibrate(model.predict_proba(X_test)[:, 1])

backtester = EventDrivenBacktester(cfg)
metrics = backtester.run_backtest(df_test, probs_test)
backtester.generate_report(metrics)
"
```

#### Step C: Run Continuous Inference / Paper Trading
Execute single paper trading cycle:
```bash
python -m crypto_ml_trader.src.paper_trader
```

---

## Mathematical & Design Principles

### Triple-Barrier Method
Given price series $P_t$ and rolling volatility $\sigma_t$:
- Profit Target Barrier: $U_t = P_t \cdot (1 + 1.5 \cdot \sigma_t)$
- Stop Loss Barrier: $L_t = P_t \cdot (1 - 1.0 \cdot \sigma_t)$
- Vertical Expiry Barrier: $t + 12$ bars

If $U_t$ touched before $L_t$ within 12 bars $\implies y = 1$ (`BUY`).
If $L_t$ touched before $U_t$ within 12 bars $\implies y = -1$ (`SELL`).
If neither touched within 12 bars $\implies y = 0$ (`HOLD`).

### Decision Engine Hard Rules
A trade execution request (`BUY`) is granted **ONLY** when ALL 10 conditions are satisfied:
1. Data complete & market tradable
2. 4h HTF regime permits long trades
3. Valid price structure (SL < Entry < TP)
4. Calibrated $P(\text{BUY}) \ge 0.55$
5. Reward-to-Risk ratio $\ge 1.5$
6. Net Expected Edge $\ge 20$ bps after all transaction costs
7. Model disagreement standard deviation $\le 0.20$
8. Daily Loss Lock inactive (daily PnL $> -1.0\%$)
9. Max Drawdown Shutdown inactive (drawdown $< 10.0\%$)
10. Cooldown inactive & zero open positions

---

## Known Limitations & Extensions

1. **Long-Only Design**: Current build focuses on Binance Spot long-only trading. Short side logic can be added by implementing sell barriers in `risk.py` and margin account routing.
2. **Execution Latency**: Default assumes execution at next bar Open (1-hour resolution). For high-frequency execution, lower base timeframes (e.g. 5m / 15m) can be configured in `configs/btcusdt_1h.yaml`.
3. **Optional Neural Networks**: PyTorch TCN/GRU neural networks are available behind config flag (`use_nn: true`).
