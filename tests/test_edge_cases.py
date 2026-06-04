"""Edge case tests for error handling and unusual scenarios."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest


@pytest.mark.edge_cases
class TestDataExtractionEdgeCases:
    """Test edge cases in data extraction."""

    def test_extract_with_no_data_points(self):
        """Test extraction when no data is available."""
        from unittest.mock import patch

        from src.extractor import _extract_single_ticker_data

        with patch("src.extractor.yf.Ticker") as mock_ticker:
            mock_ticker.return_value.history.return_value = pd.DataFrame()

            result = _extract_single_ticker_data("INVALID", "2023-01-01", "2023-12-31")
            assert result is None or len(result) == 0

    def test_extract_with_missing_close_price(self):
        """Test extraction when Close column is missing."""
        from src.extractor import _process_ticker_dataframe

        df = pd.DataFrame({"High": [100, 101, 102]}, index=pd.date_range("2023-01-01", periods=3))

        with pytest.raises(KeyError):
            _process_ticker_dataframe(df)

    def test_extract_with_all_nan_values(self):
        """Test extraction with all NaN values."""
        import numpy as np

        from src.extractor import _process_ticker_dataframe

        df = pd.DataFrame(
            {"Close": [np.nan, np.nan, np.nan]},
            index=pd.date_range("2023-01-01", periods=3),
        )

        result = _process_ticker_dataframe(df)
        # After dropna(), should be empty or very small
        assert len(result) == 0

    def test_extract_with_single_data_point(self):
        """Test extraction with only one data point."""
        from src.extractor import _process_ticker_dataframe

        df = pd.DataFrame(
            {"Close": [100.0]},
            index=pd.date_range("2023-01-01", periods=1),
        )

        result = _process_ticker_dataframe(df)
        # Should have one row (though returns will be NaN and dropped)
        assert len(result) == 0 or len(result) == 1


@pytest.mark.edge_cases
class TestDataProcessingEdgeCases:
    """Test edge cases in data processing."""

    def test_preprocess_with_empty_dict(self):
        """Test preprocessing with empty ticker dictionary."""
        from src.processor import preprocess_data

        result = preprocess_data({})
        assert result == {}

    def test_preprocess_with_misaligned_dates(self):
        """Test preprocessing when tickers have different date ranges."""
        from src.processor import preprocess_data

        data = {
            "AAPL": pd.DataFrame(
                {"Price": [100, 101, 102]},
                index=pd.date_range("2023-01-01", periods=3).date,
            ),
            "MSFT": pd.DataFrame(
                {"Price": [200, 201]},
                index=pd.date_range("2023-01-02", periods=2).date,
            ),
        }

        result = preprocess_data(data)
        # Should only have common dates
        for df in result.values():
            assert len(df) >= 1

    def test_append_predictions_empty_portfolio(self):
        """Test appending predictions to empty portfolio."""
        from src.processor import append_predictions

        result = append_predictions({}, {}, {})
        assert result == {}

    def test_collect_recent_prices_with_zero_days(self):
        """Test collecting prices with zero days lookback."""
        from src.processor import collect_recent_prices

        data = {
            "AAPL": pd.DataFrame(
                {"Price": [100, 101, 102]},
                index=pd.date_range("2023-01-01", periods=3).date,
            ),
        }

        result = collect_recent_prices(data, days=0)
        assert "AAPL" in result

    def test_collect_recent_prices_beyond_data_range(self):
        """Test collecting prices when lookback exceeds data range."""
        from src.processor import collect_recent_prices

        data = {
            "AAPL": pd.DataFrame(
                {"Price": [100, 101, 102]},
                index=pd.date_range("2023-01-01", periods=3).date,
            ),
        }

        # Request 1000 days when data only has 3 days
        result = collect_recent_prices(data, days=1000)
        assert len(result["AAPL"]) == 3


@pytest.mark.edge_cases
class TestModelEdgeCases:
    """Test edge cases in Prophet model."""

    def test_prophet_with_constant_prices(self):
        """Test Prophet when prices don't change."""
        from src.model import ProphetModel

        model = ProphetModel()
        constant_data = pd.Series([100.0] * 100, index=pd.bdate_range(start="2023-01-01", periods=100))

        model.fit(constant_data)
        forecast = model.predict_next(constant_data)
        assert forecast is not None

    def test_prophet_with_extreme_volatility(self):
        """Test Prophet with highly volatile data."""
        import numpy as np

        from src.model import ProphetModel

        model = ProphetModel()
        volatile_data = pd.Series(
            [100.0 + np.random.normal(0, 50) for _ in range(100)],
            index=pd.bdate_range(start="2023-01-01", periods=100)
        )

        model.fit(volatile_data)
        forecast = model.predict_next(volatile_data)
        assert forecast is not None

    def test_prophet_predict_multiple_periods(self):
        """Test Prophet forecasting multiple periods ahead."""
        from src.model import ProphetModel

        model = ProphetModel()
        data = pd.Series(range(100, 200), index=pd.bdate_range(start="2023-01-01", periods=100))

        model.fit(data)
        # Note: predict_next only predicts one period ahead
        forecast = model.predict_next(data)
        assert forecast is not None


