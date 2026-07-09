"""Baseline forecast models for rigorous comparison against Prophet."""

from __future__ import annotations

from typing import Mapping

import numpy as np


def price_mape(actual: Mapping[str, float], predicted: Mapping[str, float]) -> float:
    """Mean absolute percentage error across tickers (percent scale)."""
    errors: list[float] = []
    for ticker, act in actual.items():
        if ticker not in predicted or act == 0:
            continue
        pred = predicted[ticker]
        errors.append(abs(pred - act) / abs(act) * 100)
    return float(np.mean(errors)) if errors else 0.0


def implied_current_prices(
    predicted_prices: Mapping[str, float],
    predicted_returns: Mapping[str, float],
) -> dict[str, float]:
    """Recover pre-forecast prices from Prophet output: P₀ = P̂ / (1 + r̂)."""
    current: dict[str, float] = {}
    for ticker, predicted in predicted_prices.items():
        daily_return = predicted_returns.get(ticker, 0.0)
        denominator = 1.0 + daily_return
        if abs(denominator) < 1e-12:
            continue
        current[ticker] = float(predicted) / denominator
    return current


def naive_price_forecasts(current_prices: Mapping[str, float]) -> dict[str, float]:
    """Random-walk baseline: next price equals last observed price."""
    return {ticker: float(price) for ticker, price in current_prices.items()}


def drift_price_forecasts(
    current_prices: Mapping[str, float],
    mean_returns: Mapping[str, float],
) -> dict[str, float]:
    """Drift baseline: P̂ = P₀ × (1 + mean daily return)."""
    return {
        ticker: float(price) * (1.0 + float(mean_returns.get(ticker, 0.0)))
        for ticker, price in current_prices.items()
    }


def compare_forecast_mapes(
    actual_prices: Mapping[str, float],
    prophet_prices: Mapping[str, float],
    current_prices: Mapping[str, float],
    mean_returns: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """
    Compare Prophet against standard forecast baselines on one observation date.

    Returns:
        Dict with keys: prophet, naive, drift (historical-mean return drift).
    """
    mean_returns = mean_returns or {}
    naive = naive_price_forecasts(current_prices)
    drift = drift_price_forecasts(current_prices, mean_returns)
    return {
        "prophet": price_mape(actual_prices, prophet_prices),
        "naive": price_mape(actual_prices, naive),
        "drift": price_mape(actual_prices, drift),
    }


def prophet_improvement_vs_baseline(prophet_mape: float, baseline_mape: float) -> float:
    """
    Percentage-point MAPE reduction (positive means Prophet is more accurate).

    Example: naive=3.0%, prophet=2.4% → improvement = 0.6.
    """
    return float(baseline_mape - prophet_mape)


def win_rate(prophet_values: list[float], baseline_values: list[float]) -> float:
    """Fraction of observations where Prophet metric is strictly better (lower MAPE)."""
    if not prophet_values or len(prophet_values) != len(baseline_values):
        return 0.0
    wins = sum(1 for p, b in zip(prophet_values, baseline_values, strict=True) if p < b)
    return float(wins / len(prophet_values))
