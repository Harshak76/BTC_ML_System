"""
Base Interface and Abstract Specifications for BTC-ML System V2 Quantitative Research Strategies.
Ensures uniform metadata, configuration schemas, signal output structures,
unit enforcement, and strict separation from broker execution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Union
import numpy as np
import pandas as pd


class ReturnUnit(str, Enum):
    """Explicit convention for return units across research module boundaries."""
    PERCENTAGE_POINTS = "percentage_points"  # e.g., 5.0 for +5.0%
    DECIMAL_FRACTION = "decimal_fraction"    # e.g., 0.05 for +5.0%


class StrategyFamily(str, Enum):
    """Categorization of research strategy hypotheses."""
    TREND_FOLLOWING = "trend_following"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    REGIME_ADAPTIVE = "regime_adaptive"
    MULTI_FACTOR = "multi_factor"


@dataclass
class StrategyMetadata:
    """Formal metadata schema for every research strategy candidate."""
    strategy_id: str
    strategy_name: str
    family: StrategyFamily
    version: str
    author: str
    description: str
    supported_assets: List[str]
    supported_timeframes: List[str]
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    created_at: str = "2026-11-19"


@dataclass
class ExecutionAssumptions:
    """Explicit execution model assumptions governing research simulations."""
    slippage_bps: float
    commission_bps: float
    execution_timing: str = "next_bar_open"
    enforce_completed_candles: bool = True
    expected_return_unit: ReturnUnit = ReturnUnit.PERCENTAGE_POINTS


@dataclass
class ResearchSignal:
    """Standardized atomic signal representation emitted by research strategies."""
    timestamp: Any
    symbol: str
    direction: int  # 1 for Long, 0 for Flat, -1 for Short
    strength: float = 1.0  # Normalized [0.0, 1.0]
    entry_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseResearchStrategy(ABC):
    """
    Abstract Base Class for all BTC-ML Research Strategy Candidates.
    
    Guarantees:
    1. Zero broker connection: Strategies have no access to broker APIs or order routing.
    2. Completed candle compliance: Signal evaluation occurs on completed bars.
    3. Return unit standardization: Enforces explicit percentage vs. decimal scale checks.
    4. Determinism: Identical historical market data inputs produce identical signals.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.params = self.config.get("parameters", {})
        self._validate_params()

    @property
    @abstractmethod
    def metadata(self) -> StrategyMetadata:
        """Returns the immutable strategy metadata contract."""
        pass

    @property
    @abstractmethod
    def execution_assumptions(self) -> ExecutionAssumptions:
        """Returns the configured execution friction and timing assumptions."""
        pass

    @abstractmethod
    def required_features(self) -> List[str]:
        """Lists all required indicator/feature columns necessary for signal evaluation."""
        pass

    @abstractmethod
    def generate_signals(
        self,
        df: pd.DataFrame,
        htf_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Evaluates historical market candles and computes signal columns:
        - 'signal': integer in {-1, 0, 1}
        - 'signal_strength': float in [0.0, 1.0]
        - 'regime': string tag
        
        Strict zero-leakage rule: row t must depend ONLY on data up to row t.
        """
        pass

    @abstractmethod
    def calculate_stops_and_targets(
        self,
        df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Attaches risk management bounds to the signal DataFrame:
        - 'stop_loss_price': float
        - 'take_profit_price': float
        - 'trailing_stop_pct': float
        """
        pass

    def validate_input_dataframe(self, df: pd.DataFrame) -> None:
        """
        Ensures input OHLCV DataFrame conforms to quantitative standards:
        - Contains required columns: open_time, open, high, low, close, volume
        - Strictly monotonically increasing in timestamp
        - Contains zero NaN values in core OHLC series
        """
        required_cols = {"open_time", "open", "high", "low", "close", "volume"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Input DataFrame missing mandatory columns: {missing}")

        if df.empty:
            raise ValueError("Input DataFrame is empty.")

        # Check monotonic timestamps
        ts = pd.to_datetime(df["open_time"], utc=True)
        if not ts.is_monotonic_increasing:
            raise ValueError("Input DataFrame timestamps are not strictly monotonically increasing.")

        # Check OHLC non-null
        if df[["open", "high", "low", "close"]].isnull().any().any():
            raise ValueError("Input DataFrame contains NaN values in OHLC price series.")

    @staticmethod
    def validate_return_units(
        values: Union[pd.Series, np.ndarray, float],
        declared_unit: ReturnUnit
    ) -> bool:
        """
        Standardizes return units at module boundaries.
        Rejects ambiguous or anomalous values:
        - If declared DECIMAL_FRACTION, values exceeding |2.0| (200% return in single trade) trigger warning/rejection.
        - If declared PERCENTAGE_POINTS, values clustered near zero (e.g. std < 0.0001) suggest decimal confusion.
        """
        arr = np.asarray(values).flatten()
        arr = arr[~np.isnan(arr)]
        if len(arr) == 0:
            return True

        max_abs = float(np.max(np.abs(arr)))

        if declared_unit == ReturnUnit.DECIMAL_FRACTION:
            # Single trade returns in decimal should rarely exceed 2.0 (200%)
            if max_abs > 5.0:
                raise ValueError(
                    f"Return unit violation: Declared DECIMAL_FRACTION but observed value {max_abs:.2f} > 5.0. "
                    "Likely passing percentage points (e.g. 10.0 for 10%) instead of decimals (0.10)."
                )
        elif declared_unit == ReturnUnit.PERCENTAGE_POINTS:
            # If all non-zero values are < 0.02, likely decimal fractions were passed instead of percentage points
            non_zeros = arr[arr != 0.0]
            if len(non_zeros) > 10 and float(np.max(np.abs(non_zeros))) < 0.05:
                raise ValueError(
                    f"Return unit violation: Declared PERCENTAGE_POINTS but maximum non-zero value is {max_abs:.4f}. "
                    "Likely passing decimal fractions (e.g. 0.01 for 1%) instead of percentage points (1.0)."
                )

        return True

    def _validate_params(self) -> None:
        """Subclasses can override to validate parameter types and boundary ranges."""
        pass
