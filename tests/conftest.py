"""Shared pytest fixtures and configuration for all tests."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@pytest.fixture
def sample_ticker_data() -> dict[str, pd.DataFrame]:
    """Create sample ticker data for testing."""
    dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="B")
    
    sample_data = {}
    for ticker in ["AAPL", "MSFT", "GOOGL"]:
        prices = 100 + (hash(ticker) % 50)  # Vary starting price by ticker
        data = {
            "Close": [prices + i * 0.5 for i in range(len(dates))],
        }
        df = pd.DataFrame(data, index=dates)
        df.index.name = "Date"
        sample_data[ticker] = df
    
    return sample_data


@pytest.fixture
def sample_processed_data() -> dict[str, pd.DataFrame]:
    """Create sample processed data with Price and Returns columns."""
    dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="B").date
    
    processed_data = {}
    for ticker in ["AAPL", "MSFT", "GOOGL"]:
        prices = [100 + i * 0.5 for i in range(len(dates))]
        returns = [0.001 + (i % 100) * 0.00001 for i in range(len(dates))]
        
        data = {
            "Price": prices,
            "Returns": returns,
        }
        df = pd.DataFrame(data, index=dates)
        df.index.name = "Date"
        processed_data[ticker] = df
    
    return processed_data


@pytest.fixture
def sample_predictions() -> tuple[dict[str, float], dict[str, float]]:
    """Create sample price predictions and predicted returns."""
    predictions = {
        "AAPL": 150.25,
        "MSFT": 300.50,
        "GOOGL": 100.75,
    }
    predicted_returns = {
        "AAPL": 0.015,
        "MSFT": 0.020,
        "GOOGL": 0.010,
    }
    return predictions, predicted_returns


@pytest.fixture
def sample_actual_prices() -> dict[str, list[float]]:
    """Create sample actual price history."""
    return {
        "AAPL": [148.0, 149.0, 150.0, 151.0, 150.5],
        "MSFT": [298.0, 299.0, 300.0, 301.0, 300.5],
        "GOOGL": [98.0, 99.0, 100.0, 101.0, 100.5],
    }


@pytest.fixture
def sample_optimization_result() -> dict[str, float]:
    """Create sample portfolio optimization result."""
    return {
        "AAPL": 0.35,
        "MSFT": 0.40,
        "GOOGL": 0.25,
    }


@pytest.fixture
def mock_yfinance(sample_ticker_data):
    """Mock yfinance.Ticker to avoid API calls during testing."""
    with patch("src.extractor.yf.Ticker") as mock_ticker:
        def create_mock_ticker(ticker: str):
            mock_obj = MagicMock()
            mock_obj.history.return_value = sample_ticker_data.get(
                ticker, 
                pd.DataFrame({"Close": [100]})
            )
            return mock_obj
        
        mock_ticker.side_effect = create_mock_ticker
        yield mock_ticker


@pytest.fixture
def mock_supabase():
    """Mock Supabase client to avoid database calls during testing."""
    with patch("src.database.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        
        # Mock the insert chain
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[])
        
        yield mock_client


@pytest.fixture
def mock_prophet_model(sample_predictions, sample_actual_prices):
    """Mock ProphetModel to avoid training during testing."""
    with patch("src.main.ProphetModel") as mock_prophet_class:
        mock_instance = MagicMock()
        mock_prophet_class.return_value = mock_instance
        
        predictions, predicted_returns = sample_predictions
        mock_instance.predict_for_tickers.return_value = (predictions, predicted_returns)
        
        yield mock_instance


@pytest.fixture
def temp_env_vars(monkeypatch):
    """Set up temporary environment variables for testing."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test_key_12345")
    return monkeypatch


@pytest.fixture
def caplog_handler(caplog):
    """Configure caplog to capture all log levels."""
    caplog.set_level("DEBUG")
    return caplog
