"""Test utilities and helpers for common testing tasks."""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd


def create_sample_price_series(
    start_price: float = 100.0,
    num_days: int = 252,
    daily_volatility: float = 0.02,
    trend: float = 0.0001,
) -> pd.Series:
    """
    Create a sample price series with realistic properties.

    Args:
        start_price: Starting price
        num_days: Number of trading days
        daily_volatility: Daily volatility (std dev of returns)
        trend: Daily trend (drift)

    Returns:
        Series of prices
    """
    returns = np.random.normal(trend, daily_volatility, num_days)
    prices = start_price * np.exp(np.cumsum(returns))
    dates = pd.bdate_range(start="2023-01-01", periods=num_days)
    return pd.Series(prices, index=dates)


def create_correlated_portfolio(
    tickers: list[str],
    correlation_matrix: np.ndarray | None = None,
    num_days: int = 252,
) -> dict[str, pd.DataFrame]:
    """
    Create a portfolio with correlated assets.

    Args:
        tickers: List of ticker symbols
        correlation_matrix: Custom correlation matrix (uses default if None)
        num_days: Number of trading days

    Returns:
        Dictionary mapping ticker to DataFrame with Price and Returns
    """
    if correlation_matrix is None:
        # Default: moderate correlations
        n = len(tickers)
        correlation_matrix = np.eye(n) + 0.3 * (np.ones((n, n)) - np.eye(n))

    # Generate correlated returns
    cov_matrix = correlation_matrix  # Simplified; normally need to scale by std devs
    returns = np.random.multivariate_normal(
        mean=[0.0001] * len(tickers),
        cov=cov_matrix,
        size=num_days,
    )

    portfolio = {}
    dates = pd.bdate_range(start="2023-01-01", periods=num_days).date

    for i, ticker in enumerate(tickers):
        prices = 100 * np.exp(np.cumsum(returns[:, i]))
        df = pd.DataFrame(
            {
                "Price": prices,
                "Returns": returns[:, i],
            },
            index=dates,
        )
        portfolio[ticker] = df

    return portfolio


def assert_valid_weights(weights: dict[str, float], tolerance: float = 0.01) -> None:
    """
    Assert that portfolio weights are valid.

    Args:
        weights: Dictionary of ticker -> weight
        tolerance: Tolerance for sum (default: 0.01)

    Raises:
        AssertionError: If weights are invalid
    """
    total = sum(weights.values())
    assert abs(total - 1.0) < tolerance, f"Weights sum to {total}, expected ~1.0"

    for ticker, weight in weights.items():
        assert 0 <= weight <= 1, f"Weight for {ticker} is {weight}, should be [0,1]"


def assert_predictions_valid(
    predictions: dict[str, float],
    predicted_returns: dict[str, float],
    tickers: list[str],
) -> None:
    """
    Assert that predictions have valid structure and values.

    Args:
        predictions: Dictionary of ticker -> price
        predicted_returns: Dictionary of ticker -> return
        tickers: Expected tickers

    Raises:
        AssertionError: If predictions are invalid
    """
    assert len(predictions) == len(tickers), "Prediction count mismatch"
    assert len(predicted_returns) == len(tickers), "Return prediction count mismatch"

    for ticker in tickers:
        assert ticker in predictions, f"Missing prediction for {ticker}"
        assert ticker in predicted_returns, f"Missing return prediction for {ticker}"

        price = predictions[ticker]
        ret = predicted_returns[ticker]

        assert price > 0, f"Predicted price for {ticker} must be positive"
        assert -1 < ret < 10, f"Predicted return for {ticker} seems unrealistic: {ret}"


def compare_dataframes(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    rtol: float = 1e-5,
    atol: float = 1e-8,
) -> bool:
    """
    Compare two DataFrames for approximate equality.

    Args:
        df1: First DataFrame
        df2: Second DataFrame
        rtol: Relative tolerance
        atol: Absolute tolerance

    Returns:
        True if DataFrames are approximately equal
    """
    if df1.shape != df2.shape:
        return False

    if not (df1.columns == df2.columns).all():
        return False

    if not (df1.index == df2.index).all():
        return False

    return np.allclose(df1.values, df2.values, rtol=rtol, atol=atol)


def assert_dataframe_properties(
    df: pd.DataFrame,
    expected_columns: list[str] | None = None,
    expected_index_name: str | None = None,
    min_rows: int = 0,
) -> None:
    """
    Assert that a DataFrame has expected properties.

    Args:
        df: DataFrame to check
        expected_columns: Expected column names
        expected_index_name: Expected index name
        min_rows: Minimum number of rows

    Raises:
        AssertionError: If properties don't match
    """
    assert len(df) >= min_rows, f"DataFrame has {len(df)} rows, expected at least {min_rows}"

    if expected_columns:
        assert list(df.columns) == expected_columns, f"Column mismatch: {df.columns}"

    if expected_index_name:
        assert df.index.name == expected_index_name, f"Index name is {df.index.name}, expected {expected_index_name}"


def generate_test_dates(
    start: date | str = "2023-01-01",
    end: date | str = "2023-12-31",
    freq: str = "B",
) -> list[date]:
    """
    Generate date range for testing.

    Args:
        start: Start date
        end: End date
        freq: Frequency ('B' for business days, 'D' for daily)

    Returns:
        List of dates
    """
    date_range = pd.bdate_range(start=start, end=end, freq=freq)
    return date_range.date.tolist()


def create_test_result_dict(
    date: date = None,
    predictions: dict[str, float] | None = None,
    predicted_returns: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
    actual_prices_last_month: dict[str, list[float]] | None = None,
) -> dict[str, Any]:
    """
    Create a test result dictionary matching run_optimisation output.

    Args:
        date: Date of optimization
        predictions: Predicted prices
        predicted_returns: Predicted returns
        weights: Portfolio weights
        actual_prices_last_month: Recent price history

    Returns:
        Dictionary matching expected result format
    """
    if date is None:
        date = pd.Timestamp.now().date()

    if predictions is None:
        predictions = {"AAPL": 150.0, "MSFT": 300.0}

    if predicted_returns is None:
        predicted_returns = {k: 0.01 for k in predictions}

    if weights is None:
        n = len(predictions)
        weights = {k: 1.0 / n for k in predictions}

    if actual_prices_last_month is None:
        actual_prices_last_month = {k: [100.0 + i for i in range(20)] for k in predictions}

    return {
        "date": date,
        "predictions": predictions,
        "predicted_returns": predicted_returns,
        "weights": weights,
        "actual_prices_last_month": actual_prices_last_month,
    }