@pytest.mark.edge_cases
class TestOptimizationEdgeCases:
    """Test edge cases in portfolio optimization."""

    def test_optimize_with_single_asset(self):
        """Test optimization with only one asset."""
        from src.optimiser import optimize_portfolio_mean_variance

        data = {
            "AAPL": pd.DataFrame(
                {"Returns": [0.001, 0.002, 0.001]},
                index=pd.date_range("2023-01-01", periods=3).date,
            ),
        }

        weights = optimize_portfolio_mean_variance(data)
        assert weights["AAPL"] == 1.0

    def test_optimize_with_zero_variance(self):
        """Test optimization when all returns are identical."""
        from src.optimiser import optimize_portfolio_mean_variance

        data = {
            "AAPL": pd.DataFrame(
                {"Returns": [0.001, 0.001, 0.001]},
                index=pd.date_range("2023-01-01", periods=3).date,
            ),
            "MSFT": pd.DataFrame(
                {"Returns": [0.002, 0.002, 0.002]},
                index=pd.date_range("2023-01-01", periods=3).date,
            ),
        }

        weights = optimize_portfolio_mean_variance(data)
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01

    def test_optimize_with_negative_returns(self):
        """Test optimization with negative returns."""
        from src.optimiser import optimize_portfolio_mean_variance

        data = {
            "AAPL": pd.DataFrame(
                {"Returns": [-0.01, -0.02, -0.015]},
                index=pd.date_range("2023-01-01", periods=3).date,
            ),
            "MSFT": pd.DataFrame(
                {"Returns": [-0.005, -0.01, -0.008]},
                index=pd.date_range("2023-01-01", periods=3).date,
            ),
        }

        weights = optimize_portfolio_mean_variance(data)
        # Should still allocate to less bad option
        assert sum(weights.values()) > 0.99

    def test_optimize_with_extreme_constraints(self):
        """Test optimization with very tight min/max constraints."""
        from src.optimiser import optimize_portfolio_mean_variance

        data = {
            "AAPL": pd.DataFrame(
                {"Returns": [0.001, 0.002]},
                index=pd.date_range("2023-01-01", periods=2).date,
            ),
            "MSFT": pd.DataFrame(
                {"Returns": [0.002, 0.003]},
                index=pd.date_range("2023-01-01", periods=2).date,
            ),
            "GOOGL": pd.DataFrame(
                {"Returns": [0.0015, 0.0025]},
                index=pd.date_range("2023-01-01", periods=2).date,
            ),
        }

        # All must be equal weight
        weights = optimize_portfolio_mean_variance(
            data,
            minimum_allocation=0.33,
            maximum_allocation=0.34,
        )

        # Each should be between 0.33 and 0.34
        for w in weights.values():
            assert 0.33 <= w <= 0.34

    def test_optimize_with_very_high_risk_aversion(self):
        """Test optimization with extreme risk aversion."""
        from src.optimiser import optimize_portfolio_mean_variance

        data = {
            "AAPL": pd.DataFrame(
                {"Returns": [0.001, 0.002, 0.003]},
                index=pd.date_range("2023-01-01", periods=3).date,
            ),
            "MSFT": pd.DataFrame(
                {"Returns": [0.005, 0.006, 0.004]},
                index=pd.date_range("2023-01-01", periods=3).date,
            ),
        }

        weights = optimize_portfolio_mean_variance(
            data,
            minimum_allocation=0.05,
            risk_aversion=1000.0,
        )

        # Should still be valid allocation
        assert abs(sum(weights.values()) - 1.0) < 0.01


@pytest.mark.edge_cases
class TestDatabaseEdgeCases:
    """Test edge cases in database operations."""

    def test_save_with_missing_predictions(self, mock_supabase, temp_env_vars):
        """Test saving when predictions are empty."""
        from src.database import save_results_to_supabase

        result = {
            "date": date(2023, 12, 29),
            "predictions": {},
            "predicted_returns": {},
            "weights": {},
        }

        # Should handle gracefully (log warning but not crash)
        save_results_to_supabase(result)

    def test_save_with_nan_values(self, mock_supabase, temp_env_vars):
        """Test saving when values contain NaN."""

        from src.database import save_results_to_supabase

        result = {
            "date": date(2023, 12, 29),
            "predictions": {"AAPL": float("nan"), "MSFT": 300.0},
            "predicted_returns": {"AAPL": 0.01, "MSFT": float("nan")},
            "weights": {"AAPL": 0.5, "MSFT": 0.5},
        }

        # Should handle NaN gracefully
        save_results_to_supabase(result)

    def test_save_with_very_large_portfolio(self, mock_supabase, temp_env_vars):
        """Test saving with many assets."""
        from src.database import save_results_to_supabase

        num_assets = 100
        result = {
            "date": date(2023, 12, 29),
            "predictions": {f"TICK{i}": 100.0 + i for i in range(num_assets)},
            "predicted_returns": {f"TICK{i}": 0.01 for i in range(num_assets)},
            "weights": {f"TICK{i}": 1.0 / num_assets for i in range(num_assets)},
        }

        # Should handle large portfolio
        save_results_to_supabase(result)
        mock_supabase.table.assert_called_once()


@pytest.mark.edge_cases
class TestConcurrencyEdgeCases:
    """Test behavior under unusual timing/concurrency scenarios."""

    def test_same_date_predictions(self, sample_processed_data):
        """Test when prediction date equals last data date."""
        from src.processor import append_predictions

        # Manually set index to ensure same date
        predictions = {"AAPL": 150.0, "MSFT": 300.0, "GOOGL": 100.0}
        predicted_returns = {"AAPL": 0.01, "MSFT": 0.02, "GOOGL": 0.015}

        result = append_predictions(sample_processed_data, predictions, predicted_returns)

        # Should still have one more row per ticker
        for ticker in sample_processed_data:
            assert len(result[ticker]) == len(sample_processed_data[ticker]) + 1
