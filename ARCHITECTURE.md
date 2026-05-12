# Architecture Documentation

Technical design and architecture of the Prophet Portfolio Optimization system.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow](#data-flow)
4. [Module Descriptions](#module-descriptions)
5. [Technology Stack](#technology-stack)
6. [Design Decisions](#design-decisions)
7. [Scalability & Performance](#scalability--performance)
8. [Error Handling & Reliability](#error-handling--reliability)

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User/Scheduler                          │
│         (Cron Job / Manual Execution / API Call)            │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Main Orchestr. │
         │  (main.py)     │
         └────────────────┘
                  │
       ┌──────────┼──────────┐
       │          │          │
       ▼          ▼          ▼
    ┌────────┐  ┌──────────┐  ┌────────────┐
    │Extract │  │Processor │  │   Model    │
    │ (yf)   │  │(alignment)│  │ (Prophet)  │
    └────────┘  └──────────┘  └────────────┘
       │          │          │
       └──────────┼──────────┘
                  │
                  ▼
         ┌────────────────┐
         │   Optimiser    │
         │  (Markowitz)   │
         └────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │   Database     │
         │  (Supabase)    │
         └────────────────┘
```

### Key Characteristics

- **Modular**: Each component has single responsibility
- **Data-driven**: All decisions based on predictions and optimization
- **Batch-oriented**: Runs once daily, not real-time
- **Fault-tolerant**: Graceful degradation if components fail
- **Observable**: Comprehensive logging throughout

---

## Component Architecture

### 1. Extraction Layer

**Purpose:** Fetch raw market data from Yahoo Finance

**Components:**
- `src/extractor.py`
- `yfinance` library
- Network connection to Yahoo Finance

**Responsibilities:**
- Download historical OHLCV data
- Validate data quality
- Handle missing tickers gracefully
- Calculate daily returns

**Input:** Ticker symbols, date range

**Output:** Dictionary of DataFrames with Price and Returns columns

### 2. Processing Layer

**Purpose:** Prepare data for modeling and optimization

**Components:**
- `src/processor.py`
- pandas for data manipulation
- numpy for numerical operations

**Responsibilities:**
- Align data across multiple assets
- Handle missing/misaligned dates
- Calculate additional features (if needed)
- Prepare data for next steps

**Input:** Raw extracted data

**Output:** Aligned portfolio data ready for modeling

### 3. Modeling Layer

**Purpose:** Generate price predictions using time series forecasting

**Components:**
- `src/model.py`
- Facebook Prophet library
- pandas_market_calendars for holidays
- cmdstanpy for statistical inference

**Responsibilities:**
- Fit Prophet model to historical prices
- Incorporate US trading holidays
- Generate next-day price predictions
- Calculate predicted returns

**Input:** Aligned price series with datetime index

**Output:** Predicted prices and returns for each asset

### 4. Optimization Layer

**Purpose:** Calculate optimal portfolio weights

**Components:**
- `src/optimiser.py`
- scipy for constrained optimization
- numpy for numerical computations

**Responsibilities:**
- Build covariance matrix from returns
- Formulate optimization problem
- Apply Markowitz mean-variance framework
- Solve with SLSQP algorithm
- Enforce allocation constraints

**Input:** Portfolio data with predicted returns

**Output:** Dictionary of optimal weights summing to 1.0

### 5. Database Layer

**Purpose:** Persist results for analysis and dashboard

**Components:**
- `src/database.py`
- Supabase PostgreSQL backend
- Python Supabase client

**Responsibilities:**
- Connect to Supabase
- Validate results structure
- Insert results into database
- Handle connection failures gracefully

**Input:** Optimization result dictionary

**Output:** Database insertion status

### 6. Orchestration Layer

**Purpose:** Coordinate all components into complete pipeline

**Components:**
- `src/main.py`
- Python logging
- Environment configuration

**Responsibilities:**
- Load configuration
- Coordinate sequential execution
- Log all operations
- Return final results
- Handle errors gracefully

**Input:** Tickers, date range

**Output:** Complete optimization result or empty dict on failure

---

## Data Flow

### Complete Pipeline Flow

```
1. RUN_OPTIMISATION(tickers, start_date, end_date)
   │
   ├─ Load Settings from src/settings.py
   │  ├─ PORTFOLIO_TICKERS
   │  ├─ RISK_AVERSION
   │  ├─ PROPHET_PARAMS
   │  └─ OPTIMIZATION_CONSTRAINTS
   │
   ├─ EXTRACT_DATA(tickers, start_date, end_date)
   │  │
   │  └─ For each ticker:
   │     ├─ Download OHLCV from yfinance
   │     ├─ Extract Close prices
   │     ├─ Calculate daily returns
   │     └─ Validate data quality
   │
   ├─ PREPROCESS_DATA(extracted_data)
   │  │
   │  ├─ Find common trading dates
   │  ├─ Align all DataFrames to common dates
   │  └─ Create aligned portfolio dict
   │
   ├─ ProphetModel.PREDICT_FOR_TICKERS(portfolio_data)
   │  │
   │  ├─ For each ticker:
   │  │  ├─ Prepare data as Prophet DataFrame
   │  │  ├─ Get trading holidays for date range
   │  │  ├─ Fit Prophet model
   │  │  ├─ Generate next-day forecast
   │  │  └─ Calculate predicted return
   │  │
   │  └─ Collect predictions and returns dicts
   │
   ├─ COLLECT_RECENT_PRICES(portfolio_data, days=20)
   │  │
   │  └─ Extract last N trading days' prices per ticker
   │
   ├─ APPEND_PREDICTIONS(portfolio_data, predictions, returns)
   │  │
   │  └─ Add prediction row to each ticker's data
   │
   ├─ OPTIMIZE_PORTFOLIO(predicted_data, constraints)
   │  │
   │  ├─ Calculate covariance matrix
   │  ├─ Set up objective function
   │  ├─ Define constraints (sum=1, min/max bounds)
   │  ├─ Solve with scipy.optimize.minimize (SLSQP)
   │  └─ Validate solution
   │
   ├─ Log all results and metrics
   │
   ├─ SAVE_RESULTS_TO_SUPABASE(result)
   │  │
   │  ├─ Validate result structure
   │  ├─ Insert row per ticker into database
   │  └─ Handle connection failures
   │
   └─ RETURN result dict with:
      ├─ date
      ├─ predictions
      ├─ predicted_returns
      ├─ weights
      └─ actual_prices_last_month
```

### Data Structures

#### Extracted Data
```python
{
    "AAPL": DataFrame(
        index=DatetimeIndex,
        columns=["Price", "Returns"]
    ),
    "MSFT": DataFrame(...)
}
```

#### Processed Data
```python
{
    "AAPL": DataFrame(
        index=DatetimeIndex,  # Aligned across all tickers
        columns=["Price", "Returns"]
    ),
    "MSFT": DataFrame(...)
}
```

#### Predictions
```python
predictions = {
    "AAPL": 150.25,
    "MSFT": 300.50,
    "GOOGL": 100.75
}

predicted_returns = {
    "AAPL": 0.015,
    "MSFT": 0.020,
    "GOOGL": 0.010
}
```

#### Optimization Result
```python
weights = {
    "AAPL": 0.352,
    "MSFT": 0.421,
    "GOOGL": 0.227
}
# sum(weights.values()) = 1.0
```

---

## Module Descriptions

### src/extractor.py

**Size:** ~31 lines

**Key Functions:**
- `extract_data()` - Main entry point
- `_extract_single_ticker_data()` - Download single ticker
- `_process_ticker_dataframe()` - Clean and calculate returns

**Dependencies:**
- yfinance
- pandas
- numpy

**Design Notes:**
- Uses yfinance for data (free, no API key required)
- Handles missing data gracefully
- Calculates returns as percentage change
- Error handling for invalid tickers

### src/processor.py

**Size:** ~37 lines

**Key Functions:**
- `preprocess_data()` - Align data across tickers
- `append_predictions()` - Add forecast rows
- `collect_recent_prices()` - Extract recent history

**Dependencies:**
- pandas
- numpy

**Design Notes:**
- Critical for handling multiple assets
- Finds intersection of dates (common trading days)
- Enables comparison across tickers
- Modular design for reusability

### src/model.py

**Size:** ~103 lines

**Key Functions:**
- `ProphetModel.fit()` - Train on historical data
- `ProphetModel.predict_next()` - Single prediction
- `ProphetModel.predict_for_tickers()` - Batch predictions
- `_get_us_trading_holidays()` - Holiday fetching
- `_normalise_holiday_name()` - Holiday name mapping

**Dependencies:**
- prophet
- pandas_market_calendars
- pandas
- numpy

**Design Notes:**
- Wraps Prophet for cleaner API
- Automatically includes US trading holidays
- Configurable seasonality and changepoint detection
- Handles short data gracefully

**Prophet Configuration:**
```python
PROPHET_PARAMS = {
    'yearly_seasonality': True,      # Capture annual patterns
    'weekly_seasonality': False,     # Stocks don't have weekly patterns
    'daily_seasonality': False,      # Daily patterns weak
    'seasonality_mode': 'multiplicative',
    'changepoint_prior_scale': 0.05, # Sensitivity to trend changes
    'interval_width': 0.95           # 95% confidence intervals
}
```

### src/optimiser.py

**Size:** ~33 lines

**Key Functions:**
- `optimize_portfolio_mean_variance()` - Main optimization

**Dependencies:**
- scipy.optimize.minimize
- numpy
- pandas

**Design Notes:**
- Pure Markowitz mean-variance optimization
- Uses SLSQP algorithm for constrained optimization
- No transaction costs modeled
- No rebalancing costs

**Mathematical Formulation:**

Minimize:
```
f(w) = -w^T * μ + (λ/2) * w^T * Σ * w
```

Subject to:
```
Sum(w) = 1.0                    (Fully invested)
min_w <= w_i <= max_w           (Allocation bounds)
```

Where:
- `w` = weight vector
- `μ` = expected returns (predicted returns)
- `Σ` = return covariance matrix
- `λ` = risk aversion parameter

### src/database.py

**Size:** ~36 lines

**Key Functions:**
- `get_supabase_client()` - Connect to database
- `save_results_to_supabase()` - Persist results

**Dependencies:**
- supabase-py
- pandas

**Design Notes:**
- Graceful degradation if DB unavailable
- Creates one row per ticker
- Includes recent price history as JSON
- Automatic UUID generation

**Schema:**
```sql
stock_optimisation_store (
  id UUID PRIMARY KEY,
  created_at TIMESTAMP,
  run_date DATE,
  ticker TEXT,
  predicted_price DECIMAL,
  predicted_return DECIMAL,
  optimal_weight DECIMAL,
  recent_prices JSONB
)
```

### src/settings.py

**Size:** ~10 lines

**Key Variables:**
- Portfolio configuration
- Optimization parameters
- Prophet model parameters
- Database settings

**Design Notes:**
- Single source of truth for config
- Easy to modify without code changes
- Supports environment variable overrides
- Well-documented parameters

### src/main.py

**Size:** ~61 lines

**Key Functions:**
- `run_optimisation()` - Main orchestration function

**Dependencies:**
- All other modules
- logging
- datetime

**Design Notes:**
- Coordinates all components
- Comprehensive logging
- Error handling with graceful degradation
- Returns consistent result format

---

## Technology Stack

### Core Technologies

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Data** | pandas | 3.0.2 | Data manipulation |
| | numpy | 2.4.4 | Numerical operations |
| **Modeling** | prophet | 1.3.0 | Time series forecasting |
| | cmdstanpy | 1.3.0 | Statistical inference |
| **Optimization** | scipy | 1.17.1 | Constrained optimization |
| **Data Source** | yfinance | 1.3.0 | Stock prices |
| **Database** | supabase | 2.30.0 | Results storage |
| **Calendars** | pandas_market_calendars | 5.3.2 | Trading holidays |
| **Python** | - | 3.12.3 | Runtime |

### Development Tools

| Tool | Purpose |
|------|---------|
| pytest | Testing framework |
| pytest-cov | Coverage reporting |
| poetry | Dependency management |
| git | Version control |
| streamlit | Dashboard visualization |

---

## Design Decisions

### 1. Prophet for Time Series Forecasting

**Decision:** Use Facebook Prophet instead of ARIMA/GARCH

**Rationale:**
- ✅ Handles holidays automatically
- ✅ Good at capturing seasonality
- ✅ Robust to missing data
- ✅ Fast training (seconds vs minutes)
- ✅ Interpretable components
- ❌ Simpler than advanced methods
- ❌ May miss regime changes

**Alternatives Considered:**
- ARIMA: Manual parameter tuning, slower
- GARCH: Better volatility modeling, slower
- LSTM: Deep learning, overkill for daily prediction
- Random Walk: Too simple for active trading

### 2. Markowitz Mean-Variance Optimization

**Decision:** Classic Markowitz instead of Black-Litterman or other methods

**Rationale:**
- ✅ Simple, transparent, proven
- ✅ Convex optimization (global optimum)
- ✅ Fast computation
- ✅ Interpretable weights
- ❌ Doesn't handle rebalancing costs
- ❌ Ignores tail risk
- ❌ Assumes normal returns

**Alternatives Considered:**
- Black-Litterman: More complex, better for active views
- Risk Parity: Equal risk contribution
- Hierarchical Risk Parity: Better empirical performance
- Kelly Criterion: Growth-focused, riskier

### 3. SLSQP Optimization Algorithm

**Decision:** Use scipy.optimize.minimize with SLSQP algorithm

**Rationale:**
- ✅ Handles constraints well
- ✅ Fast convergence
- ✅ Built-in (no extra dependencies)
- ✅ Proven in production systems
- ❌ Local optimization (not global)
- ❌ Sensitive to initial guess

**Alternatives Considered:**
- CVX/CVXPY: More complex, unnecessary for convex problem
- Genetic Algorithms: Too slow, overly complex
- Simulated Annealing: Slower, not needed

### 4. Supabase for Database

**Decision:** Use Supabase (PostgreSQL) over Firebase/DynamoDB/etc

**Rationale:**
- ✅ SQL support (complex queries possible)
- ✅ Free tier sufficient
- ✅ Good Python library
- ✅ Open source (PostgreSQL)
- ❌ Requires API keys in code
- ❌ Cold start delays

**Alternatives Considered:**
- Firebase: Real-time, but NoSQL limitations
- DynamoDB: Serverless, but expensive at scale
- SQLite: Local only, not multi-device
- PostgreSQL (self-hosted): More control, ops burden

### 5. Daily Batch Processing

**Decision:** Run optimization once daily instead of real-time/streaming

**Rationale:**
- ✅ Stock markets closed after hours
- ✅ No intraday price data available
- ✅ Simpler architecture
- ✅ Lower computational cost
- ❌ Can't react to intraday events
- ❌ Single daily prediction

**Alternatives Considered:**
- Real-time: Not possible without intraday data
- Multiple daily runs: More valuable but more cost
- Continuous streaming: Unnecessary complexity

### 6. One-Step-Ahead Predictions

**Decision:** Predict only next trading day instead of multiple days

**Rationale:**
- ✅ Most accurate predictions (shorter horizon)
- ✅ Daily rebalancing possible
- ✅ Simple and interpretable
- ❌ Can't capture longer trends
- ❌ More frequent rebalancing costs

**Alternatives Considered:**
- Multi-step predictions: Less accurate, harder to interpret
- Scenario planning: Complex, less actionable

---

## Scalability & Performance

### Current Performance

**Typical Execution Times:**
```
12-ticker portfolio:
  Extract: ~2 seconds
  Preprocess: <1 second
  Prophet fit (per ticker): ~5 seconds → 60 sec total
  Optimization: <1 second
  Database: <1 second
  TOTAL: ~65 seconds
```

**Memory Usage:**
```
Python process: ~200-400 MB
Prophet model: ~100 MB per ticker
Peak: ~1 GB for 12 tickers + Prophet models
```

### Scalability Limits

**Current Bottleneck:** Prophet model fitting

```
Number of Tickers | Time (sec) | Memory (MB)
1                 | 5          | 300
5                 | 25         | 500
10                | 50         | 800
25                | 125        | 1500  ← Memory issues
50                | 250        | 2500  ← Too slow
100               | 500        | 5000  ← Not feasible
```

### Optimization Opportunities

1. **Parallel Prophet Fitting**
   ```python
   from multiprocessing import Pool
   
   with Pool(4) as p:
       predictions = p.map(fit_and_predict, tickers)
   ```
   Expected: 4x speedup for 4 cores

2. **Caching**
   ```python
   # Cache historical data to avoid re-download
   if data_in_cache and cache_age < 1_day:
       data = load_from_cache()
   else:
       data = extract_data()
   ```
   Expected: 10x speedup on second run

3. **Batch Optimization**
   ```python
   # Single optimization instead of per-ticker
   # Current: O(n_tickers) Prophet fits
   # Future: Single covariance + optimization
   ```

4. **GPU Acceleration**
   ```python
   # Use CmdStanPy GPU support
   # Requires NVIDIA GPU + CUDA
   ```

### Recommended Limits

- **Production:** 10-15 tickers (safe)
- **Stress:** 25-30 tickers (acceptable)
- **Breaking:** 50+ tickers (slow, memory issues)

---

## Error Handling & Reliability

### Failure Modes & Recovery

#### 1. Missing Data (Ticker)

**Scenario:** Yahoo Finance has no data for ticker

**Handling:**
```python
if not data:
    logger.warning(f"No data for {ticker}")
    continue  # Skip this ticker
# Process remaining tickers
```

**Result:** Partial optimization with available tickers

**Example:**
```
Input: ['AAPL', 'INVALID', 'MSFT']
Output: Optimizes AAPL + MSFT only
```

#### 2. Network Timeout

**Scenario:** yfinance connection fails

**Handling:**
```python
try:
    data = yf.download(...)
except Exception as e:
    logger.error(f"Download failed: {e}")
    return {}  # Empty result
```

**Result:** Returns empty dict, no crash

#### 3. Model Fitting Failure

**Scenario:** Prophet fails on problematic data

**Handling:**
```python
try:
    model.fit(series)
except Exception as e:
    logger.error(f"Model fit failed: {e}")
    predictions[ticker] = None  # Mark as failed
```

**Result:** Optimization proceeds without this ticker

#### 4. Database Connection

**Scenario:** Supabase unavailable

**Handling:**
```python
try:
    save_results_to_supabase(result)
except Exception as e:
    logger.error(f"Database save failed: {e}")
    # Results still returned to caller
    return result
```

**Result:** Results still available locally, not persisted

#### 5. Insufficient Data Points

**Scenario:** Ticker has <20 data points

**Handling:**
```python
if len(data) < MIN_POINTS:
    logger.warning(f"Insufficient data: {len(data)} < {MIN_POINTS}")
    # Prophet still fits, but less reliable
    predictions[ticker] = model.fit(data)
```

**Result:** Still produces prediction, with warning

### Reliability Features

1. **Comprehensive Logging**
   - All major operations logged
   - Error and warning messages
   - Execution time tracking

2. **Graceful Degradation**
   - Missing tickers → skip and continue
   - Network issues → empty result
   - Database down → local result only
   - Model failures → proceed without ticker

3. **Validation**
   - Check result structure
   - Verify weights sum to 1.0
   - Validate date formats
   - Check for NaN/Inf values

4. **Testing**
   - 57 test cases
   - Unit tests for each module
   - Integration tests for pipelines
   - Edge case tests
   - 58%+ code coverage

---

## Deployment Architecture

### Development

```
Local Machine
├─ src/
├─ tests/
├─ venv/
└─ .env (local credentials)
```

### Production (Hostinger VPS)

```
VPS Instance
├─ /home/prophet/
│  ├─ prophet-stock-forecast/
│  │  ├─ src/
│  │  ├─ tests/
│  │  └─ venv/
│  └─ .env (production credentials)
├─ systemd services
│  ├─ prophet-optimization (daily cron)
│  └─ prophet-dashboard (Streamlit server)
└─ logs
   └─ prophet.log
```

### Data Flow (Production)

```
Cron Job (9am UTC)
    │
    ▼
run_optimisation()
    │
    ├─→ yfinance (download)
    ├─→ Prophet (forecasting)
    ├─→ scipy (optimization)
    │
    ▼
save_results_to_supabase()
    │
    ▼
Supabase PostgreSQL
    │
    ▼
Streamlit Dashboard
(user views results)
```

---

## Monitoring & Observability

### Key Metrics

1. **Execution Health**
   - Execution time (target: <2 min)
   - Success rate (target: 100%)
   - Errors/warnings (target: 0)

2. **Prediction Quality**
   - MAPE (target: <2%)
   - Hit rate (target: >55%)
   - Bias (target: ~0%)

3. **Portfolio Quality**
   - Concentration (max single position)
   - Diversification (Herfindahl index)
   - Turnover (weight changes)

4. **System Health**
   - Database connectivity
   - Data freshness
   - Memory usage
   - CPU usage

### Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/prophet.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Starting optimization...")
```

---

## Version Information

- **Application**: Prophet Stock Forecasting v0.1.0
- **Architecture Documentation**: May 2026
- **Last Updated**: May 2026

