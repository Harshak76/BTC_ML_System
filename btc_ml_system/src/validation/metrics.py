"""
Quantitative Performance and Risk Metrics Module for BTC-ML System V2.
Provides institutional-grade metrics:
- Total & Annualized Return (CAGR)
- Sharpe Ratio, Sortino Ratio, Calmar Ratio
- Max Drawdown & Max Drawdown Duration
- Profit Factor, Win Rate, Expectancy, Average R-multiple
- Value-at-Risk (VaR) & Conditional Value-at-Risk (CVaR / Expected Shortfall)
- Skewness, Kurtosis, Turnover & Exposure
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Union, Tuple


def calculate_returns_series(equity_curve: Union[List[float], pd.Series, np.ndarray]) -> pd.Series:
    """Converts an equity curve into a percentage returns series."""
    if isinstance(equity_curve, list):
        s = pd.Series(equity_curve)
    elif isinstance(equity_curve, np.ndarray):
        s = pd.Series(equity_curve)
    else:
        s = equity_curve.copy()

    s = s.replace(0, np.nan).dropna()
    returns = s.pct_change().dropna()
    return returns


def calculate_drawdown_series(equity_curve: Union[List[float], pd.Series, np.ndarray]) -> Tuple[pd.Series, float, int]:
    """
    Computes running drawdown series, peak values, and max drawdown.
    Returns (drawdown_series, max_drawdown_pct, max_duration_steps).
    """
    if isinstance(equity_curve, (list, np.ndarray)):
        s = pd.Series(equity_curve)
    else:
        s = equity_curve.copy()

    cummax = s.cummax()
    drawdown = (s - cummax) / cummax.replace(0, np.nan)
    drawdown = drawdown.fillna(0.0)

    max_dd = float(abs(drawdown.min()))

    # Calculate max duration steps in drawdown
    in_dd = drawdown < 0
    duration = 0
    max_duration = 0
    for is_down in in_dd:
        if is_down:
            duration += 1
            if duration > max_duration:
                max_duration = duration
        else:
            duration = 0

    return drawdown, max_dd, max_duration


def calculate_performance_metrics(
    trades: List[Dict[str, Any]],
    equity_curve: Union[List[float], pd.Series, np.ndarray],
    initial_capital: float = 10000.0,
    periods_per_year: int = 252 * 24, # hourly default
    risk_free_rate: float = 0.0,
    is_crypto: bool = True
) -> Dict[str, Any]:
    """
    Computes comprehensive quantitative performance and risk metrics.
    """
    if isinstance(equity_curve, (list, np.ndarray)):
        eq_series = pd.Series(equity_curve)
    else:
        eq_series = equity_curve.copy()

    final_capital = float(eq_series.iloc[-1]) if len(eq_series) > 0 else initial_capital
    total_return_pct = ((final_capital - initial_capital) / initial_capital) * 100.0 if initial_capital > 0 else 0.0

    # Drawdown metrics
    dd_series, max_dd, max_dd_duration = calculate_drawdown_series(eq_series)
    max_dd_pct = max_dd * 100.0

    # Periodic returns
    returns = calculate_returns_series(eq_series)
    n_periods = len(returns)

    # Annualization factor
    ann_factor = 365 * 24 if is_crypto else 252 * 6.5
    years = max(n_periods / ann_factor, 1e-4) if n_periods > 0 else 1.0

    cagr_pct = ((final_capital / initial_capital) ** (1.0 / years) - 1.0) * 100.0 if initial_capital > 0 and final_capital > 0 else 0.0

    # Volatility and Sharpe
    mean_ret = float(returns.mean()) if n_periods > 1 else 0.0
    std_ret = float(returns.std(ddof=1)) if n_periods > 1 else 0.0

    if std_ret > 1e-12:
        sharpe_ratio = float((mean_ret - (risk_free_rate / ann_factor)) / std_ret * np.sqrt(ann_factor))
    else:
        sharpe_ratio = 0.0

    # Downside deviation & Sortino
    negative_returns = returns[returns < 0]
    downside_std = float(negative_returns.std(ddof=1)) if len(negative_returns) > 1 else 0.0
    if downside_std > 1e-12:
        sortino_ratio = float((mean_ret - (risk_free_rate / ann_factor)) / downside_std * np.sqrt(ann_factor))
    else:
        sortino_ratio = 0.0

    # Calmar Ratio
    calmar_ratio = float(cagr_pct / max_dd_pct) if max_dd_pct > 1e-6 else (cagr_pct if cagr_pct > 0 else 0.0)

    # Higher moments (Skewness & Kurtosis)
    if n_periods > 3 and std_ret > 1e-12:
        skewness = float(returns.skew())
        # Uncentered / Pearson kurtosis (Normal = 3.0)
        kurtosis = float(returns.kurtosis() + 3.0)
    else:
        skewness = 0.0
        kurtosis = 3.0

    # Tail-Risk Metrics (Historical VaR and CVaR / Expected Shortfall)
    if n_periods >= 20:
        var_95_pct = float(abs(np.percentile(returns, 5))) * 100.0
        var_99_pct = float(abs(np.percentile(returns, 1))) * 100.0
        tail_95 = returns[returns <= np.percentile(returns, 5)]
        cvar_95_pct = float(abs(tail_95.mean())) * 100.0 if len(tail_95) > 0 else var_95_pct
        tail_99 = returns[returns <= np.percentile(returns, 1)]
        cvar_99_pct = float(abs(tail_99.mean())) * 100.0 if len(tail_99) > 0 else var_99_pct
    else:
        var_95_pct, var_99_pct, cvar_95_pct, cvar_99_pct = 0.0, 0.0, 0.0, 0.0

    # Trade-Level Statistics
    total_trades = len(trades)
    pnls = [float(t.get("pnl_usd", t.get("pnl", 0.0))) for t in trades]
    r_multiples = [float(t.get("r_multiple", 0.0)) for t in trades if "r_multiple" in t]

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    n_wins = len(wins)
    n_losses = len(losses)

    win_rate = (n_wins / total_trades) if total_trades > 0 else 0.0
    loss_rate = (n_losses / total_trades) if total_trades > 0 else 0.0

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

    avg_win = float(np.mean(wins)) if n_wins > 0 else 0.0
    avg_loss = float(abs(np.mean(losses))) if n_losses > 0 else 0.0
    expectancy_usd = (win_rate * avg_win) - (loss_rate * avg_loss)
    avg_r_multiple = float(np.mean(r_multiples)) if len(r_multiples) > 0 else (expectancy_usd / (initial_capital * 0.005) if initial_capital > 0 else 0.0)

    # Exposure & Turnover
    durations = [float(t.get("duration_hours", t.get("duration_bars", 1))) for t in trades]
    total_market_hours = sum(durations)
    total_sim_hours = n_periods if n_periods > 0 else 1.0
    exposure_pct = min(100.0, (total_market_hours / total_sim_hours) * 100.0)

    notionals = [float(t.get("position_value_usd", t.get("position_size", 0.0))) for t in trades]
    total_volume_traded = sum(notionals) * 2.0  # entry + exit
    annualized_turnover = (total_volume_traded / initial_capital) / years if initial_capital > 0 and years > 0 else 0.0

    return {
        "initial_capital": initial_capital,
        "final_capital": final_capital,
        "total_return_pct": total_return_pct,
        "cagr_pct": cagr_pct,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "calmar_ratio": calmar_ratio,
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_duration_bars": max_dd_duration,
        "total_trades": total_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_win_usd": avg_win,
        "avg_loss_usd": avg_loss,
        "expectancy_usd": expectancy_usd,
        "avg_r_multiple": avg_r_multiple,
        "var_95_pct": var_95_pct,
        "var_99_pct": var_99_pct,
        "cvar_95_pct": cvar_95_pct,
        "cvar_99_pct": cvar_99_pct,
        "skewness": skewness,
        "kurtosis": kurtosis,
        "exposure_pct": exposure_pct,
        "annualized_turnover": annualized_turnover,
        "simulated_years": years
    }
