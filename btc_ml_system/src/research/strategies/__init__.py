"""
Research Strategies Module for BTC-ML System V2.
Exports initial research strategy candidates.
"""

from btc_ml_system.src.research.strategies.trend_following import DualEmaAtrTrendStrategy
from btc_ml_system.src.research.strategies.momentum import TsMomBreakoutStrategy
from btc_ml_system.src.research.strategies.mean_reversion import BbRsiMeanReversionStrategy
from btc_ml_system.src.research.strategies.donchian_filters import (
    Donchian40ControlStrategy,
    Donchian40AdxStrategy,
    Donchian40HtfEmaSlopeStrategy,
)

__all__ = [
    "DualEmaAtrTrendStrategy",
    "TsMomBreakoutStrategy",
    "BbRsiMeanReversionStrategy",
    "Donchian40ControlStrategy",
    "Donchian40AdxStrategy",
    "Donchian40HtfEmaSlopeStrategy",
]
