# Architecture Documentation

System design, component interactions, and technical decisions for the Prophet Portfolio Optimization application.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow](#data-flow)
4. [Module Interactions](#module-interactions)
5. [Technology Stack](#technology-stack)
6. [Design Patterns](#design-patterns)
7. [Performance Considerations](#performance-considerations)
8. [Scalability & Future Growth](#scalability--future-growth)

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interface Layer                      │
│         (Streamlit Dashboard + CLI + API)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Application Orchestration                       │
│              (main.py - run_optimisation)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼────────┐      ┌────────▼──────────┐
│  Data Pipeline │      │  Optimization     │
├────────────────┤      │  Pipeline         │
│ • Extraction   │      ├───────────────────┤
│ • Processing   │      │ • Model Fitting   │
│ • Prediction   │      │ • Weight Calc     │
└────────────────┘      │ • Constraints     │
        │               └───────────────────┘
        │                         │
        └────────────┬────────────┘
                     │
        ┌────────────▼────────────┐
        │   Storage Layer         │
        │   (Supabase Database)   │
        └─────────────────────────┘
```

### Key Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Extractor** | Fetch stock data | yfinance |
| **Processor** | Data alignment | pandas |
| **Model** | Price forecasting | Prophet (Facebook) |
| **Optimiser** | Portfolio optimization | scipy.optimize |
| **Database** | Result storage | Supabase (PostgreSQL) |
| **Dashboard** | Visualization | Streamlit |
| **Orchestrator** | Pipeline coordination | Python |

---

## Component Architecture

### 1. Data Extraction Layer (`src/extractor.py`)

**Responsibility:** Fetch historical stock data from external sources

**Functions:**
- `extract_data(tickers, start_date, end_date)`
  - Fetches OHLCV data from Yahoo Finance
  - Handles missing tickers gracefully
  - Returns aligned DataFrames

**Design Decisions:**
- ✅ Use yfinance: Free, reliable, no API key required
- ✅ Cache at application level: Reduce API calls
- ✅ Handle missing data: Skip unavailable tickers
- ❌ Don't use paid financial APIs: Cost + complexity

**Dependencies:**
- `yfinance`: Stock data provider
- `pandas`: Data structure

**Error Handling:**
```
Missing ticker → Skip ticker, continue with others
Network timeout → Return empty dict
Invalid date range → Raise ValueError
```

---

### 2. Data Processing Layer (`src/processor.py`)

**Responsibility:** Transform and align data for analysis

**Functions:**
- `preprocess_data(all_stock_data)`
  - Find common trading dates across all tickers
  - Align DataFrames to common date range
  - Calculate returns from prices

- `append_predictions(portfolio_data, predictions, predicted_returns)`
  - Extend historical data with next-day prediction
  - Maintain DataFrame structure

- `collect_recent_prices(data, days=20)`
  - Extract recent price history
  - Used for dashboard visualization

**Design Decisions:**
- ✅ Align by common dates: Ensures comparability
- ✅ Calculate returns: Needed for covariance
- ✅ Dict-based structure: Flexible ticker handling
- ❌ Don't normalize prices: Keep original scale

**Dependencies:**
- `pandas`: Data manipulation

**Data Structure:**
```python
portfolio_data = {
    'AAPL': pd.DataFrame({
        'Price': [145.0, 145.5, 146.0, ...],
        'Returns': [0.0034, 0.0021, -0.0015, ...]
    }, index=pd.DatetimeIndex([...])),
    'MSFT': {...},
    ...
}
```

---

### 3. Forecasting Layer (`src/model.py`)

**Responsibility:** Predict future stock prices using time series models

**Class:** `ProphetModel`

**Methods:**
- `fit(price_series)`: Train Prophet on historical data
- `predict_next(price_series)`: Predict next day's price
- `predict_for_tickers(portfolio_data)`: Batch predict

**Model Configuration:**
```python
PROPHET_PARAMS = {
    'yearly_seasonality': True,      # Capture yearly patterns
    'weekly_seasonality': False,     # Stock markets don't have weekly seasonality
    'daily_seasonality': False,      # Too granular for daily predictions
    'seasonality_mode': 'multiplicative',  # Multiplicative seasonality
    'changepoint_prior_scale': 0.05,      # Sensitivity to trend changes
    'interval_width': 0.95                # 95% confidence interval
}
```

**US Trading Holidays:**
- Fetched via `pandas_market_calendars`
- Integrated into Prophet model
- Prevents forecasting on non-trading days

**Design Decisions:**
- ✅ Use Prophet: Battle-tested, handles trends + seasonality
- ✅ Include holidays: Improves forecast accuracy
- ✅ One-step forward: Simpler model, sufficient for optimization
- ✅ One model per ticker: Independent predictions
- ❌ Don't use LSTM/RNN: Overkill for daily predictions
- ❌ Don't predict far ahead: Error compounds

**Performance:**
- Fitting: ~2-5 seconds per ticker (100 days data)
- Prediction: ~1 second per ticker
- For 12 tickers: ~40-60 seconds total

---

### 4. Optimization Layer (`src/optimiser.py`)

**Responsibility:** Calculate optimal portfolio weights using Markowitz theory

**Function:** `optimize_portfolio_mean_variance(...)`

**Mathematical Formulation:**

```
Objective: Minimize f(w) = -w^T * μ + (λ/2) * w^T * Σ * w

where:
  w = portfolio weights
  μ = expected returns (from predictions)
  Σ = covariance matrix of returns
  λ = risk_aversion parameter

Subject to:
  sum(w) = 1.0                    (fully invested)
  w[i] >= minimum_allocation      (minimum position size)
  w[i] <= maximum_allocation      (maximum position size)
  w[i] >= 0                       (no short selling)
```

**Solver:** `scipy.optimize.minimize` with SLSQP method

**Inputs:**
- `data_dict`: Historical returns for covariance
- `predictions`: Expected returns for optimization
- `minimum_allocation`: Constraint (default 5%)
- `maximum_allocation`: Constraint (default 100%)
- `risk_aversion`: λ parameter (default 5)

**Outputs:**
- Optimal weights dictionary summing to 1.0

**Design Decisions:**
- ✅ Use Markowitz: Standard portfolio theory
- ✅ SLSQP solver: Handles nonlinear constraints
- ✅ Use scipy: Reliable, well-tested
- ✅ Constraints: Prevent extreme allocations
- ❌ Don't use heuristics: Need mathematically optimal
- ❌ Don't allow short selling: Simpler for retail

**Risk Aversion Parameter:**

| λ | Profile | Behavior |
|---|---------|----------|
| 1 | Aggressive | Maximizes expected return, high risk |
| 5 | Balanced | Default, balanced risk/return |
| 10 | Conservative | Minimizes volatility, lower returns |

---

### 5. Database Layer (`src/database.py`)

**Responsibility:** Store and retrieve optimization results

**Functions:**
- `get_supabase_client()`: Initialize database connection
- `save_results_to_supabase(result)`: Persist results

**Database Schema:**

```sql
CREATE TABLE stock_optimisation_store (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP,
    run_date DATE,
    ticker TEXT,
    predicted_price DECIMAL,
    predicted_return DECIMAL,
    optimal_weight DECIMAL,
    recent_prices JSONB
);
```

**Row Format:**
```python
{
    'id': 'uuid-string',
    'created_at': '2024-12-31T14:30:00Z',
    'run_date': '2024-12-31',
    'ticker': 'AAPL',
    'predicted_price': 150.25,
    'predicted_return': 0.015,
    'optimal_weight': 0.35,
    'recent_prices': [145.0, 145.5, 146.0, ...]
}
```

**Design Decisions:**
- ✅ Use Supabase: Free tier, managed PostgreSQL
- ✅ One row per ticker: Easy to query, normalize data
- ✅ Store recent prices: For dashboard visualization
- ✅ UUID primary key: No reliance on ids
- ❌ Don't use NoSQL: Structured data fits SQL
- ❌ Don't redundantly store same data: Avoid duplication

**Error Handling:**
- Missing credentials: Returns gracefully, continues without saving
- Database connection error: Logs warning, doesn't crash
- Insert failure: Returns False, allows retry

---

### 6. Settings Layer (`src/settings.py`)

**Responsibility:** Configuration constants and defaults

**Configuration Categories:**

```python
# Portfolio
PORTFOLIO_TICKERS = ['AAPL', 'MSFT', ...]

# Optimization
RISK_AVERSION = 5
MINIMUM_ALLOCATION = 0.05
MAXIMUM_ALLOCATION = 1.0

# Date Range
START_DATE = "2024-01-01"
END_DATE = "2024-12-31"

# Prophet Model
PROPHET_PARAMS = {...}

# Database
SUPABASE_TABLE_NAME = "stock_optimisation_store"
```

**Design Decisions:**
- ✅ Centralize configuration: Single source of truth
- ✅ Use constants: No magic strings/numbers
- ✅ Override via environment: Flexible deployment
- ❌ Don't hardcode in modules: Violation of DRY

---

### 7. Orchestration Layer (`src/main.py`)

**Responsibility:** Coordinate pipeline execution

**Main Function:** `run_optimisation(tickers, start_date, end_date)`

**Execution Flow:**

```
1. Extract Data
   ├─ Call: extract_data(tickers, start_date, end_date)
   ├─ Input: Ticker list, date range
   └─ Output: {ticker: DataFrame}

2. Preprocess Data
   ├─ Call: preprocess_data(all_stock_data)
   ├─ Input: Raw extracted data
   └─ Output: {ticker: aligned DataFrame}

3. Generate Predictions
   ├─ Call: ProphetModel().predict_for_tickers(portfolio_data)
   ├─ Input: Aligned portfolio data
   └─ Output: (predictions, predicted_returns)

4. Collect Price History
   ├─ Call: collect_recent_prices(portfolio_data)
   ├─ Input: Aligned portfolio data
   └─ Output: {ticker: [recent prices]}

5. Append Predictions
   ├─ Call: append_predictions(portfolio_data, predictions, predicted_returns)
   ├─ Input: Portfolio data + predictions
   └─ Output: Extended portfolio data

6. Optimize Portfolio
   ├─ Call: optimize_portfolio_mean_variance(extended_data)
   ├─ Input: Portfolio data with predictions
   └─ Output: {ticker: weight}

7. Log & Return Results
   ├─ Format result dictionary
   ├─ Log to application logger
   └─ Return for persistence/display
```

**Error Handling:**
- At each step, check for empty results
- Return empty dict if any step fails
- Log warnings/errors throughout

---

## Data Flow

### End-to-End Pipeline

```
User Input:
  tickers=['AAPL', 'MSFT', 'GOOGL']
  start_date='2024-01-01'
  end_date='2024-12-31'
          │
          ▼
    ┌─────────────┐
    │  Extractor  │
    └──────┬──────┘
           │
    Returns: {
      'AAPL': DataFrame([Price, Returns]),
      'MSFT': DataFrame([Price, Returns]),
      'GOOGL': DataFrame([Price, Returns])
    }
           │
           ▼
    ┌─────────────┐
    │ Processor   │─► Align dates
    └──────┬──────┘   Calculate returns
           │
    Returns: Aligned DataFrames (same index)
           │
           ▼
    ┌──────────────┐
    │   Prophet    │─► Fit 3 models
    │   Model      │   Predict prices
    └──────┬───────┘
           │
    Returns: (predictions, predicted_returns)
           │
           ▼
    ┌──────────────┐
    │  Optimizer   │─► Calculate covariance
    │  (Markowitz) │   Solve for weights
    └──────┬───────┘
           │
    Returns: {
      'AAPL': 0.35,
      'MSFT': 0.40,
      'GOOGL': 0.25
    }
           │
           ▼
    ┌──────────────┐
    │   Database   │─► Save results
    │  (Supabase)  │
    └──────┬───────┘
           │
    Returns: {
      'date': '2024-12-31',
      'predictions': {...},
      'weights': {...},
      ...
    }
           │
           ▼
    Display/Persist
```

### Data Transformation Example

```python
# 1. Raw Data (from yfinance)
{
  'AAPL': pd.DataFrame({
    'Open': [145.0],
    'High': [147.0],
    'Low': [144.5],
    'Close': [146.0],
    'Volume': [1000000]
  }, index=pd.DatetimeIndex(['2024-12-31']))
}

# 2. After Processing
{
  'AAPL': pd.DataFrame({
    'Price': [146.0],
    'Returns': [0.0034]  # Calculated from historical
  }, index=pd.DatetimeIndex(['2024-12-31']))
}

# 3. After Prediction
predictions = {'AAPL': 150.25}
predicted_returns = {'AAPL': 0.015}

# 4. After Optimization
weights = {'AAPL': 0.35, 'MSFT': 0.40, 'GOOGL': 0.25}

# 5. Final Result
{
  'date': '2024-12-31',
  'predictions': {...},
  'predicted_returns': {...},
  'weights': {...},
  'actual_prices_last_month': {...}
}
```

---

## Module Interactions

### Dependency Graph

```
main.py
├─ imports: extractor, processor, model, optimiser, database
│
├─ extractor
│  ├─ depends: yfinance, pandas
│  └─ exports: extract_data()
│
├─ processor
│  ├─ depends: pandas
│  └─ exports: preprocess_data(), append_predictions(), collect_recent_prices()
│
├─ model
│  ├─ depends: prophet, pandas, pandas_market_calendars
│  └─ exports: ProphetModel
│
├─ optimiser
│  ├─ depends: scipy, numpy
│  └─ exports: optimize_portfolio_mean_variance()
│
├─ database
│  ├─ depends: supabase
│  └─ exports: get_supabase_client(), save_results_to_supabase()
│
└─ settings
   ├─ depends: (no module dependencies)
   └─ exports: configuration constants
```

### Import Order & Initialization

```python
# settings.py
# ├─ No dependencies
# └─ Loaded first

# extractor.py
# ├─ Imports: yfinance, pandas
# └─ Can be used immediately

# processor.py
# ├─ Imports: pandas
# └─ Takes extractor output

# model.py
# ├─ Imports: prophet, pandas_market_calendars
# ├─ Long startup time (loads Stan model)
# └─ Takes processor output

# optimiser.py
# ├─ Imports: scipy
# └─ Takes model output

# database.py
# ├─ Imports: supabase
# ├─ May fail if no credentials (handled gracefully)
# └─ Takes optimizer output

# main.py
# ├─ Imports all modules
# └─ Orchestrates execution
```

---

## Technology Stack

### Core Dependencies

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| **Prophet** | 1.3.0 | Time series forecasting | Handles trends, seasonality, holidays |
| **scipy** | 1.17.1 | Portfolio optimization | SLSQP solver for constraints |
| **pandas** | 3.0.2 | Data manipulation | Flexible DataFrames, time series |
| **numpy** | 2.4.4 | Numerical computing | Efficient arrays, covariance |
| **yfinance** | 1.3.0 | Stock data fetching | Free, no API key required |
| **supabase** | 2.30.0 | Database client | Managed PostgreSQL, free tier |
| **pandas_market_calendars** | 5.3.2 | Trading calendar | US stock market holidays |

### Development Stack

| Tool | Purpose |
|------|---------|
| **pytest** | Unit testing |
| **pytest-cov** | Coverage reporting |
| **Poetry** | Dependency management |
| **Git** | Version control |

### Optional Stack

| Tool | Purpose | Use Case |
|------|---------|----------|
| **Streamlit** | Dashboard | Web UI visualization |
| **Docker** | Containerization | Deployment |
| **Nginx** | Web server | Dashboard hosting |

---

## Design Patterns

### 1. Factory Pattern (Model Creation)

```python
class ProphetModel:
    def __init__(self):
        self.model = None  # Created on demand
    
    def fit(self, data):
        self.model = Prophet(**PROPHET_PARAMS)  # Factory creates Prophet
        self.model.fit(...)
```

### 2. Wrapper Pattern (Database Client)

```python
def get_supabase_client():
    """Wraps supabase client initialization"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    
    return supabase.create_client(SUPABASE_URL, SUPABASE_KEY)
```

### 3. Strategy Pattern (Optimization Constraints)

```python
# Different strategies for different risk profiles
conservative = {'minimum': 0.1, 'maximum': 0.2, 'risk_aversion': 10}
balanced = {'minimum': 0.05, 'maximum': 0.5, 'risk_aversion': 5}
aggressive = {'minimum': 0.05, 'maximum': 1.0, 'risk_aversion': 1}
```

### 4. Pipeline Pattern (Data Processing)

```
Data → Extraction → Processing → Modeling → Optimization → Storage
              ↓              ↓          ↓            ↓           ↓
         extract_data   preprocess  predict  optimize_   save_
         ________       ________    ______   ________    ______
```

### 5. Configuration Pattern

```python
# settings.py - single source of truth
PORTFOLIO_TICKERS = [...]
RISK_AVERSION = 5
...

# Imported everywhere needed
from src.settings import PORTFOLIO_TICKERS, RISK_AVERSION
```

---

## Performance Considerations

### Computational Complexity

| Component | Time | Space | Scalability |
|-----------|------|-------|-------------|
| Data extraction | O(n) | O(n) | Good (linear) |
| Processing | O(n) | O(n) | Good (linear) |
| Prophet fitting | O(n²) | O(n) | Fair (quadratic) |
| Covariance calc | O(m²) | O(m²) | Good (matrix ops) |
| Optimization | O(m³) | O(m²) | Fair (SLSQP) |
| Database insert | O(1) | O(1) | Excellent |

Where:
- n = number of time periods (days)
- m = number of assets (tickers)

### Measured Performance

**12-ticker portfolio, 1 year data (~252 days):**

| Step | Time | Notes |
|------|------|-------|
| Extraction | ~2-3 sec | Network-dependent |
| Processing | ~1 sec | Vectorized pandas |
| Prophet fit | ~20 sec | 3-5 sec per ticker × 12 |
| Prediction | ~12 sec | ~1 sec per ticker × 12 |
| Optimization | <1 sec | Small optimization problem |
| Database | <1 sec | Network-dependent |
| **Total** | **~36-40 sec** | Acceptable for daily jobs |

### Memory Usage

**12-ticker portfolio:**
- Raw data: ~2MB
- Fitted models: ~50MB (Prophet models)
- Covariance matrix: ~1KB
- Peak: ~60-80MB

**Scalability:**
- Add tickers: Linear memory growth
- Extend date range: Linear memory growth
- 100+ tickers: Possible but slowdowns likely

---

## Scalability & Future Growth

### Horizontal Scaling

**Current Bottleneck:** Single daily job per server

**Solution Options:**

1. **Separate Services:**
   ```
   Extraction Service → Processing Service → Prediction Service → Optimization Service
   (Parallel processing with message queue)
   ```

2. **Multiple Portfolios:**
   ```
   Main Portfolio
   Dividend Portfolio
   Growth Portfolio
   Sector Rotation Portfolio
   (Run independently, same infrastructure)
   ```

3. **Real-time Dashboard:**
   ```
   Cache results in Redis
   Serve from cache
   Update on schedule
   ```

### Vertical Scaling

**Improve Single Server:**
- Increase CPU cores (better Prophet fitting)
- Increase RAM (cache models, covariance matrices)
- Faster network (faster data fetching)

### Feature Scaling Path

**Short-term (Phase 3-4):**
- [ ] Add backtesting framework
- [ ] Add risk metrics (VaR, Sharpe ratio)
- [ ] Improve Prophet tuning

**Medium-term (Phase 5-6):**
- [ ] Multi-portfolio support
- [ ] Sector analysis
- [ ] Correlation analysis
- [ ] Machine learning optimization

**Long-term (Phase 7+):**
- [ ] Real-time predictions
- [ ] Alternative data sources
- [ ] Advanced risk models
- [ ] Portfolio simulation

### Monitoring & Observability

**Key Metrics to Track:**

```python
# Prediction accuracy
- MAPE (Mean Absolute % Error)
- RMSE (Root Mean Square Error)
- Hit rate (% correct direction)

# Portfolio performance
- Returns vs S&P 500
- Sharpe ratio
- Max drawdown

# System health
- Job execution time
- Success/failure rate
- Database query time
```

**Implementation:**
```python
# Could integrate with monitoring services:
# - Prometheus (metrics)
# - Grafana (dashboards)
# - DataDog (APM)
# - CloudWatch (AWS)
```

---

## Deployment Architectures

### Development

```
Local Machine
├─ Source code (git)
├─ Virtual environment
├─ Jupyter notebooks
└─ Local database (optional)
```

### Production (Current)

```
VPS (Hostinger)
├─ Application code
├─ Virtual environment
├─ Cron job (daily 9am)
├─ Supabase (cloud database)
└─ Streamlit dashboard (optional)
```

### Production (Advanced)

```
Cloud Infrastructure:
├─ Load Balancer (traffic)
├─ Application Servers (multiple instances)
├─ Job Queue (RabbitMQ/Redis)
├─ Database (Supabase/PostgreSQL)
├─ Cache (Redis)
├─ Monitoring (Prometheus/Grafana)
├─ Logging (ELK Stack)
└─ CDN (static assets)
```

---

## Decision Records

### Why Prophet?

✅ **Chosen:** Facebook's Prophet

**Alternatives:**
- ARIMA: Simpler but less flexible
- LSTM: More complex, harder to tune
- Holt-Winters: Limited seasonality handling

**Reasons:**
1. Handles trends, seasonality, holidays
2. Robust to missing data and outliers
3. Interpretable components
4. Automatic changepoint detection

### Why Markowitz?

✅ **Chosen:** Mean-variance optimization

**Alternatives:**
- Equal weight: No optimization
- Risk parity: Ignores expected returns
- Black-Litterman: Complex prior specification

**Reasons:**
1. Standard portfolio theory foundation
2. Mathematically sound
3. Handles constraints cleanly
4. Easy to understand and explain

### Why Supabase?

✅ **Chosen:** Supabase (managed PostgreSQL)

**Alternatives:**
- MongoDB: Unstructured, overkill
- Firebase: Expensive for this use case
- Self-managed PostgreSQL: Ops overhead

**Reasons:**
1. Free tier sufficient
2. Managed (no ops work)
3. SQL for structure queries
4. Easy to extend schema

---

## Conclusion

This architecture provides:
- ✅ **Modularity**: Each component independent
- ✅ **Testability**: Easy to test each layer
- ✅ **Scalability**: Room to grow horizontally and vertically
- ✅ **Maintainability**: Clear separation of concerns
- ✅ **Performance**: Fast enough for daily jobs
- ✅ **Simplicity**: Not over-engineered

Future enhancements can be added without major refactoring.

