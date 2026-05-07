# Architecture & Design Documentation

This document describes the system architecture, design decisions, and component interactions for the Prophet Portfolio Optimization system.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Main Pipeline (main.py)                     │
└────────────┬────────────────────────────────────────────────────┘
             │
             ├──► Data Layer (extractor.py)
             │    └─► yfinance API
             │
             ├──► Processing Layer (processor.py)
             │    └─► Data alignment & preprocessing
             │
             ├──► ML Layer (model.py)
             │    └─► Prophet forecasting
             │
             ├──► Optimization Layer (optimiser.py)
             │    └─► Markowitz portfolio optimization
             │
             └──► Persistence Layer (database.py)
                  └─► Supabase database
```

---

## Component Architecture

### 1. Data Extraction Layer (`src/extractor.py`)

**Purpose**: Fetch historical OHLCV data from external sources.

**Key Components:**
- `extract_data()`: Main function using yfinance library
- `_extract_single_ticker_data()`: Single ticker extraction
- `_process_ticker_dataframe()`: Data cleaning and validation

**Design Decisions:**
- **yfinance**: Chosen for reliable, free access to stock data
- **Error Handling**: Gracefully handles missing data for specific tickers
- **Caching**: Each extraction is fresh (no caching) to ensure current data

**Data Flow:**
```
Ticker → yfinance.Ticker() → OHLCV data → DataFrame → Clean & validate
```

**Performance:**
- ~3-5 seconds per ticker
- Scales linearly with number of tickers
- ~60 seconds for 12-ticker portfolio

---

### 2. Data Processing Layer (`src/processor.py`)

**Purpose**: Align and prepare data for forecasting.

**Key Components:**
- `preprocess_data()`: Date alignment across all tickers
- `append_predictions()`: Add forecast rows to historical data
- `collect_recent_prices()`: Extract recent price windows

**Design Decisions:**
- **Common Date Alignment**: All tickers must share common trading dates (addresses weekend/holiday misalignment)
- **Returns Calculation**: Percentage returns used for volatility estimation
- **Missing Data**: Tickers with insufficient overlap are excluded

**Data Flow:**
```
Raw Multi-Ticker Data
    ↓
Find common trading dates
    ↓
Align all tickers to common dates
    ↓
Calculate daily returns
    ↓
Processed DataFrame per ticker
```

**Why This Approach:**
- Ensures fair volatility comparison across tickers
- Handles stock splits and dividends implicitly (uses adjusted close)
- Removes market closure gaps automatically

---

### 3. ML/Forecasting Layer (`src/model.py`)

**Purpose**: Generate one-step-ahead price predictions.

**Architecture: Prophet Time Series Model**

Prophet is a decomposable time series model with components:
```
y(t) = g(t) + s(t) + h(t) + e(t)

Where:
  g(t) = Trend (piecewise linear growth with automatic changepoints)
  s(t) = Seasonality (yearly and weekly patterns)
  h(t) = Holiday effects (US trading holidays)
  e(t) = Error term
```

**Key Components:**
- `ProphetModel` class: Wrapper around Facebook Prophet
- `_get_us_trading_holidays()`: Integrates XNYS calendar
- `fit()`: Model training with holiday integration
- `predict_next()`: Single-step forecasting
- `predict_for_tickers()`: Batch forecasting

**Configuration:**
```python
PROPHET_PARAMS = {
    'seasonality_mode': 'multiplicative',      # For prices (not returns)
    'changepoint_prior_scale': 0.05,          # Flexibility in trend changes
    'seasonality_prior_scale': 10.0,          # Strength of seasonality
    'yearly_seasonality': True,                # Annual patterns
    'weekly_seasonality': True,                # Weekly patterns
    'daily_seasonality': False,                # Not applicable for daily data
    'interval_width': 0.95                     # 95% confidence intervals
}
```

**Design Decisions:**
- **Multiplicative Seasonality**: Prices have multiplicative seasonality (e.g., 2% seasonal effect on $100 = $2, on $200 = $4)
- **US Trading Holidays**: Accounts for market closures affecting patterns
- **Single-Step Forecasting**: Predicts next trading day only (reduces error accumulation)
- **No Auto-ARIMA**: Prophet handles trend/seasonality automatically, making auto-fitting unnecessary

**Prediction Flow:**
```
Historical Price Series
    ↓
