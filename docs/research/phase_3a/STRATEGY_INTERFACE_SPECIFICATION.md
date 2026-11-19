# PHASE 3A — STRATEGY INTERFACE SPECIFICATION

**Module:** `btc_ml_system.src.research.base`  
**Registry:** `btc_ml_system.src.research.registry`  
**Specification Version:** 1.0.0  
**Status:** `MANDATORY QUANTITATIVE STANDARD`

---

## 1. Overview & Objectives

The `BaseResearchStrategy` abstract interface establishes an immutable contract for all quantitative trading hypotheses developed within BTC-ML System V2.

The interface enforces:
1. **Interchangeability:** Any research strategy can be loaded, simulated, and validated through identical simulation harnesses.
2. **Deterministic Outputs:** Guarantees reproducible signal and risk-boundary generation for given historical market inputs.
3. **Decoupled Architecture:** Eliminates any direct dependency on broker order routing, account state, or network APIs.
4. **Unit Enforcement:** Standardizes metric and return scaling across module boundaries.

---

## 2. Interface Contracts & Data Schemas

### 2.1. `StrategyMetadata` Dataclass
Every strategy subclass must provide an immutable metadata definition:
```python
@dataclass
class StrategyMetadata:
    strategy_id: str                   # Unique identifier (e.g. 'RS_TF_DUAL_EMA_ATR_V1')
    strategy_name: str                 # Human-readable title
    family: StrategyFamily             # TREND_FOLLOWING, MOMENTUM, MEAN_REVERSION, etc.
    version: str                       # Semantic version (e.g. '1.0.0')
    author: str                        # Authoring group or researcher
    description: str                   # Hypothesis summary
    supported_assets: List[str]        # Universe symbols (e.g. ['AAPL', 'BTCUSDT', ...])
    supported_timeframes: List[str]    # Permitted timeframes (e.g. ['1h', '4h'])
    parameters_schema: Dict[str, Any]  # Dictionary of hyperparameters with defaults
    created_at: str                    # Creation date in ISO format
```

### 2.2. `ExecutionAssumptions` Dataclass
Defines the economic friction and execution timing under which the strategy must be simulated:
```python
@dataclass
class ExecutionAssumptions:
    slippage_bps: float                # Base slippage (e.g. 5.0 for crypto, 2.0 for equities)
    commission_bps: float              # Exit commission (e.g. 10.0 for crypto, 0.0 for equities)
    execution_timing: str              # 'next_bar_open'
    enforce_completed_candles: bool    # True
    expected_return_unit: ReturnUnit   # ReturnUnit.PERCENTAGE_POINTS
```

### 2.3. Abstract Method Signatures

#### `required_features() -> List[str]`
Returns the list of indicator column names that must be present or computed before signal generation.

#### `generate_signals(df: pd.DataFrame, htf_df: Optional[pd.DataFrame] = None) -> pd.DataFrame`
- **Input:** `df` containing columns `open_time`, `open`, `high`, `low`, `close`, `volume`.
- **Preconditions:** Verified by `validate_input_dataframe()`.
- **Output:** Returns a DataFrame containing:
  - `signal`: Integer column $\in \{-1, 0, 1\}$ (1: Long, 0: Flat/Exit, -1: Short).
  - `signal_strength`: Normalized float in $[0.0, 1.0]$.
  - `regime`: Descriptive regime tag (e.g. `'TRENDING_BULL'`, `'OVERSOLD_REVERSION'`).
  - `entry_price`: Reference fill price (typically close of bar $t$).
  - `stop_loss_price`: Absolute stop loss price level.
  - `take_profit_price`: Absolute take profit target price level.
  - `trailing_stop_pct`: Decimal trailing stop trigger percentage.

#### `calculate_stops_and_targets(df: pd.DataFrame) -> pd.DataFrame`
Attaches volatility-adjusted stop-loss and take-profit levels directly to the DataFrame.

---

## 3. Strict Boundary Validation & Return Unit Governance

### 3.1. Input Validation (`validate_input_dataframe`)
Before signal evaluation, every strategy validates that:
1. All required OHLCV columns exist and are non-null.
2. Timestamps in `open_time` are strictly monotonically increasing ($t_i < t_{i+1}$).
3. The dataset is non-empty.

### 3.2. Return Unit Standardization (`validate_return_units`)
To prevent scale confusion (such as the 100x stability distortion identified during the Phase 2.3 audit):
- If `ReturnUnit.DECIMAL_FRACTION` is declared: any single-step return exceeding $|5.0|$ ($500\%$) raises an immediate `ValueError`, preventing percentage values ($15.0$ for $15\%$) from masquerading as decimals.
- If `ReturnUnit.PERCENTAGE_POINTS` is declared: non-zero return series where all values are $< 0.05$ over extended samples raise an immediate `ValueError`, preventing decimal values ($0.015$ for $1.5\%$) from being misread as percentage points ($0.015\%$).

---

## 4. Factory & Registry Lifecycle (`ResearchStrategyRegistry`)

All research strategies are cataloged in `ResearchStrategyRegistry`:
- **Registration:** Automatically registered upon module import or via `@ResearchStrategyRegistry.register`.
- **Querying:** `ResearchStrategyRegistry.get(strategy_id, config)` dynamically instantiates candidate strategies by unique ID.
- **Listing:** `ResearchStrategyRegistry.list_strategies()` provides metadata catalogs for experiment runners.
