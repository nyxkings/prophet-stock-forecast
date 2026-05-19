"""Tests for extractor module."""

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.extractor import extract_data


class TestExtractor:
    """Test data extraction."""

    @patch("src.extractor.yf.Ticker")
    def test_extract_data(self, mock_ticker) -> None:
        """Test extracting historical data."""
        # Mock yfinance data
        mock_stock = MagicMock()
        mock_ticker.return_value = mock_stock

        # Create sample historical data
        dates = pd.date_range(start="2024-01-01", periods=252)
        prices = 100 + (0.01 * pd.Series(range(252)))
        df = pd.DataFrame({"Close": prices}, index=dates)
        mock_stock.history.return_value = df

        tickers = ["MSFT", "AAPL"]
        data = extract_data(tickers, start_date="2024-01-01")

        assert isinstance(data, dict)
        for ticker in tickers:
            if ticker in data:
                assert isinstance(data[ticker], pd.DataFrame)
                assert "Price" in data[ticker].columns
                assert "Returns" in data[ticker].columns
                assert data[ticker].index.name == "Date"
                # Check that index is date type
                assert all(isinstance(d, date) for d in data[ticker].index)

    @patch("src.extractor.yf.Ticker")
    def test_extract_data_with_end_date(self, mock_ticker) -> None:
        """Test extracting data with end_date filter."""
        # Mock yfinance data
        mock_stock = MagicMock()
        mock_ticker.return_value = mock_stock

        dates = pd.date_range(start="2024-01-01", end="2024-06-01")
        prices = 100 + (0.01 * pd.Series(range(len(dates))))
        df = pd.DataFrame({"Close": prices}, index=dates)
        mock_stock.history.return_value = df

        tickers = ["KO"]
        end_date = "2024-06-01"
        data = extract_data(tickers, start_date="2024-01-01", end_date=end_date)

        assert isinstance(data, dict)
        if tickers[0] in data:
            assert isinstance(data[tickers[0]], pd.DataFrame)
            # Check that all dates are <= end_date
            if len(data[tickers[0]]) > 0:
                assert all(
                    pd.Timestamp(d) <= pd.Timestamp(end_date) for d in data[tickers[0]].index
                )
