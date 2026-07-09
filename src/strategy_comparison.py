"""Portfolio strategy baselines for comparative evaluation."""

from __future__ import annotations

from typing import Mapping

import numpy as np
import pandas as pd

from src.optimiser import optimize_portfolio_mean_variance


def equal_weight_weights(tickers: list[str]) -> dict[str, float]:
    """Static equal-weight allocation."""
    if not tickers:
        return {}
    weight = 1.0 / len(tickers)
    return {ticker: weight for ticker in tickers}


def portfolio_period_return(
    weights: Mapping[str, float],
    actual_returns: Mapping[str, float],
) -> float:
    """Single-period portfolio return as weighted sum of asset returns."""
    return float(
        sum(float(weights.get(ticker, 0.0)) * float(actual_returns.get(ticker, 0.0)) for ticker in weights)
    )


def historical_mean_mpt_weights(
    portfolio_data: dict[str, pd.DataFrame],
) -> dict[str, float]:
    """
    Markowitz optimisation using historical mean returns as μ (no Prophet).

    Same Σ and constraints as the production Prophet+MPT strategy.
    """
    return optimize_portfolio_mean_variance(portfolio_data)


def cumulative_return(period_returns: list[float]) -> float:
    """Compound a series of simple period returns."""
    if not period_returns:
        return 0.0
    return float(np.prod([1.0 + float(value) for value in period_returns]) - 1.0)


def annualised_sharpe(period_returns: list[float], periods_per_year: int = 252) -> float:
    """Annualised Sharpe ratio on equal-length period returns (risk-free rate = 0)."""
    if not period_returns:
        return 0.0
    series = np.asarray(period_returns, dtype=float)
    std = float(np.std(series))
    if std == 0:
        return 0.0
    return float((np.mean(series) / std) * np.sqrt(periods_per_year))


def excess_return(strategy_return: float, benchmark_return: float) -> float:
    """Simple excess return (strategy minus benchmark)."""
    return float(strategy_return - benchmark_return)


def strategy_win_rate(strategy_returns: list[float], benchmark_returns: list[float]) -> float:
    """Share of periods where strategy return exceeds benchmark return."""
    if not strategy_returns or len(strategy_returns) != len(benchmark_returns):
        return 0.0
    wins = sum(
        1
        for strat, bench in zip(strategy_returns, benchmark_returns, strict=True)
        if strat > bench
    )
    return float(wins / len(strategy_returns))


def summarise_strategies(
    prophet_mpt_returns: list[float],
    historical_mpt_returns: list[float],
    equal_weight_returns: list[float],
) -> dict[str, dict[str, float]]:
    """
    Build a comparison table for three portfolio policies.

    Returns nested dict keyed by strategy name with cumulative return, Sharpe,
    and excess return vs equal-weight.
    """
    equal_cum = cumulative_return(equal_weight_returns)
    strategies = {
        "prophet_mpt": prophet_mpt_returns,
        "historical_mean_mpt": historical_mpt_returns,
        "equal_weight": equal_weight_returns,
    }
    summary: dict[str, dict[str, float]] = {}
    for name, returns in strategies.items():
        cum = cumulative_return(returns)
        summary[name] = {
            "cumulative_return": cum,
            "sharpe_ratio": annualised_sharpe(returns),
            "excess_vs_equal_weight": excess_return(cum, equal_cum),
            "win_rate_vs_equal_weight": strategy_win_rate(returns, equal_weight_returns),
        }
    return summary
