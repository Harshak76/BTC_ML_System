"""
Labeling Engine Module.
Implements Marcos Lopez de Prado's Triple-Barrier Method for classification labels
and calculates forward return, MFE, and MAE regression targets.
"""

import logging
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def compute_daily_volatility(close: pd.Series, span: int = 24) -> pd.Series:
    """Computes rolling volatility (std dev of 1h log returns) scaled to horizon."""
    returns = np.log(close / close.shift(1))
    vol = returns.ewm(span=span).std()
    return vol.bfill().fillna(0.01)


class TripleBarrierLabeler:
    """
    Implements the Triple-Barrier Method:
    - Upper barrier (Profit Take): P_t * (1 + pt * volatility)
    - Lower barrier (Stop Loss): P_t * (1 - sl * volatility)
    - Vertical barrier: t + H candles
    """

    def __init__(
        self,
        pt_multiplier: float = 1.5,
        sl_multiplier: float = 1.0,
        max_vertical_barrier: int = 12,
        volatility_window: int = 24,
        min_return: float = 0.002
    ):
        self.pt_multiplier = pt_multiplier
        self.sl_multiplier = sl_multiplier
        self.max_vertical_barrier = max_vertical_barrier
        self.volatility_window = volatility_window
        self.min_return = min_return

    def generate_labels(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates classification labels (1: BUY, -1: SELL, 0: HOLD)
        and regression targets (forward log return, MFE, MAE).
        """
        df = df.copy()
        n = len(df)
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values

        vol = compute_daily_volatility(df["close"], span=self.volatility_window).values

        labels = np.zeros(n, dtype=int)
        fwd_returns = np.zeros(n, dtype=float)
        mfes = np.zeros(n, dtype=float)
        maes = np.zeros(n, dtype=float)
        touch_barriers = ["vertical"] * n
        barrier_touch_times = np.zeros(n, dtype=int)

        H = self.max_vertical_barrier

        for i in range(n):
            if i + 1 >= n:
                labels[i] = 0
                continue

            entry_price = close[i]
            cur_vol = max(vol[i], self.min_return)

            upper_barrier = entry_price * (1.0 + self.pt_multiplier * cur_vol)
            lower_barrier = entry_price * (1.0 - self.sl_multiplier * cur_vol)

            end_idx = min(i + H + 1, n)
            window_highs = high[i + 1:end_idx]
            window_lows = low[i + 1:end_idx]
            window_closes = close[i + 1:end_idx]

            if len(window_closes) == 0:
                labels[i] = 0
                continue

            # Forward return over H bars
            fwd_returns[i] = np.log(window_closes[-1] / entry_price)

            # Maximum Favorable Excursion (MFE) & Maximum Adverse Excursion (MAE)
            mfes[i] = np.max(window_highs / entry_price - 1.0)
            maes[i] = np.min(window_lows / entry_price - 1.0)

            # Check barrier hits bar by bar
            first_touch = 0 # 0: vertical, 1: upper (BUY), -1: lower (SELL)
            touch_time = len(window_closes)

            for step in range(len(window_closes)):
                bar_high = window_highs[step]
                bar_low = window_lows[step]

                upper_hit = bar_high >= upper_barrier
                lower_hit = bar_low <= lower_barrier

                if upper_hit and lower_hit:
                    # Ambiguous bar: conservative assumption -> lower barrier (stop-loss) hit first
                    first_touch = -1
                    touch_time = step + 1
                    touch_barriers[i] = "lower"
                    break
                elif upper_hit:
                    first_touch = 1
                    touch_time = step + 1
                    touch_barriers[i] = "upper"
                    break
                elif lower_hit:
                    first_touch = -1
                    touch_time = step + 1
                    touch_barriers[i] = "lower"
                    break

            labels[i] = first_touch
            barrier_touch_times[i] = touch_time

        df["label_tb"] = labels
        # Binary target for Long-only strategy: 1 if upper barrier hit first, else 0
        df["target_buy"] = (df["label_tb"] == 1).astype(int)
        df["fwd_return_12h"] = fwd_returns
        df["mfe_12h"] = mfes
        df["mae_12h"] = maes
        df["barrier_touch_type"] = touch_barriers
        df["barrier_touch_bars"] = barrier_touch_times

        logger.info(
            f"Triple Barrier Label Distribution: "
            f"BUY (1): {(df['label_tb'] == 1).sum()} | "
            f"SELL (-1): {(df['label_tb'] == -1).sum()} | "
            f"HOLD (0): {(df['label_tb'] == 0).sum()}"
        )

        return df
