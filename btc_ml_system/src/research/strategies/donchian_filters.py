"""
Phase 3C Controlled Filter Research Strategies:
1. RS_MOM_DONCHIAN_40_CONTROL
2. RS_MOM_DONCHIAN_40_ADX25
3. RS_MOM_DONCHIAN_40_4H_EMA_SLOPE

Implements strict zero-lookahead filtering on top of the validated Phase 3B Donchian-40 core.
"""

from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

from btc_ml_system.src.research.base import (
    BaseResearchStrategy,
    StrategyMetadata,
    ExecutionAssumptions,
    StrategyFamily,
    ReturnUnit
)


class Donchian40ControlStrategy(BaseResearchStrategy):
    """
    Phase 3C Candidate 1 (Control):
    Exact reproduction of Phase 3B RS_MOM_DONCHIAN_40_V1.
    - 40-bar Donchian channel entry.
    - 20-bar Donchian channel exit.
    - 40-bar cumulative momentum filter (> 0).
    - RSI(14) exhaustion ceiling (< 75.0).
    - ATR(14) stops (SL 2.0x, TP 4.5x, trailing 2%).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.channel_entry_period = int(self.params.get("channel_entry_period", 40))
        self.channel_exit_period = int(self.params.get("channel_exit_period", 20))
        self.mom_period = int(self.params.get("mom_period", 40))
        self.rsi_period = int(self.params.get("rsi_period", 14))
        self.rsi_max_entry = float(self.params.get("rsi_max_entry", 75.0))
        self.atr_period = int(self.params.get("atr_period", 14))
        self.atr_stop_multiplier = float(self.params.get("atr_stop_multiplier", 2.0))
        self.atr_tp_multiplier = float(self.params.get("atr_tp_multiplier", 4.5))
        self.trailing_stop_pct = float(self.params.get("trailing_stop_pct", 0.02))

    @property
    def metadata(self) -> StrategyMetadata:
        strat_id = self.config.get("strategy_id", "RS_MOM_DONCHIAN_40_CONTROL")
        version = self.config.get("version", "2.0.0")
        strat_name = self.config.get(
            "strategy_name",
            "Donchian 40 Breakout Control (Phase 3C Reproduction)"
        )
        return StrategyMetadata(
            strategy_id=strat_id,
            strategy_name=strat_name,
            family=StrategyFamily.MOMENTUM,
            version=version,
            author="Quantitative Research Lab",
            description=(
                "Phase 3C Control Candidate: 40-bar Donchian breakout with 40-bar momentum filter "
                "and RSI(14) exhaustion ceiling on authentic datasets."
            ),
            supported_assets=["BTCUSDT", "ETHUSDT", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"],
            supported_timeframes=["1h", "4h", "1d"],
            parameters_schema={
                "channel_entry_period": self.channel_entry_period,
                "channel_exit_period": self.channel_exit_period,
                "mom_period": self.mom_period,
                "rsi_period": self.rsi_period,
                "rsi_max_entry": self.rsi_max_entry,
                "atr_period": self.atr_period,
                "atr_stop_multiplier": self.atr_stop_multiplier,
                "atr_tp_multiplier": self.atr_tp_multiplier,
                "trailing_stop_pct": self.trailing_stop_pct
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

            breakout = close[t] > donch_high[t]
            positive_mom = mom[t] > 0.0
            not_exhausted = rsi[t] < self.rsi_max_entry

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
        out["trailing_stop_pct"] = self.trailing_stop_pct

        return out


class Donchian40AdxStrategy(Donchian40ControlStrategy):
    """
    Phase 3C Candidate 2 (ADX Treatment):
    Inherits all core mechanics of Donchian40 Control, with:
    - ADX(14) >= 25.0 filter on completed signal candle close.
    - Entries blocked if ADX < 25.0.
    - Exits remain identical to Control.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.adx_period = int(self.params.get("adx_period", 14))
        self.adx_threshold = float(self.params.get("adx_threshold", 25.0))

    @property
    def metadata(self) -> StrategyMetadata:
        strat_id = self.config.get("strategy_id", "RS_MOM_DONCHIAN_40_ADX25")
        version = self.config.get("version", "2.0.0")
        strat_name = self.config.get(
            "strategy_name",
            "Donchian 40 Breakout with ADX(14) >= 25 Filter"
        )
        return StrategyMetadata(
            strategy_id=strat_id,
            strategy_name=strat_name,
            family=StrategyFamily.MOMENTUM,
            version=version,
            author="Quantitative Research Lab",
            description=(
                f"Phase 3C Treatment Candidate 2: Donchian 40 breakout conditioned on ADX({self.adx_period}) "
                f">= {self.adx_threshold} trend strength confirmation on completed candles."
            ),
            supported_assets=["BTCUSDT", "ETHUSDT", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"],
            supported_timeframes=["1h", "4h", "1d"],
            parameters_schema={
                "channel_entry_period": self.channel_entry_period,
                "channel_exit_period": self.channel_exit_period,
                "mom_period": self.mom_period,
                "rsi_period": self.rsi_period,
                "rsi_max_entry": self.rsi_max_entry,
                "adx_period": self.adx_period,
                "adx_threshold": self.adx_threshold,
                "atr_period": self.atr_period,
                "atr_stop_multiplier": self.atr_stop_multiplier,
                "atr_tp_multiplier": self.atr_tp_multiplier,
                "trailing_stop_pct": self.trailing_stop_pct
            }
        )

    def required_features(self) -> List[str]:
        return super().required_features() + ["adx"]

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        out = super()._compute_indicators(df)
        high = out["high"]
        low = out["low"]
        close = out["close"]

        # Wilder's ADX calculation on completed candles
        prev_close = close.shift(1)
        prev_high = high.shift(1)
        prev_low = low.shift(1)

        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        up_move = high - prev_high
        down_move = prev_low - low

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        alpha = 1.0 / self.adx_period
        tr_smooth = pd.Series(tr, index=out.index).ewm(alpha=alpha, adjust=False).mean()
        plus_dm_smooth = pd.Series(plus_dm, index=out.index).ewm(alpha=alpha, adjust=False).mean()
        minus_dm_smooth = pd.Series(minus_dm, index=out.index).ewm(alpha=alpha, adjust=False).mean()

        plus_di = 100.0 * (plus_dm_smooth / (tr_smooth + 1e-12))
        minus_di = 100.0 * (minus_dm_smooth / (tr_smooth + 1e-12))

        dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-12))
        out["adx"] = dx.ewm(alpha=alpha, adjust=False).mean()

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
        adx = out["adx"].values

        for t in range(1, n):
            if np.isnan(donch_high[t]) or np.isnan(mom[t]) or np.isnan(rsi[t]) or np.isnan(adx[t]):
                continue

            breakout = close[t] > donch_high[t]
            positive_mom = mom[t] > 0.0
            not_exhausted = rsi[t] < self.rsi_max_entry
            adx_confirmed = adx[t] >= self.adx_threshold

            exit_trigger = close[t] < donch_low[t]

            if breakout and positive_mom and not_exhausted and adx_confirmed:
                signals[t] = 1
                signal_strengths[t] = min(1.0, max(0.2, mom[t] / 10.0))
                regimes[t] = "MOMENTUM_EXPANSION_ADX"
            elif exit_trigger:
                signals[t] = 0
                signal_strengths[t] = 0.0
                regimes[t] = "MOMENTUM_EXHAUSTION"

        out["signal"] = signals
        out["signal_strength"] = signal_strengths
        out["regime"] = regimes

        return self.calculate_stops_and_targets(out)


