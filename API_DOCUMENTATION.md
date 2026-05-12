# API Documentation

Complete reference for all modules and functions in the Prophet Stock Forecasting application.

---

## Table of Contents

1. [Extractor Module](#extractor-module)
2. [Processor Module](#processor-module)
3. [Model Module](#model-module)
4. [Optimiser Module](#optimiser-module)
5. [Database Module](#database-module)
6. [Settings Module](#settings-module)
7. [Main Orchestration](#main-orchestration)

---

## Extractor Module

**File:** `src/extractor.py`

**Purpose:** Fetches historical stock price data from Yahoo Finance using the `yfinance` library.

### Functions

#### `extract_data(tickers, start_date, end_date)`

Extracts historical price data for multiple tickers.

**Parameters:**
- `tickers` (list[str]): List of stock ticker symbols (e.g., `["AAPL", "MSFT", "GOOGL"]`)
- `start_date` (str): Start date in ISO format `"YYYY-MM-DD"` (e.g., `"2023-01-01"`)
- `end_date` (str): End date in ISO format `"YYYY-MM-DD"` (e.g., `"2023-12-31"`)

**Returns:**
- `dict[str, pd.DataFrame]`: Dictionary mapping ticker to DataFrame with columns:
  - `Price`: Closing price
  - `Returns`: Daily returns (calculated as percentage change)
  
**Raises:**
- `ValueError`: If date format is invalid
- `KeyError`: If ticker data is unavailable

**Example:**
```python
from src.extractor import extract_data

data = extract_data(
    tickers=["AAPL", "MSFT", "GOOGL"],
    start_date="2023-01-01",
    end_date="2023-12-31"
)

# Access data for specific ticker
aapl_data = data["AAPL"]
print(aapl_data.head())
```

---

## Processor Module

**File:** `src/processor.py`

**Purpose:** Aligns, preprocesses, and transforms stock data across multiple tickers.

### Functions

#### `preprocess_data(all_stock_data)`

Aligns price data across multiple tickers by finding common trading dates.

**Parameters:**
- `all_stock_data` (dict[str, pd.DataFrame]): Dictionary mapping ticker to DataFrame with `Price` column

**Returns:**
- `dict[str, pd.DataFrame]`: Dictionary with aligned data containing `Price` and `Returns` columns

**Example:**
```python
from src.processor import preprocess_data
from src.extractor import extract_data

raw_data = extract_data(["AAPL", "MSFT"], "2023-01-01", "2023-12-31")
aligned_data = preprocess_data(raw_data)

# All tickers now have same date range
print(len(aligned_data["AAPL"]) == len(aligned_data["MSFT"]))  # True
```

#### `append_predictions(portfolio_data, predictions, predicted_returns)`

Appends predicted prices and returns to historical data.

**Parameters:**
- `portfolio_data` (dict[str, pd.DataFrame]): Historical portfolio data
- `predictions` (dict[str, float]): Predicted prices {ticker: price}
- `predicted_returns` (dict[str, float]): Predicted returns {ticker: return_pct}

**Returns:**
- `dict[str, pd.DataFrame]`: Data with prediction row appended

**Example:**
```python
from src.processor import append_predictions

predictions = {"AAPL": 150.25, "MSFT": 300.50}
predicted_returns = {"AAPL": 0.015, "MSFT": 0.020}

predicted_data = append_predictions(
    portfolio_data, 
    predictions, 
    predicted_returns
)
```

#### `collect_recent_prices(data, days=20)`

Extracts recent price history for analysis.

**Parameters:**
- `data` (dict[str, pd.DataFrame]): Portfolio data with `Price` column
- `days` (int): Number of recent trading days to collect (default: 20)

**Returns:**
- `dict[str, list[float]]`: Recent prices {ticker: [price1, price2, ...]}

**Example:**
```python
from src.processor import collect_recent_prices

recent = collect_recent_prices(portfolio_data, days=30)
print(f"Recent AAPL prices: {recent['AAPL']}")
```

---

## Model Module

**File:** `src/model.py`

**Purpose:** Time series forecasting using Facebook's Prophet model with US trading holidays.

### ProphetModel Class

Wrapper around Facebook Prophet for one-step forward prediction.

#### `__init__()`

Initialize ProphetModel instance.

**Example:**
```python
from src.model import ProphetModel

model = ProphetModel()
```

#### `fit(price_series)`

Fit Prophet model to historical price data.

**Parameters:**
- `price_series` (pd.Series): Historical prices with datetime index

**Returns:**
- `self`: ProphetModel instance for method chaining

**Example:**
```python
# price_series has datetime index
model.fit(price_series)
```

#### `predict_next(price_series)`

Predict next day's price given historical data.

**Parameters:**
- `price_series` (pd.Series): Historical prices with datetime index

**Returns:**
- `float`: Predicted price for next trading day

**Example:**
```python
next_price = model.predict_next(price_series)
print(f"Predicted AAPL price: ${next_price:.2f}")
```

#### `predict_for_tickers(portfolio_data)`

Predict next day's price for multiple tickers.

**Parameters:**
- `portfolio_data` (dict[str, pd.DataFrame]): Portfolio data {ticker: DataFrame}

**Returns:**
- `tuple[dict[str, float], dict[str, float]]`: 
  - Predictions {ticker: predicted_price}
  - Predicted returns {ticker: return_pct}

**Example:**
```python
predictions, returns = model.predict_for_tickers(portfolio_data)

print(f"Predicted prices: {predictions}")
print(f"Predicted returns: {returns}")
```

### Module-Level Functions

#### `_get_us_trading_holidays(start_year=2020, end_year=2030)`

Fetch US stock market trading holidays.

**Parameters:**
- `start_year` (int): Start year for holidays (default: 2020)
- `end_year` (int): End year for holidays (default: 2030)

**Returns:**
- `pd.DataFrame`: DataFrame with columns `holiday`, `ds`, `lower_window`, `upper_window`

**Example:**
```python
from src.model import _get_us_trading_holidays

holidays = _get_us_trading_holidays(2023, 2024)
print(f"Found {len(holidays)} trading holidays")
```

---

## Optimiser Module

**File:** `src/optimiser.py`

**Purpose:** Portfolio optimization using Markowitz mean-variance optimization with constraints.

### Functions

#### `optimize_portfolio_mean_variance(data_dict, minimum_allocation=0.05, maximum_allocation=1.0, risk_aversion=5)`

Calculate optimal portfolio weights using Markowitz optimization.

**Parameters:**
- `data_dict` (dict[str, pd.DataFrame]): Portfolio data with `Returns` column
- `minimum_allocation` (float): Minimum weight per asset (default: 0.05 = 5%)
- `maximum_allocation` (float): Maximum weight per asset (default: 1.0 = 100%)
- `risk_aversion` (float): Risk aversion coefficient (default: 5)

**Returns:**
- `dict[str, float]`: Optimal weights {ticker: weight}, where sum(weights) = 1.0

**Constraints:**
- Sum of weights = 1.0 (fully invested)
- Each weight ≥ `minimum_allocation`
- Each weight ≤ `maximum_allocation`

**Example:**
```python
from src.optimiser import optimize_portfolio_mean_variance

weights = optimize_portfolio_mean_variance(
    portfolio_data,
    minimum_allocation=0.05,
    maximum_allocation=0.40,
    risk_aversion=5.0
)

# Display results
for ticker, weight in weights.items():
    print(f"{ticker}: {weight*100:.2f}%")
```

**Mathematical Foundation:**

The optimization minimizes:
```
f(w) = -w^T * μ + (λ/2) * w^T * Σ * w

where:
- w = portfolio weights
- μ = expected returns (predicted next-day returns)
- Σ = covariance matrix of returns
- λ = risk_aversion parameter
```

---

## Database Module

**File:** `src/database.py`

**Purpose:** Supabase integration for storing and retrieving portfolio optimization results.

### Functions

#### `get_supabase_client()`

Initialize and return Supabase client.

**Returns:**
- `supabase.Client | None`: Supabase client if credentials available, None otherwise

**Environment Variables Required:**
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Your Supabase API key

**Example:**
```python
from src.database import get_supabase_client

supabase = get_supabase_client()
if supabase:
    print("Connected to Supabase")
else:
    print("Supabase credentials not configured")
```

#### `save_results_to_supabase(result)`

Save optimization results to Supabase database.

**Parameters:**
- `result` (dict): Optimization result containing:
  - `date`: Optimization date
  - `predictions`: Predicted prices {ticker: price}
  - `predicted_returns`: Predicted returns {ticker: return}
  - `weights`: Portfolio weights {ticker: weight}
  - `actual_prices_last_month`: Historical prices {ticker: [prices]}

**Returns:**
- `bool`: True if save successful, False if Supabase unavailable

**Database Schema:**

Table: `stock_optimisation_store`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key (auto-generated) |
| created_at | timestamp | Creation timestamp |
| run_date | date | Date of optimization run |
| ticker | text | Stock ticker symbol |
| predicted_price | float | Predicted next-day price |
| predicted_return | float | Predicted return percentage |
| optimal_weight | float | Recommended portfolio weight |
| recent_prices | jsonb | Last 20 trading day prices |

**Example:**
```python
from src.database import save_results_to_supabase

result = {
    "date": "2023-12-31",
    "predictions": {"AAPL": 150.25, "MSFT": 300.50},
    "predicted_returns": {"AAPL": 0.015, "MSFT": 0.020},
    "weights": {"AAPL": 0.50, "MSFT": 0.50},
    "actual_prices_last_month": {"AAPL": [...], "MSFT": [...]}
}

success = save_results_to_supabase(result)
print("Results saved!" if success else "Failed to save results")
```

---

## Settings Module

**File:** `src/settings.py`

**Purpose:** Configuration constants for the entire application.

### Configuration Variables

#### Portfolio Configuration

```python
PORTFOLIO_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META',
    'TSLA', 'JPM', 'JNJ', 'V', 'WMT', 'XOM'
]
```
List of stock tickers to include in optimization.

#### Optimization Parameters

```python
RISK_AVERSION = 5
MINIMUM_ALLOCATION = 0.05  # 5% minimum per asset
MAXIMUM_ALLOCATION = 1.0   # 100% maximum per asset
```

#### Date Range

```python
START_DATE = "2024-01-01"
END_DATE = "2024-12-31"
```

#### Prophet Model Parameters

```python
PROPHET_PARAMS = {
    'yearly_seasonality': True,
    'weekly_seasonality': False,
    'daily_seasonality': False,
    'seasonality_mode': 'multiplicative',
    'changepoint_prior_scale': 0.05,
    'interval_width': 0.95
}
```

#### Database Configuration

```python
SUPABASE_TABLE_NAME = "stock_optimisation_store"
```

---

## Main Orchestration

**File:** `src/main.py`

**Purpose:** Orchestrates the entire pipeline from data extraction to portfolio optimization.

### Functions

#### `run_optimisation(tickers, start_date, end_date)`

Execute complete portfolio optimization pipeline.

**Pipeline Steps:**
1. Extract historical data using yfinance
2. Preprocess and align data across tickers
3. Generate predictions using Prophet model
4. Collect recent price history
5. Calculate optimal portfolio weights
6. Log and return results

**Parameters:**
- `tickers` (list[str]): Stock tickers to optimize
- `start_date` (str): Historical data start date `"YYYY-MM-DD"`
- `end_date` (str): Historical data end date `"YYYY-MM-DD"`

**Returns:**
- `dict`: Optimization result containing:
  - `date`: Optimization date
  - `predictions`: Predicted prices {ticker: price}
  - `predicted_returns`: Predicted returns {ticker: return}
  - `weights`: Portfolio weights {ticker: weight}
  - `actual_prices_last_month`: Recent price history {ticker: [prices]}
- Empty `dict`: If extraction fails

**Raises:**
- Logs warnings/errors but returns empty dict gracefully

**Example:**
```python
from src.main import run_optimisation
from src.database import save_results_to_supabase

result = run_optimisation(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    start_date='2023-01-01',
    end_date='2023-12-31'
)

if result:
    print(f"Optimal weights on {result['date']}:")
    for ticker, weight in result['weights'].items():
        print(f"  {ticker}: {weight*100:.2f}%")
    
    # Save to database
    save_results_to_supabase(result)
else:
    print("Optimization failed - no data")
```

**Execution Flow:**

```
┌─────────────────────────────────────────────────────────┐
│ run_optimisation(tickers, start_date, end_date)        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │  Extract Data       │
        │  (yfinance)         │
        └────────┬────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │  Preprocess Data    │
        │  (Align dates)      │
        └────────┬────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │  Generate Predictions
        │  (Prophet Model)    │
        └────────┬────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │  Collect Recent     │
        │  Prices             │
        └────────┬────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │  Optimize Portfolio │
        │  (Markowitz)        │
        └────────┬────────────┘
                 │
                 ▼
        ┌─────────────────────┐
        │  Return Results     │
        │  & Log Metrics      │
        └─────────────────────┘
```

---

## Error Handling

All modules implement graceful error handling:

### Common Error Scenarios

#### Missing Data
```python
# Returns empty dict if ticker not found
result = run_optimisation(['INVALID'], '2023-01-01', '2023-12-31')
if not result:
    print("No data available for tickers")
```

#### Date Issues
```python
# Automatically handles misaligned dates
portfolio_data = preprocess_data(extracted_data)  # Finds common dates
```

#### Database Unavailable
```python
# Gracefully handles Supabase connection failures
success = save_results_to_supabase(result)
if not success:
    print("Could not save to database - API credentials missing")
```

#### Model Fitting Issues
```python
# ProphetModel handles short data and special cases
model = ProphetModel()
model.fit(short_data)  # Works even with limited data
```

---

## Dependencies

### Core Libraries
- **pandas** (3.0.2): Data manipulation and time series
- **numpy** (2.4.4): Numerical computations
- **scipy** (1.17.1): Optimization and statistical functions
- **yfinance** (1.3.0): Stock data fetching
- **prophet** (1.3.0): Time series forecasting

### Database
- **supabase** (2.30.0): Database client

### Utilities
- **pandas_market_calendars** (5.3.2): Trading calendar support
- **python-dateutil**: Date/time utilities

---

## Environment Setup

Required environment variables:
```bash
# Supabase (optional)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Optional: customize portfolio
PORTFOLIO_TICKERS=AAPL,MSFT,GOOGL,AMZN
```

---

## Version Information

- **Application Version**: 0.1.0
- **Python Version**: 3.12.3+
- **Last Updated**: May 2026

---

## Support & Contributing

For issues, questions, or contributions, please:
1. Check existing documentation in the `/docs` folder
2. Review test cases in `/tests` for usage examples
3. Submit issues to the GitHub repository

