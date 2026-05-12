# User Guide

Complete guide for using the Prophet Portfolio Optimization application.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Running Optimization](#running-optimization)
3. [Understanding Results](#understanding-results)
4. [Configuration Guide](#configuration-guide)
5. [Dashboard Usage](#dashboard-usage)
6. [Portfolio Scenarios](#portfolio-scenarios)
7. [FAQ](#faq)

---

## Quick Start

### Minimum Viable Setup (5 minutes)

1. **Install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Set Supabase credentials** (optional)
   ```bash
   export SUPABASE_URL="https://your-project.supabase.co"
   export SUPABASE_KEY="your-anon-key"
   ```

3. **Run optimization**
   ```bash
   python -c "
   from src.main import run_optimisation
   
   result = run_optimisation(
       tickers=['AAPL', 'MSFT', 'GOOGL'],
       start_date='2024-01-01',
       end_date='2024-12-31'
   )
   
   if result:
       print('Optimization Results:')
       print(f\"Date: {result['date']}\")
       print(f\"Recommendations:\")
       for ticker, weight in result['weights'].items():
           print(f\"  {ticker}: {weight*100:.1f}%\")
   "
   ```

4. **View results**
   ```
   Optimization Results:
   Date: 2024-12-31
   Recommendations:
     AAPL: 35.2%
     MSFT: 42.1%
     GOOGL: 22.7%
   ```

---

## Running Optimization

### Basic Usage

```python
from src.main import run_optimisation
from src.database import save_results_to_supabase

# Run optimization
result = run_optimisation(
    tickers=['AAPL', 'MSFT', 'GOOGL', 'AMZN'],
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# Check if successful
if not result:
    print("Optimization failed - no data")
    exit(1)

# Save results to database
save_results_to_supabase(result)
print("✅ Optimization complete and saved!")
```

### With Custom Parameters

```python
from src.main import run_optimisation

result = run_optimisation(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# Configure optimization parameters
from src.optimiser import optimize_portfolio_mean_variance

optimal_weights = optimize_portfolio_mean_variance(
    data_dict=portfolio_data,
    minimum_allocation=0.10,  # 10% minimum per stock
    maximum_allocation=0.35,  # 35% maximum per stock
    risk_aversion=7.0         # Higher = more conservative
)
```

### Handling Errors

```python
from src.main import run_optimisation
import logging

logging.basicConfig(level=logging.INFO)

try:
    result = run_optimisation(
        tickers=['AAPL', 'MSFT'],
        start_date='2024-01-01',
        end_date='2024-12-31'
    )
    
    if not result:
        print("⚠️  No data returned - check tickers and dates")
    else:
        print("✅ Optimization successful")
        print(f"Results saved for {result['date']}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    logging.exception("Full traceback:")
```

---

## Understanding Results

### Result Structure

```python
{
    "date": "2024-12-31",                           # Optimization date
    "predictions": {                                # Next-day price predictions
        "AAPL": 150.25,
        "MSFT": 300.50,
        "GOOGL": 100.75
    },
    "predicted_returns": {                          # Predicted returns
        "AAPL": 0.015,  # 1.5%
        "MSFT": 0.020,  # 2.0%
        "GOOGL": 0.010  # 1.0%
    },
    "weights": {                                    # Optimal allocation
        "AAPL": 0.35,   # 35%
        "MSFT": 0.40,   # 40%
        "GOOGL": 0.25   # 25%
    },
    "actual_prices_last_month": {                   # Recent price history
        "AAPL": [145.0, 145.5, 146.0, ...],
        "MSFT": [295.0, 296.0, 297.0, ...],
        "GOOGL": [98.0, 98.5, 99.0, ...]
    }
}
```

### Interpreting Weights

**What the weights mean:**
- Sum always equals 1.0 (100% of portfolio)
- Each weight = recommended allocation percentage
- Higher weight = more conviction in expected returns

**Example:**
```
Portfolio: $100,000

Recommendations:
  AAPL: 35.2% = $35,200
  MSFT: 42.1% = $42,100
  GOOGL: 22.7% = $22,700
  Total: 100.0% = $100,000
```

### Interpreting Predictions

**Predicted Price:**
- Model's estimate of next trading day's closing price
- Based on historical patterns + seasonality

**Predicted Return:**
- Expected percentage change next day
- Positive = price expected to increase
- Negative = price expected to decrease

**Example Analysis:**
```python
result = run_optimisation(...)

for ticker, (price, weight) in zip(
    result['predictions'].items(),
    result['weights'].values()
):
    pred_return = result['predicted_returns'][ticker]
    impact = weight * pred_return  # Portfolio impact of this position
    
    print(f"{ticker}:")
    print(f"  Predicted price: ${price:.2f}")
    print(f"  Expected return: {pred_return*100:.2f}%")
    print(f"  Allocation: {weight*100:.1f}%")
    print(f"  Portfolio impact: {impact*100:.3f}%")
```

---

## Configuration Guide

### Changing Portfolio

#### Using Configuration File

Edit `src/settings.py`:
```python
# Default portfolio
PORTFOLIO_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL',  # Tech
    'AMZN', 'NVDA', 'META',   # Mega-cap tech
    'TSLA',                    # EV/Growth
    'JPM', 'JNJ', 'V',        # Financial/Healthcare/Payments
    'WMT', 'XOM'              # Consumer/Energy
]
```

Change to your portfolio:
```python
PORTFOLIO_TICKERS = [
    'AAPL', 'MSFT',           # Core holdings
    'JNJ', 'XOM',             # Dividend stocks
    'AMZN'                    # Growth
]
```

#### Using Environment Variable

```bash
export PORTFOLIO_TICKERS="AAPL,MSFT,GOOGL,JPM,JNJ"
```

#### Runtime Configuration

```python
from src.main import run_optimisation

# Custom portfolio
my_portfolio = ['AAPL', 'MSFT', 'GOOGL', 'JPM']

result = run_optimisation(
    tickers=my_portfolio,
    start_date='2024-01-01',
    end_date='2024-12-31'
)
```

### Adjusting Risk Tolerance

#### Conservative Portfolio (Lower Risk)
```python
from src.optimiser import optimize_portfolio_mean_variance

weights = optimize_portfolio_mean_variance(
    portfolio_data,
    minimum_allocation=0.05,   # Small positions ok
    maximum_allocation=0.20,   # No large bets
    risk_aversion=10.0         # Very risk-averse
)
```

Results: Balanced allocations, small concentrated positions

#### Balanced Portfolio (Medium Risk)
```python
weights = optimize_portfolio_mean_variance(
    portfolio_data,
    minimum_allocation=0.05,   # 5% minimum
    maximum_allocation=0.50,   # 50% maximum
    risk_aversion=5.0          # Default
)
```

Results: Moderate allocations, some concentration allowed

#### Aggressive Portfolio (Higher Risk)
```python
weights = optimize_portfolio_mean_variance(
    portfolio_data,
    minimum_allocation=0.05,   # Small positions ok
    maximum_allocation=1.0,    # Can be 100% in one stock
    risk_aversion=1.0          # High growth potential
)
```

Results: Concentrated positions, high conviction

#### Equally Weighted Portfolio
```python
from src.settings import PORTFOLIO_TICKERS

equal_weights = {
    ticker: 1.0 / len(PORTFOLIO_TICKERS)
    for ticker in PORTFOLIO_TICKERS
}
```

Results: Same allocation to all holdings

### Adjusting Time Period

```python
from src.main import run_optimisation
from datetime import date, timedelta

# Last 1 year
today = date.today()
year_ago = today - timedelta(days=365)

result = run_optimisation(
    tickers=['AAPL', 'MSFT'],
    start_date=str(year_ago),
    end_date=str(today)
)
```

Time period affects:
- Prophet model training data
- Return estimates for optimization
- Seasonal patterns captured

**Recommendations:**
- Minimum: 6 months (less data = less reliable)
- Recommended: 1-2 years (balance reliability and recency)
- Maximum: 5+ years (captures full market cycles)

---

## Dashboard Usage

### Starting Dashboard

```bash
# Activate virtual environment
source venv/bin/activate

# Run Streamlit app
streamlit run src/streamlit_app.py
```

Opens at `http://localhost:8501`

### Dashboard Sections

#### 1. Latest Optimization Results

Shows:
- Optimization date and time
- Latest predicted prices
- Predicted returns
- Recommended allocations

#### 2. Price History

Displays:
- Historical prices vs predictions
- Price trends over time
- Prediction accuracy

#### 3. Portfolio Recommendations

Visual display of:
- Asset allocation percentages
- Pie chart of portfolio weights
- Allocation ranges

#### 4. Prediction Performance

Metrics:
- Mean Absolute Percentage Error (MAPE)
- Root Mean Square Error (RMSE)
- Hit rate (% correct direction)

### Interpreting Charts

**Price Chart:**
- Blue line = Historical prices
- Red line = Predicted prices
- Green = Predicted increase
- Red = Predicted decrease

**Allocation Chart:**
- Size of segment = portfolio weight
- Color = ticker symbol
- Hover for percentage

**Performance Metrics:**
- Lower MAPE/RMSE = More accurate model
- Higher hit rate = Better directional calls

---

## Portfolio Scenarios

### Scenario 1: Growth Portfolio

**Use Case:** Long-term investor, high risk tolerance, wants growth

**Configuration:**
```python
growth_tickers = [
    'NVDA',   # AI/Semiconductors
    'TSLA',   # EV/Tech
    'GOOGL',  # Tech/Internet
    'META',   # Social/AI
    'AAPL'    # Tech/Innovation
]

result = run_optimisation(
    tickers=growth_tickers,
    start_date='2024-01-01',
    end_date='2024-12-31'
)
```

**Expected Results:**
- Higher growth potential
- More volatile allocations
- Higher expected returns
- Higher risk

### Scenario 2: Income Portfolio

**Use Case:** Retiree, low risk tolerance, wants consistent dividends

**Configuration:**
```python
income_tickers = [
    'XOM',    # Energy (high dividend)
    'JNJ',    # Healthcare (dividend aristocrat)
    'V',      # Payments (growing dividend)
    'JPM',    # Finance (strong dividends)
    'WMT'     # Retail (stable dividend)
]

weights = optimize_portfolio_mean_variance(
    portfolio_data,
    minimum_allocation=0.10,   # Larger positions
    maximum_allocation=0.25,   # Not too concentrated
    risk_aversion=8.0          # Conservative
)
```

**Expected Results:**
- Stable allocations
- Lower volatility
- Predictable returns
- Dividend-focused

### Scenario 3: Balanced Portfolio

**Use Case:** Moderate investor, balanced risk/reward

**Configuration:**
```python
balanced_tickers = [
    # Tech
    'AAPL', 'MSFT', 'GOOGL',
    # Finance
    'JPM', 'V',
    # Healthcare
    'JNJ',
    # Growth
    'AMZN'
]

weights = optimize_portfolio_mean_variance(
    portfolio_data,
    minimum_allocation=0.05,
    maximum_allocation=0.40,
    risk_aversion=5.0
)
```

**Expected Results:**
- Moderate growth potential
- Reasonable risk level
- Balanced sector exposure
- Good diversification

### Scenario 4: Sector Rotation

**Use Case:** Tactical investor, wants to rotate between sectors

**Q1 Configuration (Tech heavy):**
```python
q1_tickers = ['AAPL', 'MSFT', 'NVDA', 'GOOGL']
```

**Q2 Configuration (Rotate to Finance):**
```python
q2_tickers = ['JPM', 'V', 'GS', 'BAC']
```

**Q3 Configuration (Rotate to Energy):**
```python
q3_tickers = ['XOM', 'CVX', 'MPC', 'EOG']
```

---

## FAQ

### Q: How often should I run optimization?

**A:** Depends on your strategy:
- **Daily traders**: Run daily before market open
- **Active investors**: Run weekly (Sunday evening)
- **Long-term investors**: Run monthly or quarterly
- **Set and forget**: Run once, rebalance annually

### Q: Should I follow the model's predictions exactly?

**A:** No. Use predictions as input to decision-making:
- ✅ Use as one factor among many
- ✅ Cross-check with fundamentals
- ✅ Consider your risk tolerance
- ❌ Don't follow blindly
- ❌ Don't ignore your research

### Q: How accurate are the predictions?

**A:** Typically 50-60% directional accuracy:
- Better on stable stocks
- Worse on volatile stocks
- Improves with more training data
- Depends on market conditions

**Check dashboard for:**
- MAPE (Mean Absolute % Error)
- Hit rate (% correct direction)
- Recent track record

### Q: What if a ticker data is missing?

**A:** Application handles gracefully:
- Missing tickers are skipped
- Optimization continues with available data
- Returns empty dict if NO data for any ticker
- Check logs for details

### Q: Can I use different date ranges?

**A:** Yes, but with tradeoffs:

| Period | Pros | Cons |
|--------|------|------|
| 3 months | Recent trends | Less reliable |
| 1 year | Good balance | May miss cycles |
| 2-3 years | Comprehensive | Less recent |
| 5+ years | Full cycles | Outdated data |

**Recommendation:** Use 1-2 years

### Q: How do allocation constraints work?

**A:** 
- **Minimum:** Smallest position allowed (e.g., 0.05 = 5%)
- **Maximum:** Largest position allowed (e.g., 0.40 = 40%)
- **Sum:** Always equals 1.0 (100% invested)

Example:
```
Without constraints:
  AAPL: 100% (concentrated)
  MSFT: 0%

With min=0.1, max=0.4:
  AAPL: 40% (max allowed)
  MSFT: 35% (gets allocated)
  GOOGL: 25% (gets allocated)
```

### Q: Can I manually adjust weights?

**A:** Yes, after getting recommendations:

```python
result = run_optimisation(...)
weights = result['weights']

# Adjust based on your views
weights['AAPL'] = 0.30  # Reduce
weights['MSFT'] = 0.50  # Increase
weights['GOOGL'] = 0.20 # Adjust

# Verify sum = 1.0
assert abs(sum(weights.values()) - 1.0) < 0.01
```

### Q: How do I interpret prediction confidence?

**A:** No confidence interval included, but use:
1. **Recent accuracy** - Check dashboard MAPE
2. **Model fit** - Better fit = more confident
3. **Data quality** - More historical data = more confident
4. **Market volatility** - High volatility = less confident

### Q: What if I have a small portfolio?

**A:** Works fine, but:

```python
# Small portfolio example
small_portfolio = ['AAPL', 'MSFT']  # Just 2 stocks

result = run_optimisation(
    tickers=small_portfolio,
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# Will still optimize, but:
# - Less diversification benefit
# - Simpler optimization problem
# - May focus on single stock
```

**Recommendation:** At least 3-5 stocks for diversification

### Q: Can I use international stocks?

**A:** Yes, yfinance supports them:

```python
international = [
    'AAPL',      # USA
    'ASML.AS',   # Netherlands
    'SAP.DE',    # Germany
    'BP.L',      # UK
    'TSM',       # Taiwan
]

result = run_optimisation(tickers=international, ...)
```

**Note:** Currency differences not handled; returns in local currency

### Q: How do I handle rebalancing?

**A:** Three approaches:

1. **No rebalancing** (buy and hold)
   ```python
   # Run once, keep weights
   weights = result['weights']
   # Don't change weights
   ```

2. **Annual rebalancing**
   ```python
   # Every Jan 1, run optimization
   if today.month == 1 and today.day == 1:
       result = run_optimisation(...)
       new_weights = result['weights']
       # Rebalance to new weights
   ```

3. **Daily rebalancing** (active)
   ```python
   # Run daily, change weights daily
   result = run_optimisation(...)
   daily_weights = result['weights']
   # Rebalance daily
   ```

### Q: What about transaction costs?

**A:** Not currently modeled. To include:
- Larger allocation swings = higher costs
- Consider using `minimum_allocation` constraint
- Don't rebalance too frequently
- Use limit orders to minimize slippage

---

## Support

- **Documentation**: See `API_DOCUMENTATION.md`
- **Deployment**: See `DEPLOYMENT.md`
- **Testing**: Run `pytest tests/ -v`
- **Issues**: Check GitHub repository