class Donchian40HtfEmaSlopeStrategy(Donchian40ControlStrategy):
    """
    Phase 3C Candidate 3 (4H EMA Slope Treatment):
    Inherits all core mechanics of Donchian40 Control, with:
    - Multi-timeframe trend confirmation from higher timeframe (4H).
    - 20-period EMA calculated strictly on fully completed 4H bars.
    - Slope = EMA_4H[k] - EMA_4H[k-1] > 0.
    - Strict Zero-Lookahead: At 1H candle close t, only completed 4H bars are referenced.
      The currently forming 4H bar is strictly ignored.
    - Entries blocked if 4H EMA slope <= 0.
    - Exits remain identical to Control.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.htf_ema_period = int(self.params.get("htf_ema_period", 20))

    @property
    def metadata(self) -> StrategyMetadata:
        strat_id = self.config.get("strategy_id", "RS_MOM_DONCHIAN_40_4H_EMA_SLOPE")
        version = self.config.get("version", "2.0.0")
        strat_name = self.config.get(
            "strategy_name",
            "Donchian 40 Breakout with 4H EMA Slope > 0 Filter"
        )
        return StrategyMetadata(
            strategy_id=strat_id,
            strategy_name=strat_name,
            family=StrategyFamily.MOMENTUM,
            version=version,
            author="Quantitative Research Lab",
            description=(
                f"Phase 3C Treatment Candidate 3: Donchian 40 breakout conditioned on positive 4H EMA({self.htf_ema_period}) "
                "slope calculated strictly on completed 4H bars without lookahead."
            ),
            supported_assets=["BTCUSDT", "ETHUSDT", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN"],
            supported_timeframes=["1h", "4h", "1d"],
            parameters_schema={
                "channel_entry_period": self.channel_entry_period,
                "channel_exit_period": self.channel_exit_period,
                "mom_period": self.mom_period,
                "rsi_period": self.rsi_period,
                "rsi_max_entry": self.rsi_max_entry,
                "htf_ema_period": self.htf_ema_period,
                "atr_period": self.atr_period,
                "atr_stop_multiplier": self.atr_stop_multiplier,
                "atr_tp_multiplier": self.atr_tp_multiplier,
                "trailing_stop_pct": self.trailing_stop_pct
            }
        )

    def required_features(self) -> List[str]:
        return super().required_features() + ["htf_ema_slope"]

    def _compute_htf_slope(self, df: pd.DataFrame, htf_df: Optional[pd.DataFrame] = None) -> pd.Series:
        """
        Computes 4H EMA slope strictly using completed 4H bars.
        Ensures zero lookahead: at 1H row t (which closes at t_open + 1h),
        only 4H bars with completed_at <= t_open + 1h are referenced.
        """
        open_time = pd.to_datetime(df["open_time"], utc=True)
        # 1H bar close time
        close_time = open_time + pd.to_timedelta(1, unit="h")

        # Determine median bar interval of df
        time_diffs = open_time.diff().dropna()
        median_hours = (time_diffs.median().total_seconds() / 3600.0) if len(time_diffs) > 0 else 1.0

        if median_hours >= 3.5:
            # Data is already 4H or higher (e.g. BTCUSDT 4H)
            # In a 4H dataframe, row t is the completed 4H bar!
            # The EMA and slope of row t can be used directly for bar t
            ema = df["close"].ewm(span=self.htf_ema_period, adjust=False).mean()
            slope = ema.diff()
            return slope

        # If htf_df is explicitly supplied, use it
        if htf_df is not None and not htf_df.empty:
            htf = htf_df.copy()
            htf["open_time"] = pd.to_datetime(htf["open_time"], utc=True)
            htf["completed_at"] = htf["open_time"] + pd.to_timedelta(4, unit="h")
            htf["ema"] = htf["close"].ewm(span=self.htf_ema_period, adjust=False).mean()
            htf["slope"] = htf["ema"].diff()
            ohlc_4h = htf
        else:
            # Resample 1H data to 4H bars
            df_sorted = df.copy()
            df_sorted["dt_idx"] = open_time
            df_sorted = df_sorted.set_index("dt_idx").sort_index()

            ohlc_4h = df_sorted.resample("4h", origin="start_day").agg({
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum"
            }).dropna(subset=["close"]).reset_index()

            ohlc_4h["completed_at"] = ohlc_4h["dt_idx"] + pd.to_timedelta(4, unit="h")
            ohlc_4h["ema"] = ohlc_4h["close"].ewm(span=self.htf_ema_period, adjust=False).mean()
            ohlc_4h["slope"] = ohlc_4h["ema"].diff()

        # Merge asof to align each 1H row with the most recent COMPLETED 4H bar
        df_temp = pd.DataFrame({
            "orig_idx": np.arange(len(df)),
            "close_time": close_time
        }).sort_values("close_time")

        merged = pd.merge_asof(
            df_temp,
            ohlc_4h[["completed_at", "slope"]].dropna(subset=["completed_at"]).sort_values("completed_at"),
            left_on="close_time",
            right_on="completed_at",
            direction="backward"
        ).sort_values("orig_idx")

        return pd.Series(merged["slope"].values, index=df.index)

    def _compute_indicators(self, df: pd.DataFrame, htf_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        out = super()._compute_indicators(df)
        out["htf_ema_slope"] = self._compute_htf_slope(df, htf_df)
        return out

    def generate_signals(
        self,
        df: pd.DataFrame,
        htf_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        self.validate_input_dataframe(df)
        out = self._compute_indicators(df, htf_df)

        n = len(out)
        signals = np.zeros(n, dtype=int)
        signal_strengths = np.zeros(n, dtype=float)
        regimes = ["NORMAL"] * n

        close = out["close"].values
        donch_high = out["donchian_high"].values
        donch_low = out["donchian_low"].values
        mom = out["momentum"].values
        rsi = out["rsi"].values
        slope = out["htf_ema_slope"].values

        for t in range(1, n):
            if np.isnan(donch_high[t]) or np.isnan(mom[t]) or np.isnan(rsi[t]) or np.isnan(slope[t]):
                continue

            breakout = close[t] > donch_high[t]
            positive_mom = mom[t] > 0.0
            not_exhausted = rsi[t] < self.rsi_max_entry
            slope_confirmed = slope[t] > 0.0

            exit_trigger = close[t] < donch_low[t]

            if breakout and positive_mom and not_exhausted and slope_confirmed:
                signals[t] = 1
                signal_strengths[t] = min(1.0, max(0.2, mom[t] / 10.0))
                regimes[t] = "MOMENTUM_EXPANSION_4H_SLOPE"
            elif exit_trigger:
                signals[t] = 0
                signal_strengths[t] = 0.0
                regimes[t] = "MOMENTUM_EXHAUSTION"

        out["signal"] = signals
        out["signal_strength"] = signal_strengths
        out["regime"] = regimes

        return self.calculate_stops_and_targets(out)