Decompose into trend + seasonality + holidays + error
    ↓
Fit regression model for each component
    ↓
Generate one-day forecast
    ↓
Inverse transform (yhat) to get price prediction
```

---

### 4. Optimization Layer (`src/optimiser.py`)

**Purpose**: Compute optimal portfolio allocation.

**Markowitz Mean-Variance Optimization Problem**

```
Maximize: μᵀw - (λ/2)(wᵀΣw)

Subject to:
  Σwᵢ = 1
  wᵢ_min ≤ wᵢ ≤ wᵢ_max
  wᵢ ≥ 0
```

**Parameters:**
- `μ`: Expected returns vector (derived from price forecasts)
- `Σ`: Covariance matrix (estimated from historical returns)
- `w`: Portfolio weights (optimization variables)
- `λ`: Risk aversion parameter (higher = more conservative)

**Key Components:**
- `optimize_portfolio_mean_variance()`: Main optimization function
- Utilizes scipy.optimize.minimize with SLSQP algorithm

**Design Decisions:**
- **SLSQP Method**: Handles inequality constraints (allocation bounds)
- **Risk Aversion Parameter**: User-configurable (default=5.0)
  - Risk aversion = 1.0 → aggressive (emphasize returns)
  - Risk aversion = 10.0 → conservative (emphasize stability)
- **Covariance Estimation**: Rolling window from recent returns
- **Allocation Constraints**: 
  - Minimum: 5% per asset (avoid micro-allocations)
  - Maximum: 100% per asset (long-only portfolio)

**Optimization Flow:**
```
Expected Returns (from Prophet)
    ↓
Historical Returns Covariance Matrix
    ↓
Formulate objective function & constraints
    ↓
SciPy SLSQP solver
    ↓
Optimal Portfolio Weights
```

**Why This Approach:**
- Theoretically sound (Modern Portfolio Theory)
- Handles correlations between assets
- Computationally efficient (milliseconds for 12+ assets)
- Configurable risk profile

---

### 5. Persistence Layer (`src/database.py`)

**Purpose**: Store and retrieve optimization results.

**Architecture: Supabase (PostgreSQL + API)**

```
┌─────────────────┐
│   Supabase      │
├─────────────────┤
│  PostgreSQL DB  │
│   (Data Rows)   │
├─────────────────┤
│   REST API      │
│  (JSON access)  │
└─────────────────┘
```

**Database Schema:**
```sql
Table: stock_optimisation_store
├── id (UUID, Primary Key)
├── created_at (Timestamp)
├── date (Date)
├── ticker (String)
├── predicted_price (Float)
├── predicted_return (Float)
├── weight (Float)
├── actual_prices_last_month (JSONB Array)
└── metadata (JSONB, Optional)
```

**Key Components:**
- `get_supabase_client()`: Initialize authenticated client
- `save_results_to_supabase()`: Insert results (one row per ticker)

**Design Decisions:**
- **One Row Per Ticker**: Normalized structure for easy analysis
- **JSONB for Prices**: Flexible storage of time series data
- **UUID Primary Key**: Distributed system friendly
- **Timestamp Tracking**: Automatic created_at for audit trail

**Data Flow:**
```
Optimization Result
    ↓
Transform to row-per-ticker format
    ↓
Insert via Supabase REST API
    ↓
Database acknowledgment
```

---

### 6. Orchestration Layer (`src/main.py`)

**Purpose**: Coordinate all components into a complete pipeline.

**Pipeline Flow:**

```
INPUT: Tickers, Date Range
  ↓
1. EXTRACTION (2-5 sec)
   Extract historical data from yfinance
  ↓
2. PREPROCESSING (1-2 sec)
   Align dates, calculate returns
  ↓
3. VALIDATION (< 1 sec)
   Check data quality
  ↓
4. FORECASTING (5-10 sec)
   Train Prophet models, generate predictions
  ↓
5. OPTIMIZATION (< 1 sec)
   Solve Markowitz optimization problem
  ↓
6. PERSISTENCE (1-2 sec)
   Save results to Supabase
  ↓
