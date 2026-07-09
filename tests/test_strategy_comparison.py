"""Tests for portfolio strategy comparison helpers."""

from __future__ import annotations

import pandas as pd

from src.strategy_comparison import (
    annualised_sharpe,
    cumulative_return,
    equal_weight_weights,
    historical_mean_mpt_weights,
    portfolio_period_return,
    strategy_win_rate,
    summarise_strategies,
)


def _sample_portfolio() -> dict[str, pd.DataFrame]:
    dates = pd.bdate_range("2023-01-01", periods=60)
    return {
        "AAPL": pd.DataFrame({"Returns": [0.001] * 60}, index=dates),
        "MSFT": pd.DataFrame({"Returns": [0.0005] * 60}, index=dates),
    }


class TestStrategyComparison:
    def test_equal_weight_sums_to_one(self) -> None:
        weights = equal_weight_weights(["AAPL", "MSFT", "GOOG"])
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_portfolio_period_return(self) -> None:
        weights = {"AAPL": 0.6, "MSFT": 0.4}
        returns = {"AAPL": 0.02, "MSFT": 0.01}
        result = portfolio_period_return(weights, returns)
        assert abs(result - 0.016) < 1e-9

    def test_historical_mean_mpt_produces_valid_weights(self) -> None:
        weights = historical_mean_mpt_weights(_sample_portfolio())
        assert abs(sum(weights.values()) - 1.0) < 0.01
        assert all(w >= 0 for w in weights.values())

    def test_cumulative_return(self) -> None:
        assert abs(cumulative_return([0.01, 0.02]) - 0.0302) < 1e-6

    def test_strategy_win_rate(self) -> None:
        assert strategy_win_rate([0.02, 0.01], [0.01, 0.02]) == 0.5

    def test_summarise_strategies_keys(self) -> None:
        summary = summarise_strategies(
            prophet_mpt_returns=[0.01, 0.02],
            historical_mpt_returns=[0.005, 0.015],
            equal_weight_returns=[0.008, 0.012],
        )
        assert set(summary.keys()) == {"prophet_mpt", "historical_mean_mpt", "equal_weight"}
        assert "sharpe_ratio" in summary["prophet_mpt"]
