"""Generate mock prediction data for dashboard testing."""

from __future__ import annotations

import json

import pandas as pd


def generate_mock_portfolio_data() -> pd.DataFrame:
    """Generate mock portfolio prediction data for dashboard testing.

    Returns:
        DataFrame with columns: ticker, as_of_date, predicted_price, predicted_return,
        portfolio_weight, created_at, actual_prices_last_month (as JSON strings)
    """
    tickers = ["AMD", "MSFT", "AAPL", "TSLA", "AMZN", "NVDA", "META", "GOOG", "TSM", "JPM", "NFLX", "PLTR"]

    # Predicted prices from the pipeline
    predicted_prices = {
        "AMD": 368.05,
        "MSFT": 428.15,
        "AAPL": 302.23,
        "TSLA": 408.55,
        "AMZN": 265.25,
        "NVDA": 230.19,
        "META": 647.73,
        "GOOG": 394.34,
        "TSM": 419.11,
        "JPM": 307.36,
        "NFLX": 94.96,
        "PLTR": 135.33,
    }

    predicted_returns = {
        "AMD": -0.2573,
        "MSFT": 0.0375,
        "AAPL": -0.0277,
        "TSLA": -0.0722,
        "AMZN": -0.0243,
        "NVDA": 0.0828,
        "META": 0.0196,
        "GOOG": 0.0247,
        "TSM": -0.0086,
        "JPM": 0.0270,
        "NFLX": 0.0871,
        "PLTR": 0.0213,
    }

    portfolio_weights = {
        "AMD": 0.2351,
        "MSFT": 0.0500,
        "AAPL": 0.0506,
        "TSLA": 0.0500,
        "AMZN": 0.0500,
        "NVDA": 0.0500,
        "META": 0.0500,
        "GOOG": 0.1884,
        "TSM": 0.1259,
        "JPM": 0.0500,
        "NFLX": 0.0500,
        "PLTR": 0.0500,
    }

    # Generate price history (last 20 trading days with noise)
    import numpy as np
    np.random.seed(42)

    base_prices = {
        "AMD": 495.0,
        "MSFT": 412.5,
        "AAPL": 311.0,
        "TSLA": 440.5,
        "AMZN": 271.5,
        "NVDA": 212.5,
        "META": 635.0,
        "GOOG": 385.0,
        "TSM": 422.5,
        "JPM": 299.0,
        "NFLX": 87.0,
        "PLTR": 132.5,
    }

    records = []
    today = pd.Timestamp.now().normalize()

    # Create 5 historical records with different dates
    for day_offset in [4, 3, 2, 1, 0]:
        as_of_date = today - pd.Timedelta(days=day_offset)

        for ticker in tickers:
            # Generate price history
            price_history = []
            base = base_prices[ticker]
            for _i in range(20):
                # Add random walk with drift
                drift = -0.001 * predicted_returns[ticker]  # Reverse drift
                noise = np.random.normal(0, 0.02)
                base = base * (1 + drift + noise)
                price_history.append(float(base))

            records.append({
                "ticker": ticker,
                "as_of_date": as_of_date.date(),
                "predicted_price": float(predicted_prices[ticker]),
                "predicted_return": float(predicted_returns[ticker]),
                "portfolio_weight": float(portfolio_weights[ticker]),
                "created_at": as_of_date,
                "actual_prices_last_month": json.dumps(price_history),  # Store as JSON string
            })

    df = pd.DataFrame(records)
    return df


def save_mock_data_to_csv(output_path: str = "mock_predictions.csv") -> None:
    """Save mock data to CSV for manual Supabase import.

    Args:
        output_path: Path to save CSV file
    """
    df = generate_mock_portfolio_data()

    # Convert list to JSON string for CSV
    df_export = df.copy()
    df_export["actual_prices_last_month"] = df_export["actual_prices_last_month"].apply(
        lambda x: str(x)  # Convert list to string for CSV
    )

    df_export.to_csv(output_path, index=False)
    print(f"Mock data saved to {output_path}")


if __name__ == "__main__":
    df = generate_mock_portfolio_data()
    print("Mock Portfolio Data")
    print("=" * 100)
    print(df.head(12).to_string())
    print(f"\nTotal records: {len(df)}")
    print(f"\nUnique tickers: {df['ticker'].nunique()}")
    print(f"Dates: {sorted(df['as_of_date'].unique())}")

    save_mock_data_to_csv()
