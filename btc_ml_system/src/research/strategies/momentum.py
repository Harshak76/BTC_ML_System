"""
Research Strategy Candidate 2: Momentum Family.
Strategy ID: RS_MOM_TSMOM_BREAKOUT_V1
Hypothesis: Time-series return persistence produces continuing upward price drift
when breaking above the 20-bar Donchian resistance. Filtering for RSI exhaustion
avoids parabolic late-stage entries.
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


class TsMomBreakoutStrategy(BaseResearchStrategy):
    """
    Candidate 2: Momentum Strategy.
    - 20-bar Donchian channel breakout.
    - 20-bar cumulative momentum filter (> 0).
    - RSI(14) overbought ceiling (< 75) to prevent buying exhaustion spikes.
    - 10-bar Donchian low trailing exit.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.channel_entry_period = int(self.params.get("channel_entry_period", 20))
        self.channel_exit_period = int(self.params.get("channel_exit_period", 10))
        self.mom_period = int(self.params.get("mom_period", 20))
        self.rsi_period = int(self.params.get("rsi_period", 14))
        self.rsi_max_entry = float(self.params.get("rsi_max_entry", 75.0))
        self.atr_period = int(self.params.get("atr_period", 14))
        self.atr_stop_multiplier = float(self.params.get("atr_stop_multiplier", 2.0))
        self.atr_tp_multiplier = float(self.params.get("atr_tp_multiplier", 4.5))

    @property
    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            strategy_id="RS_MOM_TSMOM_BREAKOUT_V1",
            strategy_name="Time-Series Momentum with Donchian Breakout & RSI Exhaustion Filter",
            family=StrategyFamily.MOMENTUM,
            version="1.0.0",
            author="Quantitative Research Lab",
            description=(
                "Captures intermediate momentum breakouts using 20-bar Donchian channel highs "
                "with an RSI exhaustion ceiling filter and trailing 10-bar channel exit."
            ),
            supported_assets=["BTCUSDT", "ETHUSDT", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"],
            supported_timeframes=["1h", "4h", "1d"],
            parameters_schema={
                "channel_entry_period": 20,
                "channel_exit_period": 10,
                "mom_period": 20,
                "rsi_period": 14,
                "rsi_max_entry": 75.0,
                "atr_period": 14,
                "atr_stop_multiplier": 2.0,
                "atr_tp_multiplier": 4.5
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
        return ["donchian_high", "donchian_low", "momentum", "rsi", "atr"]

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        close = out["close"]
        high = out["high"]
        low = out["low"]

        # Donchian Channels (shifted by 1 bar to strictly avoid lookahead)
        out["donchian_high"] = high.shift(1).rolling(window=self.channel_entry_period).max()
        out["donchian_low"] = low.shift(1).rolling(window=self.channel_exit_period).min()

        # Cumulative Time-Series Momentum (% return over lookback)
        out["momentum"] = (close - close.shift(self.mom_period)) / (close.shift(self.mom_period) + 1e-12) * 100.0

        # RSI(14)
        delta = close.diff()
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = pd.Series(gain, index=out.index).rolling(window=self.rsi_period).mean()
        avg_loss = pd.Series(loss, index=out.index).rolling(window=self.rsi_period).mean()
        rs = avg_gain / (avg_loss + 1e-12)
        out["rsi"] = 100.0 - (100.0 / (1.0 + rs))

        # ATR(14)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        out["atr"] = tr.rolling(window=self.atr_period).mean()

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

        close = out["close"].values
        donch_high = out["donchian_high"].values
        donch_low = out["donchian_low"].values
        mom = out["momentum"].values
        rsi = out["rsi"].values

        for t in range(1, n):
            if np.isnan(donch_high[t]) or np.isnan(mom[t]) or np.isnan(rsi[t]):
                continue

            # Breakout condition: current close breaches prior 20-bar high
            breakout = close[t] > donch_high[t]
            positive_mom = mom[t] > 0.0
            not_exhausted = rsi[t] < self.rsi_max_entry

            # Exit condition: close falls below prior 10-bar low
            exit_trigger = close[t] < donch_low[t]

            if breakout and positive_mom and not_exhausted:
                signals[t] = 1
                signal_strengths[t] = min(1.0, max(0.2, mom[t] / 10.0))
                regimes[t] = "MOMENTUM_EXPANSION"
            elif exit_trigger:
                signals[t] = 0
                signal_strengths[t] = 0.0
                regimes[t] = "MOMENTUM_EXHAUSTION"

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
        out["trailing_stop_pct"] = 0.02

        return out
