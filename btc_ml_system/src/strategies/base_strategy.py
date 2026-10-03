"""
Base Strategy Abstract Class for V4.0 btc_ml_system.
Defines the standard interface for all quantitative strategy modules.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import pandas as pd


class BaseStrategy(ABC):
    """Abstract Base Class for plug-and-play strategies."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.strat_cfg = config.get("strategy", {}).get("params", {})

    @abstractmethod
    def evaluate_signals(self, df_ltf: pd.DataFrame, df_htf: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Evaluates strategy conditions and attaches a boolean column 'direction_valid'
        (and optionally 'htf_trend_valid') to df_ltf.
        """
        pass
