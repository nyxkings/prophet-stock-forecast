"""Tests for Streamlit dashboard functionality."""

from __future__ import annotations

import json
from datetime import date

import pandas as pd
import pytest

from src.streamlit_app import (
    _parse_price_history,
    calculate_mae,
    calculate_mape,
    calculate_metrics,
    calculate_portfolio_metrics,
    calculate_rmse,
    create_correlation_matrix,
    create_cumulative_returns_chart,
    create_error_heatmap,
    create_returns_distribution,
    create_weight_history_chart,
    export_to_csv,
)


class TestMetricsCalculation:
    """Test metric calculation functions."""

    def test_calculate_mape(self):
        """Test MAPE calculation."""
        actual = pd.Series([100, 200, 300])
        predicted = pd.Series([110, 190, 310])

        mape = calculate_mape(actual, predicted)
        assert isinstance(mape, float)
        assert 0 <= mape <= 100
        # Expected: |10/100| + |10/200| + |10/300| = 0.1 + 0.05 + 0.033 ≈ 0.183
        # Mean: 0.183/3 ≈ 0.061 = 6.1%
        assert 5 < mape < 7

    def test_calculate_rmse(self):
        """Test RMSE calculation."""
        actual = pd.Series([100, 200, 300])
        predicted = pd.Series([110, 190, 310])

        rmse = calculate_rmse(actual, predicted)
        assert isinstance(rmse, float)
        assert rmse > 0
        # Expected: sqrt((100 + 100 + 100) / 3) = sqrt(100) = 10
        assert 9 < rmse < 11

    def test_calculate_mae(self):
        """Test MAE calculation."""
        actual = pd.Series([100, 200, 300])
        predicted = pd.Series([110, 190, 310])

        mae = calculate_mae(actual, predicted)
        assert isinstance(mae, float)
        assert mae > 0
        # Expected: (10 + 10 + 10) / 3 = 10
        assert 9 < mae < 11

    def test_calculate_metrics_full(self):
        """Test full metrics calculation."""
        perf_df = pd.DataFrame({
            "ticker": ["AAPL", "AAPL", "MSFT"],
            "actual_price": [100, 200, 300],
            "predicted_price": [110, 190, 310],
        })

        metrics = calculate_metrics(perf_df)

        assert metrics["mape"] > 0
        assert metrics["rmse"] > 0
        assert metrics["mae"] > 0
        assert metrics["count"] == 3

    def test_calculate_metrics_by_ticker(self):
        """Test metrics calculation for specific ticker."""
        perf_df = pd.DataFrame({
            "ticker": ["AAPL", "AAPL", "MSFT", "MSFT"],
            "actual_price": [100, 200, 300, 400],
            "predicted_price": [110, 190, 310, 390],
        })

        aapl_metrics = calculate_metrics(perf_df, "AAPL")
        assert aapl_metrics["count"] == 2

        msft_metrics = calculate_metrics(perf_df, "MSFT")
        assert msft_metrics["count"] == 2

    def test_calculate_metrics_empty(self):
        """Test metrics with empty dataframe."""
        perf_df = pd.DataFrame()

        metrics = calculate_metrics(perf_df)
        assert metrics["mape"] == 0.0
        assert metrics["rmse"] == 0.0
        assert metrics["mae"] == 0.0
        assert metrics["count"] == 0


class TestPortfolioMetrics:
    """Test portfolio-level metrics."""

    def test_calculate_portfolio_metrics(self):
        """Test portfolio metrics calculation."""
        perf_df = pd.DataFrame({
            "ticker": ["AAPL", "MSFT", "AAPL", "MSFT"],
            "actual_price": [100, 200, 105, 210],
            "predicted_price": [110, 190, 110, 200],
            "evaluation_date": [
                date(2024, 1, 1), date(2024, 1, 1),
                date(2024, 1, 2), date(2024, 1, 2),
            ],
        })

        metrics = calculate_portfolio_metrics(perf_df)

        assert isinstance(metrics, dict)
        # Should have Sharpe and volatility metrics if enough data
        if metrics:
            assert "sharpe_actual" in metrics or len(metrics) == 0

    def test_calculate_portfolio_metrics_empty(self):
        """Test portfolio metrics with empty data."""
        perf_df = pd.DataFrame()

        metrics = calculate_portfolio_metrics(perf_df)
        assert metrics == {}


