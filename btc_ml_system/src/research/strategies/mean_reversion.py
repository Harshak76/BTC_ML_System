"""
Research Strategy Candidate 3: Mean Reversion Family.
Strategy ID: RS_MR_BB_RSI_REVERSION_V1
Hypothesis: Asset prices in non-trending or normal volatility regimes exhibit statistical
mean-reversion towards their rolling 20-period moving average after reaching extreme
lower Bollinger Band deviations and oversold RSI levels.
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


class BbRsiMeanReversionStrategy(BaseResearchStrategy):
    """
    Candidate 3: Mean Reversion Strategy.
    - 20-period Bollinger Band (2.0 std dev) lower band penetration.
    - RSI(14) oversold threshold (<= 32) confirmation.
    - Bullish candle rejection (close > open) for entry confirmation.
    - Exit target at Middle Band (20 SMA) or ATR stop loss.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.bb_period = int(self.params.get("bb_period", 20))
        self.bb_std = float(self.params.get("bb_std", 2.0))
        self.rsi_period = int(self.params.get("rsi_period", 14))
        self.rsi_oversold = float(self.params.get("rsi_oversold", 32.0))
        self.atr_period = int(self.params.get("atr_period", 14))
        self.atr_stop_multiplier = float(self.params.get("atr_stop_multiplier", 1.5))

    @property
    def metadata(self) -> StrategyMetadata:
        strat_id = self.config.get("strategy_id", "RS_MR_BB_RSI_REVERSION_V1")
        version = self.config.get("version", "1.0.0")
        strat_name = self.config.get(
            "strategy_name",
            f"Bollinger Band Deviation ({self.bb_period}, {self.bb_std} std) with RSI Oversold & Mean Reversion Exit"
        )
        return StrategyMetadata(
            strategy_id=strat_id,
            strategy_name=strat_name,
            family=StrategyFamily.MEAN_REVERSION,
            version=version,
            author="Quantitative Research Lab",
            description=(
                f"Exploits short-term statistical mean reversion when price pierces the lower "
                f"Bollinger Band ({self.bb_std} std) under oversold RSI conditions. Targets the middle moving average band."
            ),
            supported_assets=["BTCUSDT", "ETHUSDT", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"],
            supported_timeframes=["1h", "4h"],
            parameters_schema={
                "bb_period": self.bb_period,
                "bb_std": self.bb_std,
                "rsi_period": self.rsi_period,
                "rsi_oversold": self.rsi_oversold,
                "atr_period": self.atr_period,
                "atr_stop_multiplier": self.atr_stop_multiplier
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
        return ["bb_middle", "bb_upper", "bb_lower", "rsi", "atr"]

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        close = out["close"]
        high = out["high"]
        low = out["low"]

        # Bollinger Bands (20-period, 2 std)
        rolling_mean = close.rolling(window=self.bb_period).mean()
        rolling_std = close.rolling(window=self.bb_period).std()
        out["bb_middle"] = rolling_mean
        out["bb_upper"] = rolling_mean + (rolling_std * self.bb_std)
        out["bb_lower"] = rolling_mean - (rolling_std * self.bb_std)

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
        open_p = out["open"].values
        low = out["low"].values
        bb_middle = out["bb_middle"].values
        bb_lower = out["bb_lower"].values
        rsi = out["rsi"].values

        for t in range(1, n):
            if np.isnan(bb_lower[t]) or np.isnan(rsi[t]):
                continue

            # Oversold condition: prior bar dipped into or below lower band, or current low breached
            band_penetration = (low[t] <= bb_lower[t]) or (close[t-1] <= bb_lower[t-1])
            oversold_rsi = (rsi[t] <= self.rsi_oversold) or (rsi[t-1] <= self.rsi_oversold)
            bullish_candle = close[t] > open_p[t]  # Green rejection bar

            # Target exit: close reaches or exceeds middle band (20 SMA)
            target_reached = close[t] >= bb_middle[t]

            if band_penetration and oversold_rsi and bullish_candle:
                signals[t] = 1
                signal_strengths[t] = min(1.0, max(0.3, (self.rsi_oversold - rsi[t] + 10.0) / 20.0))
                regimes[t] = "OVERSOLD_REVERSION"
            elif target_reached:
                signals[t] = 0
                signal_strengths[t] = 0.0
                regimes[t] = "MEAN_REVERTED"

        out["signal"] = signals
        out["signal_strength"] = signal_strengths
        out["regime"] = regimes

        return self.calculate_stops_and_targets(out)

    def calculate_stops_and_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        close = out["close"]
        atr = out.get("atr", close * 0.015)
        bb_middle = out.get("bb_middle", close * 1.02)

        out["entry_price"] = close
        out["stop_loss_price"] = close - (atr * self.atr_stop_multiplier)
        out["take_profit_price"] = bb_middle
        out["trailing_stop_pct"] = 0.015

        return out
