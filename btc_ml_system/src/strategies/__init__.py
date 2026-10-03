"""
Strategy Factory Registry for V4.3 btc_ml_system.
Dynamically instantiates strategy modules based on configuration settings.
"""

from typing import Dict, Any
from btc_ml_system.src.strategies.base_strategy import BaseStrategy
from btc_ml_system.src.strategies.trend_pullback import TrendPullbackStrategy
from btc_ml_system.src.strategies.crypto_regime_momentum import CryptoRegimeMomentumStrategy
from btc_ml_system.src.strategies.btc_htf_trend import BtcHtfTrendStrategy


class StrategyFactory:
    """Factory registry for quantitative strategies."""

    _strategies = {
        "trend_pullback": TrendPullbackStrategy,
        "crypto_regime_momentum": CryptoRegimeMomentumStrategy,
        "btc_htf_trend": BtcHtfTrendStrategy,
    }

    @classmethod
    def get_strategy(cls, config: Dict[str, Any]) -> BaseStrategy:
        strat_name = config.get("strategy", {}).get("name", "trend_pullback")
        if strat_name not in cls._strategies:
            raise ValueError(f"Unknown strategy name: '{strat_name}'. Available: {list(cls._strategies.keys())}")
        return cls._strategies[strat_name](config)
