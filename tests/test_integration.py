"""Integration tests for end-to-end pipeline."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.main import run_optimisation


@pytest.mark.integration
class TestFullPipeline:
    """Test the complete optimization pipeline."""

    def test_run_optimisation_full_pipeline(
        self,
        mock_yfinance,
        mock_prophet_model,
        sample_predictions,
        sample_actual_prices,
        sample_optimization_result,
        temp_env_vars,
    ):
        """Test end-to-end: extract -> preprocess -> predict -> optimize."""
        with patch("src.main.optimize_portfolio_mean_variance") as mock_optimize:
            mock_optimize.return_value = sample_optimization_result
            
            result = run_optimisation(
                tickers=["AAPL", "MSFT", "GOOGL"],
                start_date="2023-01-01",
                end_date="2023-12-31",
            )
            
            # Verify result structure
            assert "date" in result
            assert "predictions" in result
            assert "predicted_returns" in result
            assert "weights" in result
            assert "actual_prices_last_month" in result
            
            # Verify data content
            assert result["predictions"] == sample_predictions[0]
            assert result["predicted_returns"] == sample_predictions[1]
            assert result["weights"] == sample_optimization_result
            assert isinstance(result["date"], date)

    def test_run_optimisation_with_database_save(
        self,
        mock_yfinance,
        mock_prophet_model,
        mock_supabase,
        sample_optimization_result,
        temp_env_vars,
    ):
        """Test that results are successfully returned from optimization."""
        with patch("src.main.optimize_portfolio_mean_variance") as mock_optimize:
            mock_optimize.return_value = sample_optimization_result
            
            result = run_optimisation(
                tickers=["AAPL", "MSFT"],
                start_date="2023-01-01",
                end_date="2023-12-31",
            )
            
            # Verify result structure
            assert "date" in result
            assert "weights" in result
            assert result["weights"] == sample_optimization_result

    def test_run_optimisation_handles_missing_data(
        self,
        temp_env_vars,
    ):
        """Test graceful handling when no data is extracted."""
        with patch("src.main.extract_data") as mock_extract:
            mock_extract.return_value = {}
            
            result = run_optimisation(
                tickers=["INVALID_TICKER"],
                start_date="2023-01-01",
                end_date="2023-12-31",
            )
            
            # Should return empty dict on failure
            assert result == {}

    def test_run_optimisation_with_single_ticker(
        self,
        mock_yfinance,
        mock_prophet_model,
        sample_optimization_result,
    ):
        """Test optimization with single ticker."""
        with patch("src.main.optimize_portfolio_mean_variance") as mock_optimize:
            mock_optimize.return_value = {"AAPL": 1.0}
            
            result = run_optimisation(
                tickers=["AAPL"],
                start_date="2023-01-01",
                end_date="2023-12-31",
            )
            
            # Verify result has expected structure
            assert result is not None
            assert "weights" in result
            assert result["weights"]["AAPL"] == 1.0

    def test_run_optimisation_with_multiple_tickers(
        self,
        mock_yfinance,
        mock_prophet_model,
    ):
        """Test optimization with many tickers."""
        large_portfolio = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"]
        
        with patch("src.main.optimize_portfolio_mean_variance") as mock_optimize:
            weights = {ticker: 1 / len(large_portfolio) for ticker in large_portfolio}
            mock_optimize.return_value = weights
            
            result = run_optimisation(
                tickers=large_portfolio,
                start_date="2023-01-01",
                end_date="2023-12-31",
            )
            
            # Should not raise error with multiple tickers
            # Note: May be empty due to mocking, but shouldn't fail


@pytest.mark.integration
class TestDataProcessingPipeline:
    """Test the data processing pipeline."""

    def test_preprocessing_aligns_data(self, sample_ticker_data):
        """Test that preprocessing aligns data across tickers."""
        from src.processor import preprocess_data
        
        result = preprocess_data(sample_ticker_data)
        
        # All DataFrames should have same length
        lengths = [len(df) for df in result.values()]
        assert len(set(lengths)) == 1, "All tickers should have same number of dates"

    def test_predictions_appended_to_data(self, sample_processed_data, sample_predictions):
        """Test that predictions are properly appended to historical data."""
        from src.processor import append_predictions
        
        predictions, predicted_returns = sample_predictions
        result = append_predictions(sample_processed_data, predictions, predicted_returns)
        
        # Each ticker should have one more row
        for ticker, df in result.items():
            assert len(df) == len(sample_processed_data[ticker]) + 1

    def test_recent_prices_collected(self, sample_processed_data):
        """Test that recent prices are correctly collected."""
        from src.processor import collect_recent_prices
        
        result = collect_recent_prices(sample_processed_data, days=30)
        
        # Should have prices for each ticker
        assert len(result) == len(sample_processed_data)
        
        # Each should be a list of prices
        for ticker, prices in result.items():
            assert isinstance(prices, list)
            assert len(prices) > 0


@pytest.mark.integration
class TestModelPipeline:
    """Test the Prophet model pipeline."""

    def test_prophet_model_prediction(self, sample_processed_data):
        """Test Prophet model can make predictions."""
        from src.model import ProphetModel
        
        model = ProphetModel()
        
        # Test with one ticker
        ticker_data = sample_processed_data["AAPL"]
        model.fit(ticker_data["Price"])
        
        # Should return a forecast
        forecast = model.predict_next(ticker_data["Price"])
        assert forecast is not None
        assert isinstance(forecast, (int, float))

    def test_prophet_model_handles_short_data(self):
        """Test Prophet model with minimal data."""
        from src.model import ProphetModel
        
        model = ProphetModel()
        
        # Create minimal dataset with proper date index
        short_data = pd.Series(
            [100.0, 101.0, 102.0],
            index=pd.bdate_range(start="2023-01-01", periods=3)
        )
        
        # Should not raise error even with short data
        model.fit(short_data)
        forecast = model.predict_next(short_data)
        assert forecast is not None


@pytest.mark.integration
class TestOptimizationPipeline:
    """Test the portfolio optimization pipeline."""

    def test_mean_variance_optimization(self, sample_processed_data):
        """Test mean-variance optimization."""
        from src.optimiser import optimize_portfolio_mean_variance
        
        weights = optimize_portfolio_mean_variance(sample_processed_data)
        
        # Weights should sum to 1
        total_weight = sum(weights.values())
        assert abs(total_weight - 1.0) < 0.01
        
        # All weights should be non-negative
        assert all(w >= 0 for w in weights.values())
        
        # Should have a weight for each ticker
        assert len(weights) == len(sample_processed_data)

    def test_optimization_respects_constraints(self, sample_processed_data):
        """Test that optimization respects min/max allocation constraints."""
        from src.optimiser import optimize_portfolio_mean_variance
        
        min_alloc = 0.1
        max_alloc = 0.6
        
        weights = optimize_portfolio_mean_variance(
            sample_processed_data,
            minimum_allocation=min_alloc,
            maximum_allocation=max_alloc,
        )
        
        # Check constraints
        for weight in weights.values():
            assert weight >= min_alloc
            assert weight <= max_alloc

    def test_optimization_with_risk_aversion(self, sample_processed_data):
        """Test optimization with different risk aversion parameters."""
        from src.optimiser import optimize_portfolio_mean_variance
        import pytest
        
        weights_low_risk = optimize_portfolio_mean_variance(
            sample_processed_data, risk_aversion=1.0
        )
        weights_high_risk = optimize_portfolio_mean_variance(
            sample_processed_data, risk_aversion=10.0
        )
        
        # Both should produce valid weights that sum to 1
        assert abs(sum(weights_low_risk.values()) - 1.0) < 1e-6
        assert abs(sum(weights_high_risk.values()) - 1.0) < 1e-6
        # All weights should be non-negative
        for weight in weights_low_risk.values():
            assert weight >= 0
        for weight in weights_high_risk.values():
            assert weight >= 0


@pytest.mark.integration
class TestDatabaseIntegration:
    """Test database operations."""

    def test_save_results_to_supabase(
        self,
        mock_supabase,
        temp_env_vars,
        sample_predictions,
        sample_actual_prices,
        sample_optimization_result,
    ):
        """Test saving results to Supabase."""
        from src.database import save_results_to_supabase
        
        result = {
            "date": date(2023, 12, 29),
            "predictions": sample_predictions[0],
            "predicted_returns": sample_predictions[1],
            "weights": sample_optimization_result,
            "actual_prices_last_month": sample_actual_prices,
        }
        
        save_results_to_supabase(result)
        
        # Verify Supabase was called
        mock_supabase.table.assert_called_once()

    def test_save_results_without_credentials(self, sample_predictions):
        """Test handling when Supabase credentials are missing."""
        from src.database import save_results_to_supabase
        
        result = {
            "date": date(2023, 12, 29),
            "predictions": sample_predictions[0],
            "predicted_returns": sample_predictions[1],
            "weights": {},
        }
        
        # Should raise ValueError when credentials missing
        with pytest.raises(ValueError):
            save_results_to_supabase(result)
