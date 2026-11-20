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

# Register Phase 3B pre-registered variants
ResearchStrategyRegistry.register_variant(
    "RS_TF_DUAL_EMA_21_55_V1",
    DualEmaAtrTrendStrategy,
    {"strategy_id": "RS_TF_DUAL_EMA_21_55_V1", "parameters": {"fast_ema_period": 21, "slow_ema_period": 55}}
)
ResearchStrategyRegistry.register_variant(
    "RS_TF_DUAL_EMA_20_50_V1",
    DualEmaAtrTrendStrategy,
    {"strategy_id": "RS_TF_DUAL_EMA_20_50_V1", "parameters": {"fast_ema_period": 20, "slow_ema_period": 50}}
)
ResearchStrategyRegistry.register_variant(
    "RS_TF_DUAL_EMA_50_100_V1",
    DualEmaAtrTrendStrategy,
    {"strategy_id": "RS_TF_DUAL_EMA_50_100_V1", "parameters": {"fast_ema_period": 50, "slow_ema_period": 100}}
)

ResearchStrategyRegistry.register_variant(
    "RS_MOM_DONCHIAN_20_V1",
    TsMomBreakoutStrategy,
    {"strategy_id": "RS_MOM_DONCHIAN_20_V1", "parameters": {"channel_entry_period": 20, "channel_exit_period": 10, "mom_period": 20}}
)
ResearchStrategyRegistry.register_variant(
    "RS_MOM_DONCHIAN_40_V1",
    TsMomBreakoutStrategy,
    {"strategy_id": "RS_MOM_DONCHIAN_40_V1", "parameters": {"channel_entry_period": 40, "channel_exit_period": 20, "mom_period": 40}}
)
ResearchStrategyRegistry.register_variant(
    "RS_MOM_DONCHIAN_55_V1",
    TsMomBreakoutStrategy,
    {"strategy_id": "RS_MOM_DONCHIAN_55_V1", "parameters": {"channel_entry_period": 55, "channel_exit_period": 25, "mom_period": 55}}
)

ResearchStrategyRegistry.register_variant(
    "RS_MR_BB_RSI_20_STD_V1",
    BbRsiMeanReversionStrategy,
    {"strategy_id": "RS_MR_BB_RSI_20_STD_V1", "parameters": {"bb_period": 20, "bb_std": 2.0, "rsi_oversold": 32.0}}
)
ResearchStrategyRegistry.register_variant(
    "RS_MR_BB_RSI_22_STD_V1",
    BbRsiMeanReversionStrategy,
    {"strategy_id": "RS_MR_BB_RSI_22_STD_V1", "parameters": {"bb_period": 20, "bb_std": 2.2, "rsi_oversold": 30.0}}
)
ResearchStrategyRegistry.register_variant(
    "RS_MR_BB_RSI_25_STD_V1",
    BbRsiMeanReversionStrategy,
    {"strategy_id": "RS_MR_BB_RSI_25_STD_V1", "parameters": {"bb_period": 20, "bb_std": 2.5, "rsi_oversold": 28.0}}
)

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
