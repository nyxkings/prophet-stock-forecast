# User Guide

Quick start guide for using the Prophet Portfolio Optimization system.

## Table of Contents
1. [Quickstart](#quickstart)
2. [Running the Dashboard](#running-the-dashboard)
3. [Interpreting Results](#interpreting-results)
4. [Configuration](#configuration)
5. [Common Scenarios](#common-scenarios)
6. [FAQ](#faq)

---

## Quickstart

### Running a Single Optimization

The simplest way to get started:

```python
from src.main import run_optimisation
from datetime import datetime

# Run optimization for 12 major stocks
result = run_optimisation(
    tickers=['AAPL', 'MSFT', 'GOOGL', 'AMZN'],
    start_date='2023-01-01',
    end_date='2024-05-06'
)

# Results
if result:
    print(f"Optimization Date: {result['date']}")
    print(f"Predicted Prices: {result['predictions']}")
    print(f"Optimal Weights: {result['weights']}")
else:
    print("Optimization failed")
```

### Expected Output

```
Optimization Date: 2024-05-07
Predicted Prices: 
  AAPL: $190.25
  MSFT: $445.50
  GOOGL: $165.75
  AMZN: $185.30

Optimal Weights:
  AAPL: 25.0%
  MSFT: 35.0%
  GOOGL: 20.0%
  AMZN: 20.0%

Total Portfolio Value: $100,000
  AAPL: $25,000
  MSFT: $35,000
  GOOGL: $20,000
  AMZN: $20,000
```

---

## Running the Dashboard

### Web Interface

**Start dashboard:**
```bash
streamlit run src/streamlit_app.py
```

**Access in browser:**
```
http://localhost:8501
```

### Dashboard Features

#### 1. **Predictions Panel**
Shows:
- Next-day price predictions for each stock
- Predicted returns (% change)
- Confidence intervals

#### 2. **Historical Comparison**
Compares:
- Predicted prices vs actual prices over past 30 days
- Prediction accuracy (MAPE, RMSE)
- Trend direction (correct/incorrect calls)

#### 3. **Portfolio Allocation**
Displays:
- Optimal weights recommended
- Current allocation (if previously implemented)
- Weight changes vs previous day

#### 4. **Performance Metrics**
Shows:
- Prediction accuracy (MAPE, MAE)
- Portfolio volatility
- Correlation matrix
- Sharpe ratio (if historical data available)

---

## Interpreting Results

### Understanding Portfolio Weights

**What they mean:**
- Weight = percentage of portfolio allocated to that stock
- Weights must sum to 100%
- Optimize recommends rebalancing portfolio to match these weights

**Example:**
```
Current Portfolio (100,000):
  AAPL: $40,000 (40%)
  MSFT: $30,000 (30%)
  GOOGL: $20,000 (20%)
  AMZN: $10,000 (10%)

Optimization Recommends:
  AAPL: 25% → Reduce to $25,000 (sell $15,000)
  MSFT: 35% → Increase to $35,000 (buy $5,000)
  GOOGL: 20% → Keep at $20,000 (no change)
  AMZN: 20% → Increase to $20,000 (buy $10,000)
```

### Interpreting Predictions

**Price Predictions:**
- Based on next trading day only
- Uses historical trend, seasonality, holidays
- Includes 95% confidence interval

**Return Predictions:**
- Calculated as: (Predicted Price - Current Price) / Current Price
- Positive = expected price increase
- Negative = expected price decrease

### Understanding Accuracy Metrics

**MAPE (Mean Absolute Percentage Error):**
- Measures average prediction error as percentage
- Lower is better
- Below 5% = excellent
- 5-10% = good
- Above 10% = acceptable

**Sharpe Ratio:**
- Risk-adjusted return metric
- Higher is better (above 1.0 is good)
- Formula: (Return - Risk-Free Rate) / Volatility

**Volatility:**
- Standard deviation of daily returns
- Measures risk/unpredictability
- Higher = more volatile (risky)

---

## Configuration

### Customizing Your Portfolio

**Edit src/settings.py:**

```python
# Change portfolio tickers
PORTFOLIO_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN',  # Add/remove tickers
]

# Adjust risk parameters
RISK_AVERSION = 5.0  # 1-10 scale
# 1.0 = aggressive (emphasize returns)
# 5.0 = balanced
# 10.0 = conservative (emphasize stability)

# Set allocation constraints
MINIMUM_ALLOCATION = 0.05  # Min 5% per stock
MAXIMUM_ALLOCATION = 1.0   # Max 100% per stock

# Adjust date range
START_DATE = "2023-01-01"  # Historical data start
```

### Risk Aversion Parameter

How different values affect allocation:

**Low Risk Aversion (1.0) - Aggressive:**
```
Emphasis: Maximize Returns
Result: Concentrated portfolio
Example: AAPL: 60%, MSFT: 25%, GOOGL: 15%
Risk: High volatility
```

**Medium Risk Aversion (5.0) - Balanced:**
```
Emphasis: Balance Returns & Risk
Result: Moderate diversification
Example: AAPL: 25%, MSFT: 35%, GOOGL: 20%, AMZN: 20%
Risk: Medium volatility
```

**High Risk Aversion (10.0) - Conservative:**
```
Emphasis: Minimize Risk
Result: Well-diversified portfolio
Example: AAPL: 20%, MSFT: 25%, GOOGL: 25%, AMZN: 30%
Risk: Low volatility
```

### Allocation Constraints

**Minimum Allocation:**
- Default: 5% per stock
- Prevents tiny allocations
- If you want equal weight: set to 25% for 4 stocks

**Maximum Allocation:**
- Default: 100% (can go all-in on one stock)
- Conservative setting: 40% (max 40% in any stock)

---

## Common Scenarios

### Scenario 1: Rebuild Portfolio from Scratch

```python
from src.main import run_optimisation

# Get latest recommendations
result = run_optimisation(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    start_date='2024-01-01',
    end_date='2024-05-07'
)

portfolio_value = 100_000  # $100,000 to invest

for ticker, weight in result['weights'].items():
    allocation = portfolio_value * weight
    print(f"Buy ${allocation:,.0f} of {ticker}")

# Example output:
# Buy $25,000 of AAPL
# Buy $35,000 of MSFT
# Buy $40,000 of GOOGL
```

### Scenario 2: Rebalance Existing Portfolio

```python
from src.main import run_optimisation

current_portfolio = {
    'AAPL': 40_000,
    'MSFT': 30_000,
    'GOOGL': 30_000
}

result = run_optimisation(
    tickers=list(current_portfolio.keys()),
    start_date='2024-01-01',
    end_date='2024-05-07'
)

total_value = sum(current_portfolio.values())

print("Rebalancing Actions:")
for ticker, weight in result['weights'].items():
    target = total_value * weight
    current = current_portfolio[ticker]
    change = target - current
    
    if change > 0:
        print(f"BUY ${change:,.0f} of {ticker}")
    elif change < 0:
        print(f"SELL ${abs(change):,.0f} of {ticker}")
    else:
        print(f"HOLD {ticker}")

# Example output:
# SELL $15,000 of AAPL
# BUY $5,000 of MSFT
# BUY $10,000 of GOOGL
```

### Scenario 3: Risk-Adjusted Portfolio

```python
from src.optimiser import optimize_portfolio_mean_variance
from src.extractor import extract_data
from src.processor import preprocess_data

# Extract and prepare data
raw_data = extract_data(
    ['AAPL', 'MSFT', 'GOOGL'],
    '2023-01-01',
    '2024-05-07'
)
data = preprocess_data(raw_data)

# Get different risk profiles
conservative = optimize_portfolio_mean_variance(
    data, risk_aversion=10.0
)
balanced = optimize_portfolio_mean_variance(
    data, risk_aversion=5.0
)
aggressive = optimize_portfolio_mean_variance(
    data, risk_aversion=1.0
)

print("Conservative:", conservative)
print("Balanced:", balanced)
print("Aggressive:", aggressive)
```

### Scenario 4: Monitor Prediction Accuracy

```python
from src.main import run_optimisation
import pandas as pd

# Historical tracking
results_history = []

for month in range(1, 13):
    result = run_optimisation(
        tickers=['AAPL', 'MSFT', 'GOOGL'],
        start_date=f'2023-{month:02d}-01',
        end_date=f'2023-{month:02d}-28'
    )
    
    if result:
        results_history.append({
            'date': result['date'],
            'accuracy': calculate_accuracy(result)
        })

# Analyze trends
df = pd.DataFrame(results_history)
print(df.describe())
```

---

## FAQ

### Q: How often should I rebalance my portfolio?

**A:** Weekly rebalancing is reasonable. Daily rebalancing incurs transaction costs. Monthly is conservative. 

**Recommendation:**
- Weekly for active traders
- Monthly for most investors
- Quarterly for long-term investors

### Q: What if a prediction seems wrong?

**A:** 
- Predictions are statistical models with ~5-10% MAPE
- They can fail during market shocks or extreme events
- Always use as guidance, not absolute truth
- Consider combining with other analysis

### Q: How much historical data do I need?

**A:**
- Minimum: 6 months
- Recommended: 1-2 years
- Longer history = better seasonality capture
- Too long (>10 years) = includes old market conditions

### Q: Can I use this for crypto or bonds?

**A:**
- Crypto: Yes, but higher volatility = less reliable
- Bonds: Not recommended (Prophet works best with volatile daily data)
- Forex: Yes, forex has daily data
- Commodities: Yes, with commodity tickers

### Q: What's a good risk aversion value?

**A:**
- **1-3**: Aggressive growth (stock trader)
- **3-6**: Balanced (typical investor)
- **6-10**: Conservative (retiree)

Start with 5.0 and adjust based on comfort level.

### Q: How accurate are the predictions?

**A:**
- Typical MAPE: 5-8% for large-cap stocks
- Range: 3-15% depending on volatility
- Accuracy decreases with market shocks
- More accurate for stable companies (Microsoft, Apple)
- Less accurate for volatile stocks (Tesla, crypto)

### Q: What if a stock data fetch fails?

**A:**
- System continues with other stocks
- Missing stocks are excluded from portfolio
- Check logs for specific error
- Usually temporary (retry next day)

### Q: Can I add more than 20 stocks?

**A:** 
- Yes, but diminishing returns
- More stocks = more computation time
- More stocks = lower weight per stock
- Optimal: 10-20 stocks
- Maximum tested: 50 stocks

### Q: Is this financial advice?

**A:** 
**NO.** This is for educational/illustrative purposes only.
- Past performance ≠ future results
- Always consult a financial advisor
- Use at your own risk
- Author is not responsible for investment losses

### Q: How do I troubleshoot prediction failures?

Check in this order:
1. Internet connection (can reach yfinance?)
2. Valid tickers (do they exist?)
3. Date range (is data available?)
4. Logs: Check system logs for errors
5. Credentials: Are Supabase credentials set?

### Q: Can I use this in production?

**A:** 
- Yes, but with caution
- Tested with ~$5,000 portfolios
- Add monitoring and alerts
- Use conservative settings initially
- Test with paper trading first

### Q: What's the typical runtime?

**A:**
- 12 stocks: ~15-20 seconds
- 30 stocks: ~30-40 seconds
- 50 stocks: ~60-120 seconds

### Q: How do I report a bug?

**A:**
- GitHub Issues: https://github.com/nyxkings/prophet-stock-forecast/issues
- Include: error message, stocks, date range
- Check existing issues first

---

## Example: Complete Workflow

```python
# 1. Run optimization
from src.main import run_optimisation

result = run_optimisation(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    start_date='2024-01-01',
    end_date='2024-05-07'
)

# 2. Calculate allocation amounts
portfolio_value = 100_000
allocations = {}

for ticker, weight in result['weights'].items():
    allocations[ticker] = portfolio_value * weight

# 3. Execute trades
print("Suggested Trades:")
for ticker, amount in allocations.items():
    print(f"  Buy ${amount:,.0f} of {ticker}")

# 4. Monitor results
print("\nPredicted Performance:")
print(f"Expected Returns: {result['predicted_returns']}")

# 5. Track accuracy (next day)
actual_prices = ...  # Fetch from broker
predictions = result['predictions']

accuracy = calculate_accuracy(predictions, actual_prices)
print(f"\nPrediction Accuracy: {accuracy:.1%}")

# 6. Rebalance next week
# Repeat process
```

---

## Next Steps

- **Advanced**: Read [API Documentation](API.md)
- **Architecture**: See [Architecture Docs](ARCHITECTURE.md)
- **Deployment**: Check [Deployment Guide](DEPLOYMENT.md)
- **Contributing**: See [Testing Guide](TESTING.md)

---

**Need Help?**
- GitHub Issues: https://github.com/nyxkings/prophet-stock-forecast/issues
- Subreddit: r/algotrading, r/investing
- Email: Check repo README for contact

**Disclaimer**: This software is provided "AS-IS" without warranty. Past performance is not indicative of future results. Always consult a financial advisor before making investment decisions.

---

**Last Updated**: May 7, 2024