OUTPUT: Portfolio weights + predictions
```

**Total Execution Time**: ~10-20 seconds

**Error Handling:**
- Graceful degradation (continues with available tickers)
- Comprehensive logging
- Returns empty dict on critical failures

---

## Data Flow Diagrams

### End-to-End Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ INPUT: tickers=['AAPL','MSFT'], dates=[2024-01-01, 2024-05-06] │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │  src.extractor.extract_data    │
         │  (yfinance API calls)          │
         └───────────────┬────────────────┘
                         │
                    Raw OHLCV Data
                         │
         ┌───────────────▼────────────────┐
         │ src.processor.preprocess_data  │
         │ (align, calculate returns)     │
         └───────────────┬────────────────┘
                         │
                 Aligned Price Data
                   + Returns Matrix
                         │
         ┌───────────────▼────────────────┐
         │ src.model.predict_for_tickers  │
         │ (Prophet forecasting)          │
         └───────────────┬────────────────┘
                         │
               Predictions + Returns
                         │
       ┌─────────────────▼──────────────────┐
       │ src.optimiser.optimize_portfolio   │
       │ (Markowitz optimization)           │
       └─────────────────┬──────────────────┘
                         │
                  Portfolio Weights
                         │
       ┌─────────────────▼──────────────────┐
       │ src.database.save_results_to_db    │
       │ (Supabase insertion)               │
       └─────────────────┬──────────────────┘
                         │
          ┌──────────────▼──────────────┐
          │  OUTPUT: Result Dictionary  │
          │  - date                     │
          │  - predictions              │
          │  - predicted_returns        │
          │  - weights                  │
          │  - actual_prices_last_month │
          └─────────────────────────────┘
```

---

## Technology Stack

### Data & Scientific Computing
- **pandas 3.0.2**: Data manipulation and time series handling
- **numpy 2.4.4**: Numerical computations and arrays
- **scipy 1.17.1**: Optimization (SLSQP solver)

### Time Series Forecasting
- **prophet 1.3.0**: Facebook's time series library
- **cmdstanpy 1.3.0**: Prophet's backend (Bayesian inference)
- **pandas_market_calendars 5.3.2**: Trading calendar holidays

### Data Sources & External APIs
- **yfinance 1.3.0**: Yahoo Finance data extraction
- **supabase 2.30.0**: Database as a service

### Testing & Quality
- **pytest 9.0.3**: Unit and integration testing
- **pytest-cov 7.1.0**: Coverage reporting
- **coverage 7.13.5**: Code coverage analysis

---

## Performance Characteristics

### Scaling
- **Time Complexity**: O(n) where n = number of tickers
- **Space Complexity**: O(n·m) where m = historical data points

### Typical Timings (12-ticker portfolio)
- Data extraction: 3-5 seconds
- Data preprocessing: 1-2 seconds
- Prophet model training: 5-10 seconds per ticker (parallel capable)
- Optimization: <1 second
- Database persistence: 1-2 seconds
- **Total**: 15-30 seconds

### Resource Usage
- **Memory**: ~500MB for typical portfolio
- **CPU**: Single-threaded (could parallelize Prophet training)
- **Network**: Minor (yfinance + Supabase)

---

## Security & Reliability

### Data Security
- Environment variables for credentials (Supabase)
- No credentials in code or git repository
- SSL/TLS for all API communications

### Error Resilience
- Graceful handling of missing ticker data
- Timeout protection on API calls
- Validation at each pipeline stage

### Data Integrity
- Transaction-like semantics (all-or-nothing per optimization run)
- Atomic database inserts
- Audit trail via created_at timestamps

---

## Future Improvements

### Performance Optimization
- Parallel Prophet model training (async)
- Caching historical data locally
- Incremental covariance matrix updates

### Robustness
- Multi-day ahead forecasting (with uncertainty)
- Robust optimization (mean-absolute deviation)
- Tail risk optimization (CVaR)

### Features
- Transaction costs modeling
- Rebalancing frequency optimization
- Multi-asset class support (bonds, crypto, commodities)

---

## Design Principles

1. **Modularity**: Each component has single responsibility
2. **Testability**: 57+ unit and integration tests
3. **Observability**: Comprehensive logging throughout
4. **Configurability**: Settings exposed in `src/settings.py`
5. **Graceful Degradation**: Continues with available data on errors
6. **Type Safety**: Type hints throughout codebase

---

See Also:
- [API Documentation](API.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Testing Guide](TESTING.md)
- [User Guide](USER_GUIDE.md)
