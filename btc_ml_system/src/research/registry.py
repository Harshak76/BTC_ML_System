"""
Research Strategy Registry and Factory for BTC-ML System V2.
Maintains a catalog of all research candidates, separating them from production strategies.
"""

import logging
from typing import Dict, Any, Type, List, Optional
from btc_ml_system.src.research.base import BaseResearchStrategy, StrategyMetadata

logger = logging.getLogger("btc_ml_system.research.registry")


class ResearchStrategyRegistry:
    """Central registry and factory for all quantitative research strategies."""

    _registry: Dict[str, Type[BaseResearchStrategy]] = {}

    @classmethod
    def register(cls, strategy_class: Type[BaseResearchStrategy]) -> Type[BaseResearchStrategy]:
        """Class decorator or explicit registration method for research strategies."""
        # Create a dummy instance or inspect metadata to extract strategy_id
        try:
            inst = strategy_class()
            strat_id = inst.metadata.strategy_id
        except Exception:
            # Fallback to class name
            strat_id = strategy_class.__name__

        if strat_id in cls._registry:
            logger.warning(f"Overwriting existing strategy registration for '{strat_id}'.")
        cls._registry[strat_id] = strategy_class
        return strategy_class

    @classmethod
    def get(cls, strategy_id: str, config: Optional[Dict[str, Any]] = None) -> BaseResearchStrategy:
        """Instantiates a registered research strategy by its unique ID."""
        if strategy_id not in cls._registry:
            raise KeyError(
                f"Strategy '{strategy_id}' not found in ResearchStrategyRegistry. "
                f"Available strategies: {list(cls._registry.keys())}"
            )
        strat_cls = cls._registry[strategy_id]
        return strat_cls(config)

    @classmethod
    def list_strategies(cls) -> List[StrategyMetadata]:
        """Returns metadata for all registered research strategies."""
        metas = []
        for strat_cls in cls._registry.values():
            inst = strat_cls()
            metas.append(inst.metadata)
        return metas

    @classmethod
    def clear(cls) -> None:
        """Clears the registry (useful for testing)."""
        cls._registry.clear()
