"""
Research Strategy Registry and Factory for BTC-ML System V2.
Maintains a catalog of all research candidates and variants, separating them from production strategies.
"""

import logging
from typing import Dict, Any, Type, List, Optional, Tuple
from btc_ml_system.src.research.base import BaseResearchStrategy, StrategyMetadata

logger = logging.getLogger("btc_ml_system.research.registry")


class ResearchStrategyRegistry:
    """Central registry and factory for all quantitative research strategies and variants."""

    _registry: Dict[str, Type[BaseResearchStrategy]] = {}
    _variants: Dict[str, Tuple[Type[BaseResearchStrategy], Dict[str, Any]]] = {}

    @classmethod
    def register(cls, strategy_class: Type[BaseResearchStrategy]) -> Type[BaseResearchStrategy]:
        """Class decorator or explicit registration method for research strategies."""
        try:
            inst = strategy_class()
            strat_id = inst.metadata.strategy_id
        except Exception:
            strat_id = strategy_class.__name__

        if strat_id in cls._registry:
            logger.warning(f"Overwriting existing strategy registration for '{strat_id}'.")
        cls._registry[strat_id] = strategy_class
        return strategy_class

    @classmethod
    def register_variant(
        cls,
        variant_id: str,
        strategy_class: Type[BaseResearchStrategy],
        config: Dict[str, Any]
    ) -> None:
        """Registers a pre-configured strategy variant with its unique ID."""
        cfg = config.copy()
        cfg["strategy_id"] = variant_id
        cls._variants[variant_id] = (strategy_class, cfg)

    @classmethod
    def get(cls, strategy_id: str, config: Optional[Dict[str, Any]] = None) -> BaseResearchStrategy:
        """Instantiates a registered research strategy or pre-registered variant by unique ID."""
        if strategy_id in cls._variants:
            strat_cls, default_cfg = cls._variants[strategy_id]
            merged_cfg = default_cfg.copy()
            if config:
                merged_cfg.update(config)
            return strat_cls(merged_cfg)

        if strategy_id in cls._registry:
            strat_cls = cls._registry[strategy_id]
            return strat_cls(config)

        available = list(cls._registry.keys()) + list(cls._variants.keys())
        raise KeyError(
            f"Strategy '{strategy_id}' not found in ResearchStrategyRegistry. "
            f"Available strategies: {available}"
        )

    @classmethod
    def list_strategies(cls) -> List[StrategyMetadata]:
        """Returns metadata for all registered research strategies and variants."""
        metas = []
        for strat_cls in cls._registry.values():
            inst = strat_cls()
            metas.append(inst.metadata)
        for variant_id, (strat_cls, cfg) in cls._variants.items():
            inst = strat_cls(cfg)
            metas.append(inst.metadata)
        return metas

    @classmethod
    def clear(cls) -> None:
        """Clears the registry and variants (useful for testing)."""
        cls._registry.clear()
        cls._variants.clear()
