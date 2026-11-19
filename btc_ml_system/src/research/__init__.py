"""
Quantitative Research Architecture Package for BTC-ML System V2.
Separates research strategies, hypothesis formulations, and evaluation engines
from frozen production and paper trading modules.
"""

from btc_ml_system.src.research.base import (
    BaseResearchStrategy,
    StrategyMetadata,
    ExecutionAssumptions,
    ResearchSignal,
    StrategyFamily,
    ReturnUnit,
)
from btc_ml_system.src.research.registry import ResearchStrategyRegistry
from btc_ml_system.src.research.strategies import (
    DualEmaAtrTrendStrategy,
    TsMomBreakoutStrategy,
    BbRsiMeanReversionStrategy,
)

# Auto-register Phase 3A initial candidates
ResearchStrategyRegistry.register(DualEmaAtrTrendStrategy)
ResearchStrategyRegistry.register(TsMomBreakoutStrategy)
ResearchStrategyRegistry.register(BbRsiMeanReversionStrategy)

__all__ = [
    "BaseResearchStrategy",
    "StrategyMetadata",
    "ExecutionAssumptions",
    "ResearchSignal",
    "StrategyFamily",
    "ReturnUnit",
    "ResearchStrategyRegistry",
    "DualEmaAtrTrendStrategy",
    "TsMomBreakoutStrategy",
    "BbRsiMeanReversionStrategy",
]
