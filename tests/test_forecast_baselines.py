"""Tests for forecast baseline models."""

from __future__ import annotations

from src.forecast_baselines import (
    compare_forecast_mapes,
    implied_current_prices,
    naive_price_forecasts,
    price_mape,
    prophet_improvement_vs_baseline,
    win_rate,
)


class TestForecastBaselines:
    def test_naive_equals_current_price(self) -> None:
        current = {"AAPL": 100.0, "MSFT": 200.0}
        naive = naive_price_forecasts(current)
        assert naive == current

    def test_implied_current_prices(self) -> None:
        predicted = {"AAPL": 105.0}
        returns = {"AAPL": 0.05}
        current = implied_current_prices(predicted, returns)
        assert abs(current["AAPL"] - 100.0) < 1e-6

    def test_prophet_beats_naive_on_perfect_forecast(self) -> None:
        actual = {"AAPL": 105.0}
        current = {"AAPL": 100.0}
        prophet = {"AAPL": 105.0}
        mapes = compare_forecast_mapes(actual, prophet, current, {"AAPL": 0.05})
        assert mapes["prophet"] < mapes["naive"]

    def test_price_mape_zero_on_exact_match(self) -> None:
        actual = {"AAPL": 100.0}
        predicted = {"AAPL": 100.0}
        assert price_mape(actual, predicted) == 0.0

    def test_improvement_positive_when_prophet_better(self) -> None:
        assert prophet_improvement_vs_baseline(2.0, 3.0) == 1.0

    def test_win_rate(self) -> None:
        assert win_rate([1.0, 2.0], [2.0, 3.0]) == 1.0
        assert win_rate([3.0, 1.0], [2.0, 2.0]) == 0.5
