"""
Meta-Labeler Module for V3.4 btc_ml_system.
Trains a point-in-time ML model (Logistic Regression or LightGBM) on candidate breakout signals to predict win probability P(Win).
"""

import logging
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("btc_ml_system.meta_labeler")


class MetaLabeler:
    """Extracts point-in-time features and filters candidate trade signals using ML win probability."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.meta_cfg = config.get("meta_labeler", {})
        self.enabled = self.meta_cfg.get("enabled", True)
        self.min_prob = self.meta_cfg.get("min_probability_threshold", 0.55)
        self.model_type = self.meta_cfg.get("model_type", "logistic_regression")
        self.scaler = StandardScaler()
        self.model = None

    def extract_features(self, df_1h: pd.DataFrame) -> pd.DataFrame:
        """
        Computes point-in-time safe features on 1h candles without lookahead leakage.
        """
        df = df_1h.copy()
        close = df["close"]
        open_p = df["open"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # 1. RSI (14)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        df["rsi_14"] = 100 - (100 / (1 + rs))

        # 2. Volume ratio (24h)
        vol_sma = volume.rolling(24).mean().replace(0, 1e-10)
        df["vol_ratio_24h"] = volume / vol_sma

        # 3. ATR % (14)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/14, adjust=False).mean()
        df["atr_pct"] = atr / close

        # 4. EMA20/50 Distance %
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()
        df["ema20_50_dist_pct"] = (ema20 - ema50) / ema50

        # 5. Candle Body Ratio
        candle_range = (high - low).replace(0, 1e-10)
        candle_body = (close - open_p).abs()
        df["body_ratio"] = candle_body / candle_range

        # 6. Breakout Distance % from 20-bar high
        rolling_20_high = high.shift(1).rolling(20).max()
        df["breakout_dist_pct"] = (close - rolling_20_high) / rolling_20_high

        return df

    def fit_predict_signals(
        self,
        df_1h: pd.DataFrame,
        signals: List[Any],
        trades: List[Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Trains model on signal features and filters out trades where P(Win) < min_prob.
        """
        if not self.enabled or not signals or not trades:
            logger.info("Meta-Labeler disabled or insufficient signals/trades.")
            return signals, {"meta_model_status": "disabled", "approved_signals": len(signals)}

        df_feat = self.extract_features(df_1h)
        
        # Build dataset mapping approved signal index -> trade outcome
        feature_cols = ["rsi_14", "vol_ratio_24h", "atr_pct", "ema20_50_dist_pct", "body_ratio", "breakout_dist_pct"]
        
        # Map Trade objects by entry_time / signal timestamp
        trade_outcomes = {}
        for tr in trades:
            # entry_idx in backtester is i+1 (the next bar open time)
            # Find signal timestamp at entry_idx - 1 or match via pd.Timestamp string
            ts = getattr(tr, "entry_time", None) or getattr(tr, "open_time", None) or getattr(tr, "timestamp", None)
            pnl = getattr(tr, "pnl", 0.0)
            if ts is not None:
                # Store normalized string representations in UTC ISO format (YYYY-MM-DD HH:MM:SS)
                ts_dt = pd.to_datetime(ts, utc=True)
                ts_str = ts_dt.strftime("%Y-%m-%d %H:%M:%S")
                trade_outcomes[ts_str] = 1 if pnl > 0 else 0

        df_feat["open_time_dt"] = pd.to_datetime(df_feat["open_time"], utc=True)
        df_feat["open_time_str"] = df_feat["open_time_dt"].dt.strftime("%Y-%m-%d %H:%M:%S")

        X_list, y_list, approved_sig_ptrs = [], [], []

        for sig in signals:
            if not getattr(sig, "allowed_trade", False):
                continue
            sig_dt = pd.to_datetime(sig.timestamp, utc=True)
            sig_str = sig_dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # Find matching trade outcome
            if sig_str not in trade_outcomes:
                # Try matching nearest bar (+1h entry time)
                next_hour_str = (sig_dt + pd.Timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
                if next_hour_str in trade_outcomes:
                    outcome = trade_outcomes[next_hour_str]
                else:
                    continue
            else:
                outcome = trade_outcomes[sig_str]

            # Find matching bar features
            matching_rows = df_feat[df_feat["open_time_str"] == sig_str]
            if matching_rows.empty:
                continue
            
            row_feats = matching_rows[feature_cols].iloc[0].values
            if np.isnan(row_feats).any():
                continue

            X_list.append(row_feats)
            y_list.append(outcome)
            approved_sig_ptrs.append(sig)

        if len(X_list) < 20:
            logger.warning(f"Too few dataset samples ({len(X_list)}) to train Meta-Labeler reliably. Passing all signals.")
            return signals, {"meta_model_status": "insufficient_data", "approved_signals": len(signals)}

        X = np.array(X_list)
        y = np.array(y_list)

        # Use 50% temporal split for out-of-sample prediction
        split_idx = len(X) // 2
        
        # Train on first half
        X_train, y_train = X[:split_idx], y[:split_idx]
        X_test = X[split_idx:]
        
        # Fit scaler and model
        X_train_scaled = self.scaler.fit_transform(X_train)
        
        # Use regularized Logistic Regression (C=0.5) to avoid overfitting small sample size
        self.model = LogisticRegression(C=0.5, random_state=42, max_iter=200)
        self.model.fit(X_train_scaled, y_train)

        # Predict probabilities on test set
        X_test_scaled = self.scaler.transform(X_test)
        probs_test = self.model.predict_proba(X_test_scaled)[:, 1]

        filtered_out_count = 0
        for i, prob in enumerate(probs_test):
            sig = approved_sig_ptrs[split_idx + i]
            if prob < self.min_prob:
                sig.allowed_trade = False
                sig.action = "HOLD"
                sig.rejection_reason = f"Blocked by Meta-Labeler: Win Prob {prob:.2f} < {self.min_prob:.2f}"
                filtered_out_count += 1

        stats = {
            "meta_model_status": "active",
            "total_candidate_signals": len(approved_sig_ptrs),
            "train_samples": split_idx,
            "test_samples": len(X_test),
            "filtered_out_test_signals": filtered_out_count,
            "retained_test_signals": len(probs_test) - filtered_out_count,
            "min_prob_threshold": self.min_prob
        }

        logger.info(f"Meta-Labeler audit: Evaluated {len(X_test)} out-of-sample signals -> Approved {len(probs_test) - filtered_out_count}, Blocked {filtered_out_count} (Prob < {self.min_prob})")

        return signals, stats