class TestVisualizationFunctions:
    """Test visualization creation functions."""

    @pytest.fixture
    def perf_df(self):
        """Create sample performance dataframe."""
        return pd.DataFrame({
            "ticker": ["AAPL", "AAPL", "MSFT", "MSFT"],
            "evaluation_date": [
                date(2024, 1, 1), date(2024, 1, 2),
                date(2024, 1, 1), date(2024, 1, 2),
            ],
            "prediction_date": [
                date(2024, 1, 1), date(2024, 1, 2),
                date(2024, 1, 1), date(2024, 1, 2),
            ],
            "actual_price": [100, 105, 200, 210],
            "predicted_price": [110, 110, 190, 200],
            "error": [10, 5, -10, -10],
            "error_pct": [0.1, 0.05, -0.05, -0.05],
        })

    def test_create_error_heatmap(self, perf_df):
        """Test error heatmap creation."""
        fig = create_error_heatmap(perf_df)

        assert fig is not None
        assert fig.data[0].z is not None

    def test_create_error_heatmap_empty(self):
        """Test error heatmap with empty data."""
        fig = create_error_heatmap(pd.DataFrame())
        assert fig is None

    def test_create_correlation_matrix(self, perf_df):
        """Test correlation matrix creation."""
        fig = create_correlation_matrix(perf_df)

        # Should work with 2+ tickers
        assert fig is not None or len(perf_df["ticker"].unique()) < 2

    def test_create_correlation_matrix_single_ticker(self):
        """Test correlation matrix with single ticker."""
        perf_df = pd.DataFrame({
            "ticker": ["AAPL", "AAPL"],
            "evaluation_date": [date(2024, 1, 1), date(2024, 1, 2)],
            "error_pct": [0.1, 0.05],
        })

        fig = create_correlation_matrix(perf_df)
        assert fig is None  # Should return None for single ticker

    def test_create_returns_distribution(self, perf_df):
        """Test returns distribution creation."""
        fig = create_returns_distribution(perf_df, "AAPL")

        assert fig is not None
        assert len(fig.data) > 0

    def test_create_returns_distribution_empty_ticker(self, perf_df):
        """Test returns distribution for non-existent ticker."""
        fig = create_returns_distribution(perf_df, "GOOG")
        assert fig is None

    def test_create_cumulative_returns_chart(self, perf_df):
        """Test cumulative returns chart creation."""
        fig = create_cumulative_returns_chart(perf_df, "AAPL")

        assert fig is not None

    def test_create_weight_history_chart(self):
        """Test weight history chart creation."""
        df = pd.DataFrame({
            "ticker": ["AAPL", "MSFT", "AAPL", "MSFT"],
            "as_of_date": [
                date(2024, 1, 1), date(2024, 1, 1),
                date(2024, 1, 2), date(2024, 1, 2),
            ],
            "portfolio_weight": [0.5, 0.5, 0.6, 0.4],
        })

        fig = create_weight_history_chart(df)

        assert fig is not None
        assert len(fig.data) >= 2  # Should have traces for each ticker

    def test_create_weight_history_chart_empty(self):
        """Test weight history chart with empty data."""
        fig = create_weight_history_chart(pd.DataFrame())
        assert fig is None


class TestDataParsing:
    """Test data parsing and export functions."""

    def test_parse_price_history_list(self):
        """Test parsing price history from list."""
        prices = [100.5, 101.2, 102.3]

        result = _parse_price_history(prices)
        assert result == prices

    def test_parse_price_history_json_string(self):
        """Test parsing price history from JSON string."""
        prices_json = json.dumps([100.5, 101.2, 102.3])

        result = _parse_price_history(prices_json)
        assert result == [100.5, 101.2, 102.3]

    def test_parse_price_history_invalid(self):
        """Test parsing invalid price history."""
        result = _parse_price_history("invalid json")
        assert result == []

    def test_parse_price_history_none(self):
        """Test parsing None."""
        result = _parse_price_history(None)
        assert result == []

    def test_export_to_csv(self):
        """Test CSV export."""
        perf_df = pd.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "actual_price": [100, 200],
            "predicted_price": [110, 190],
        })

        date_df = pd.DataFrame({
            "ticker": ["AAPL", "MSFT"],
            "predicted_price": [110, 190],
            "predicted_return": [0.1, 0.05],
            "portfolio_weight": [0.5, 0.5],
        })

        csv_content = export_to_csv(perf_df, date_df)

        assert isinstance(csv_content, str)
        assert "PREDICTION PERFORMANCE" in csv_content
        assert "LATEST PORTFOLIO WEIGHTS" in csv_content
        assert "AAPL" in csv_content
        assert "MSFT" in csv_content


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_metrics_with_single_value(self):
        """Test metrics with single data point."""
        actual = pd.Series([100])
        predicted = pd.Series([110])

        mape = calculate_mape(actual, predicted)
        assert isinstance(mape, float)

    def test_metrics_with_identical_values(self):
        """Test metrics when prediction equals actual."""
        actual = pd.Series([100, 200, 300])
        predicted = pd.Series([100, 200, 300])

        mape = calculate_mape(actual, predicted)
        rmse = calculate_rmse(actual, predicted)
        mae = calculate_mae(actual, predicted)

        assert mape == 0.0
        assert rmse == 0.0
        assert mae == 0.0

    def test_metrics_with_negative_values(self):
        """Test metrics with negative price values."""
        actual = pd.Series([100, 200, -50])
        predicted = pd.Series([110, 190, -40])

        mae = calculate_mae(actual, predicted)
        assert isinstance(mae, float)
        assert mae >= 0

    def test_large_date_range(self):
        """Test with large date ranges."""
        df = pd.DataFrame({
            "ticker": ["AAPL"] * 100,
            "as_of_date": pd.date_range(start="2023-01-01", periods=100).date,
            "portfolio_weight": [0.5] * 100,
        })

        fig = create_weight_history_chart(df)
        assert fig is not None
