# API Documentation

Complete API reference for the Prophet Portfolio Optimization System.

## Table of Contents
1. [Core Modules](#core-modules)
2. [Data Models](#data-models)
3. [Usage Examples](#usage-examples)
4. [Error Handling](#error-handling)

---

## Core Modules

### `src.extractor` - Data Extraction

Handles fetching historical stock price data from Yahoo Finance.

#### `extract_data(tickers, start_date, end_date)`

Extracts historical OHLCV data for multiple stock tickers.

**Parameters:**
- `tickers` (list[str]): List of ticker symbols (e.g., ['AAPL', 'MSFT'])
- `start_date` (str): Start date in format 'YYYY-MM-DD'
- `end_date` (str): End date in format 'YYYY-MM-DD'

**Returns:**
- `dict[str, pd.DataFrame]`: Dictionary mapping ticker to DataFrame with columns:
  - `Close`: Closing price
  - Other OHLCV columns as returned by yfinance

**Raises:**
- `ValueError`: If no valid data can be extracted for any ticker

**Example:**
```python
from src.extractor import extract_data

data = extract_data(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    start_date='2023-01-01',
    end_date='2023-12-31'
)
# Returns: {'AAPL': DataFrame, 'MSFT': DataFrame, 'GOOGL': DataFrame}
```

---

### `src.processor` - Data Preprocessing

Aligns and prepares data for forecasting.

#### `preprocess_data(all_stock_data)`

Aligns historical data across multiple tickers by common trading dates.

**Parameters:**
- `all_stock_data` (dict[str, pd.DataFrame]): Raw ticker data from extractor

**Returns:**
- `dict[str, pd.DataFrame]`: Aligned data with columns:
  - `Price`: Closing price
  - `Returns`: Daily percentage returns

**Example:**
```python
from src.processor import preprocess_data

processed = preprocess_data(raw_data)
# All DataFrames now have identical date indices
```

#### `append_predictions(data, predictions, predicted_returns)`

Appends forecasted prices to historical data.

**Parameters:**
- `data` (dict[str, pd.DataFrame]): Historical processed data
- `predictions` (dict[str, float]): Predicted prices by ticker
- `predicted_returns` (dict[str, float]): Predicted returns by ticker

**Returns:**
- `dict[str, pd.DataFrame]`: Data with additional forecasted row

#### `collect_recent_prices(data, days=30)`

Extracts recent price history for visualization.

**Parameters:**
- `data` (dict[str, pd.DataFrame]): Processed data
- `days` (int): Number of recent trading days to collect

**Returns:**
- `dict[str, list[float]]`: Recent prices for each ticker

---

### `src.model` - Time Series Forecasting

Prophet-based forecasting for stock prices.

#### `ProphetModel()`

Wrapper around Facebook Prophet for one-step-ahead price forecasting.

**Methods:**

##### `fit(price_series)`

Trains Prophet model on historical price data.

**Parameters:**
- `price_series` (pd.Series): Historical prices with datetime index

**Returns:**
- `self`: For method chaining

**Features:**
- Automatically includes US trading holidays
- Configurable seasonality mode and changepoint prior scale
- Handles up to 3-year history for reliable trend detection

##### `predict_next(price_series)`

Predicts next day's price given historical data.

**Parameters:**
- `price_series` (pd.Series): Historical prices including current day

**Returns:**
- `float`: Predicted price for next trading day

**Example:**
```python
from src.model import ProphetModel
import pandas as pd

model = ProphetModel()
prices = pd.Series([100, 101, 102, ...], index=pd.date_range(...))

model.fit(prices)
next_price = model.predict_next(prices)
```

##### `predict_for_tickers(portfolio_data)`

Batch prediction for entire portfolio.

**Parameters:**
- `portfolio_data` (dict[str, pd.DataFrame]): Processed portfolio data

**Returns:**
- `tuple[dict[str, float], dict[str, float]]`: (predicted_prices, predicted_returns)

#### `_get_us_trading_holidays(start_year, end_year)`

Helper function to fetch US trading calendar holidays.

**Parameters:**
- `start_year` (int): Start year
- `end_year` (int): End year

**Returns:**
- `pd.DataFrame`: Holiday dates with Prophet-compatible format

---

### `src.optimiser` - Portfolio Optimization

Markowitz portfolio optimization with constraints.

#### `optimize_portfolio_mean_variance(data_dict, minimum_allocation=0.05, maximum_allocation=1.0, risk_aversion=5.0)`

Computes optimal portfolio weights using Markowitz mean-variance optimization.

**Parameters:**
- `data_dict` (dict[str, pd.DataFrame]): Portfolio data with Price and Returns columns
- `minimum_allocation` (float): Minimum weight per asset (default: 5%)
- `maximum_allocation` (float): Maximum weight per asset (default: 100%)
- `risk_aversion` (float): Risk aversion parameter λ (default: 5.0)
  - Higher values = more conservative (emphasize risk reduction)
  - Lower values = more aggressive (emphasize returns)

**Returns:**
- `dict[str, float]`: Portfolio weights summing to 1.0

**Constraints:**
- Sum of weights = 1.0 (fully invested portfolio)
- Each weight ∈ [minimum_allocation, maximum_allocation]
- Uses SciPy's SLSQP solver for constrained optimization

**Example:**
```python
from src.optimiser import optimize_portfolio_mean_variance

weights = optimize_portfolio_mean_variance(
    data_dict=portfolio_data,
    minimum_allocation=0.05,
    maximum_allocation=0.40,
    risk_aversion=3.0  # More aggressive
)
# Returns: {'AAPL': 0.35, 'MSFT': 0.40, 'GOOGL': 0.25}
```

---

### `src.database` - Persistence

Supabase integration for storing results.

#### `get_supabase_client()`

Creates authenticated Supabase client.

**Returns:**
- `supabase.Client`: Connected Supabase client

**Requires:**
- Environment variables: `SUPABASE_URL` and `SUPABASE_KEY`

**Raises:**
- `ValueError`: If credentials are missing

#### `save_results_to_supabase(result)`

Stores optimization results to database.

**Parameters:**
- `result` (dict): Must contain:
  - `date`: Optimization date
  - `predictions`: Dict of forecasted prices
  - `predicted_returns`: Dict of forecasted returns
  - `weights`: Dict of portfolio weights
  - `actual_prices_last_month`: Recent price history

**Returns:**
- Database response (list of inserted records)

**Example:**
```python
from src.database import save_results_to_supabase

result = {
    'date': date(2024, 5, 7),
    'predictions': {'AAPL': 150.25, 'MSFT': 300.50},
    'predicted_returns': {'AAPL': 0.015, 'MSFT': 0.020},
    'weights': {'AAPL': 0.35, 'MSFT': 0.65},
    'actual_prices_last_month': {'AAPL': [145, 148, 150.25]}
}

save_results_to_supabase(result)
```

---

### `src.main` - Orchestration

Main entry point for complete optimization pipeline.

#### `run_optimisation(tickers, start_date, end_date)`

Executes full pipeline: extract → preprocess → predict → optimize → save.

**Parameters:**
- `tickers` (list[str]): Portfolio ticker symbols
- `start_date` (str): Historical data start date (YYYY-MM-DD)
- `end_date` (str): Historical data end date (YYYY-MM-DD)

**Returns:**
- `dict`: Optimization result containing:
  - `date`: Execution date
  - `predictions`: Forecasted prices
  - `predicted_returns`: Forecasted returns
  - `weights`: Optimal portfolio allocation
  - `actual_prices_last_month`: Recent price history
- `dict`: Empty dict if pipeline fails

**Raises:**
- Gracefully catches and logs all errors; returns empty dict on failure

**Example:**
```python
from src.main import run_optimisation

result = run_optimisation(
    tickers=['AAPL', 'MSFT', 'GOOGL', 'AMZN'],
    start_date='2023-06-01',
    end_date='2024-05-06'
)

if result:
    print(f"Recommended weights: {result['weights']}")
else:
    print("Optimization failed")
```

---

### `src.settings` - Configuration

Global configuration constants.

**Available Settings:**

```python
PORTFOLIO_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA',
    'META', 'NVIDIA', 'BERKB', 'JPM', 'JNJ', 'V'
]

RISK_AVERSION = 5.0  # Risk-return trade-off parameter
MINIMUM_ALLOCATION = 0.05  # 5% minimum per asset
MAXIMUM_ALLOCATION = 1.0  # 100% maximum per asset
START_DATE = "2024-01-01"  # Default data start

PROPHET_PARAMS = {
    'seasonality_mode': 'multiplicative',
    'changepoint_prior_scale': 0.05,
    'seasonality_prior_scale': 10.0
}

SUPABASE_TABLE_NAME = "stock_optimisation_store"
```

---

## Data Models

### DataFrame Structure - Portfolio Data

```
Index: Date (datetime)
Columns:
  - Price (float): Asset closing price
  - Returns (float): Daily percentage return
```

### Result Dictionary Structure

```python
{
    'date': datetime.date,
    'predictions': {
        'TICKER1': float,  # Predicted price
        'TICKER2': float,
        ...
    },
    'predicted_returns': {
        'TICKER1': float,  # Predicted return
        'TICKER2': float,
        ...
    },
    'weights': {
        'TICKER1': float,  # Optimal allocation
        'TICKER2': float,
        ...
    },
    'actual_prices_last_month': {
        'TICKER1': [float, float, ...],  # Recent prices
        'TICKER2': [float, float, ...],
        ...
    }
}
```

---

## Usage Examples

### Complete Pipeline

```python
from src.main import run_optimisation
from datetime import date

# Run complete optimization
result = run_optimisation(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    start_date='2023-01-01',
    end_date='2024-05-06'
)

# Check results
if result:
    print(f"Date: {result['date']}")
    print(f"Predicted Prices: {result['predictions']}")
    print(f"Optimal Weights: {result['weights']}")
```

### Individual Module Usage

```python
from src.extractor import extract_data
from src.processor import preprocess_data
from src.model import ProphetModel
from src.optimiser import optimize_portfolio_mean_variance

# Extract data
raw_data = extract_data(['AAPL', 'MSFT'], '2023-01-01', '2024-05-06')

# Preprocess
portfolio = preprocess_data(raw_data)

# Forecast
model = ProphetModel()
predictions, predicted_returns = model.predict_for_tickers(portfolio)

# Optimize
weights = optimize_portfolio_mean_variance(portfolio)
```

---

## Error Handling

### Common Errors

**ValueError: No valid ticker data extracted**
- Cause: Invalid ticker symbols or date range
- Solution: Verify ticker symbols and date range validity

**RuntimeError: Model not fitted**
- Cause: Attempting predictions before fitting
- Solution: Call `model.fit()` before `predict_next()`

**ValueError: Missing SUPABASE credentials**
- Cause: Environment variables not set
- Solution: Set `SUPABASE_URL` and `SUPABASE_KEY`

**DateParseError: Invalid date format**
- Cause: Incorrect date string format
- Solution: Use 'YYYY-MM-DD' format

### Best Practices

1. **Always check return values**: Main pipeline returns empty dict on failure
2. **Set environment variables**: For Supabase integration
3. **Use appropriate date ranges**: At least 6 months of historical data recommended
4. **Monitor resource usage**: Large portfolios (100+ tickers) may require optimization tuning
5. **Handle API rate limits**: yfinance has rate limiting; use delays for bulk operations

---

## Version Information

- **Prophet**: 1.3.0
- **SciPy**: 1.17.1
- **Pandas**: 3.0.2
- **yfinance**: 1.3.0
- **Supabase**: 2.30.0

---

## See Also

- [Architecture Documentation](ARCHITECTURE.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Testing Guide](TESTING.md)
- [User Guide](USER_GUIDE.md)
