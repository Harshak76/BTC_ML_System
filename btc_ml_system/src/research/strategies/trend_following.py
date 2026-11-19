"""
Research Strategy Candidate 1: Trend Following Family.
Strategy ID: RS_TF_DUAL_EMA_ATR_V1
Hypothesis: Dual Exponential Moving Average crossovers coupled with an ADX trend strength filter
and volatility-adaptive ATR trailing stops capture sustained directional market expansions
while pruning consolidation whip-saws.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from btc_ml_system.src.research.base import (
    BaseResearchStrategy,
    StrategyMetadata,
    ExecutionAssumptions,
    StrategyFamily,
    ReturnUnit
)


class DualEmaAtrTrendStrategy(BaseResearchStrategy):
    """
    Candidate 1: Trend Following Strategy.
    - Fast EMA / Slow EMA crossover for directional entry.
    - ADX filter (>= threshold) to reject ranging/low-volatility periods.
    - Volatility-adjusted stop-loss (multiplier * ATR) and trailing stop.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.fast_period = int(self.params.get("fast_ema_period", 21))
        self.slow_period = int(self.params.get("slow_ema_period", 55))
        self.adx_period = int(self.params.get("adx_period", 14))
        self.adx_threshold = float(self.params.get("adx_threshold", 20.0))
        self.atr_period = int(self.params.get("atr_period", 14))
        self.atr_stop_multiplier = float(self.params.get("atr_stop_multiplier", 2.0))
        self.atr_tp_multiplier = float(self.params.get("atr_tp_multiplier", 4.0))
        self.trailing_stop_pct = float(self.params.get("trailing_stop_pct", 0.025))

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="RS_TF_DUAL_EMA_ATR_V1",
            strategy_name="Dual EMA Crossover with ATR Channel & Trailing Stop",
            family=StrategyFamily.TREND_FOLLOWING,
            version="1.0.0",
            author="Quantitative Research Lab",
            description=(
                "Captures medium-term directional trends using Fast/Slow EMA crossovers. "
                "Enforces an ADX trend strength filter and sets volatility-adaptive ATR risk limits."
            ),
            supported_assets=["BTCUSDT", "ETHUSDT", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"],
            supported_timeframes=["1h", "4h", "1d"],
            parameters_schema={
                "fast_ema_period": 21,
                "slow_ema_period": 55,
                "adx_period": 14,
                "adx_threshold": 20.0,
                "atr_period": 14,
                "atr_stop_multiplier": 2.0,
                "atr_tp_multiplier": 4.0,
                "trailing_stop_pct": 0.025
            }
        )

    @property
    def execution_assumptions(self) -> ExecutionAssumptions:
        return ExecutionAssumptions(
            slippage_bps=5.0,
            commission_bps=10.0,
            execution_timing="next_bar_open",
            enforce_completed_candles=True,
            expected_return_unit=ReturnUnit.PERCENTAGE_POINTS
        )

    def required_features(self) -> List[str]:
        return ["fast_ema", "slow_ema", "adx", "atr"]

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Computes technical indicators without lookahead bias."""
        out = df.copy()
        close = out["close"]
        high = out["high"]
        low = out["low"]

        # EMAs
        out["fast_ema"] = close.ewm(span=self.fast_period, adjust=False).mean()
        out["slow_ema"] = close.ewm(span=self.slow_period, adjust=False).mean()

        # True Range & ATR
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        out["atr"] = tr.rolling(window=self.atr_period, min_periods=self.atr_period).mean()

        # Directional Movement & ADX
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        tr_smooth = tr.rolling(window=self.adx_period, min_periods=self.adx_period).sum()
        plus_di = 100.0 * (pd.Series(plus_dm, index=out.index).rolling(window=self.adx_period).sum() / (tr_smooth + 1e-12))
        minus_di = 100.0 * (pd.Series(minus_dm, index=out.index).rolling(window=self.adx_period).sum() / (tr_smooth + 1e-12))
        dx = 100.0 * (plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-12)
        out["adx"] = dx.rolling(window=self.adx_period, min_periods=self.adx_period).mean()

        return out

    def generate_signals(
        self,
        df: pd.DataFrame,
        htf_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        self.validate_input_dataframe(df)
        out = self._compute_indicators(df)

        n = len(out)
        signals = np.zeros(n, dtype=int)
        signal_strengths = np.zeros(n, dtype=float)
        regimes = ["NORMAL"] * n

        fast_ema = out["fast_ema"].values
        slow_ema = out["slow_ema"].values
        adx = out["adx"].values
        close = out["close"].values

        # Generate signals strictly on completed bar close
        for t in range(1, n):
            if np.isnan(fast_ema[t]) or np.isnan(slow_ema[t]) or np.isnan(adx[t]):
                continue

            # Bullish Crossover: Fast crosses above Slow
            cross_up = (fast_ema[t-1] <= slow_ema[t-1]) and (fast_ema[t] > slow_ema[t])
            # Trend strength filter
            trending = adx[t] >= self.adx_threshold
            price_above = close[t] > fast_ema[t]

            # Bearish Cross: Fast crosses below Slow
            cross_down = (fast_ema[t-1] >= slow_ema[t-1]) and (fast_ema[t] < slow_ema[t])

            if cross_up and trending and price_above:
                signals[t] = 1
                signal_strengths[t] = min(1.0, float(adx[t] / 40.0))
                regimes[t] = "TRENDING_BULL"
            elif cross_down or (fast_ema[t] < slow_ema[t] and not trending):
                signals[t] = 0
                signal_strengths[t] = 0.0
                regimes[t] = "TRENDING_BEAR" if cross_down else "RANGING"

        out["signal"] = signals
        out["signal_strength"] = signal_strengths
        out["regime"] = regimes

        return self.calculate_stops_and_targets(out)

    def calculate_stops_and_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        close = out["close"]
        atr = out.get("atr", close * 0.02)

        out["entry_price"] = close
        out["stop_loss_price"] = close - (atr * self.atr_stop_multiplier)
        out["take_profit_price"] = close + (atr * self.atr_tp_multiplier)
        out["trailing_stop_pct"] = self.trailing_stop_pct

        return out
