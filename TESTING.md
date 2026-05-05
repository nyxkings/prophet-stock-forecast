# Testing Guide

## Overview

This document describes the testing strategy, test structure, and how to run tests for the Prophet Portfolio Optimization project.

## Test Organization

### Test Files

- **`conftest.py`**: Shared pytest fixtures and configuration used across all tests
- **`test_database.py`**: Unit tests for database operations
- **`test_extractor.py`**: Unit tests for data extraction module
- **`test_model.py`**: Unit tests for Prophet model
- **`test_optimiser.py`**: Unit tests for portfolio optimization
- **`test_processor.py`**: Unit tests for data processing
- **`test_integration.py`**: End-to-end integration tests for the full pipeline
- **`test_edge_cases.py`**: Edge case and error handling tests
- **`test_utils.py`**: Testing utilities and helper functions

### Test Categories

Tests are organized by category using pytest markers:

- **`@pytest.mark.unit`**: Unit tests for individual functions/classes
- **`@pytest.mark.integration`**: End-to-end integration tests
- **`@pytest.mark.edge_cases`**: Edge cases and error scenarios
- **`@pytest.mark.slow`**: Tests that take significant time
- **`@pytest.mark.mock`**: Tests using mocks extensively

## Running Tests

### Run All Tests

```bash
make test
```

Or with poetry:

```bash
poetry run pytest
```

### Run Specific Test Categories

```bash
# Run only integration tests
poetry run pytest -m integration

# Run only edge case tests
poetry run pytest -m edge_cases

# Run all except slow tests
poetry run pytest -m "not slow"
```

### Run Specific Test File

```bash
poetry run pytest tests/test_model.py -v
```

### Run Specific Test Class or Function

```bash
# Run a specific test class
poetry run pytest tests/test_integration.py::TestFullPipeline -v

# Run a specific test function
poetry run pytest tests/test_integration.py::TestFullPipeline::test_run_optimisation_full_pipeline -v
```

### Run with Coverage Report

```bash
# Generate coverage report
poetry run pytest --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Run with Verbose Output

```bash
poetry run pytest -v
```

### Run with Print Statements

```bash
poetry run pytest -s
```

## Coverage Requirements

### Current Target

- **Overall Coverage**: 85%+
- **Core Modules**: 90%+ (model.py, optimiser.py, main.py)
- **Utilities**: 80%+ (processor.py, extractor.py)

### Viewing Coverage

Coverage reports are generated automatically with `make test`:

```bash
# View in terminal
poetry run pytest --cov=src --cov-report=term-missing

# View in HTML
poetry run pytest --cov=src --cov-report=html
open htmlcov/index.html
```

## Test Fixtures

### Available Fixtures

Common fixtures provided in `conftest.py`:

- **`sample_ticker_data`**: Raw OHLCV data from yfinance
- **`sample_processed_data`**: Preprocessed data with Price/Returns columns
- **`sample_predictions`**: Sample Prophet predictions
- **`sample_actual_prices`**: Recent price history
- **`sample_optimization_result`**: Sample portfolio weights
- **`mock_yfinance`**: Mocks yfinance API calls
- **`mock_supabase`**: Mocks Supabase database calls
- **`mock_prophet_model`**: Mocks Prophet model training/prediction
- **`temp_env_vars`**: Sets temporary environment variables
- **`caplog_handler`**: Configured logging capture

### Using Fixtures

```python
def test_example(sample_processed_data, mock_yfinance):
    """Example test using fixtures."""
    result = some_function(sample_processed_data)
    assert result is not None
```

## Test Utilities

The `test_utils.py` module provides helper functions:

### Data Generation

```python
from tests.test_utils import create_sample_price_series, create_correlated_portfolio

# Create realistic price series
prices = create_sample_price_series(start_price=100, num_days=252)

# Create correlated portfolio
portfolio = create_correlated_portfolio(
    tickers=["AAPL", "MSFT", "GOOGL"],
    num_days=252
)
```

### Assertions

```python
from tests.test_utils import assert_valid_weights, assert_predictions_valid

# Check portfolio weights
assert_valid_weights(weights)

# Check prediction structure
assert_predictions_valid(predictions, predicted_returns, tickers)
```

### DataFrames

```python
from tests.test_utils import assert_dataframe_properties, compare_dataframes

# Check DataFrame properties
assert_dataframe_properties(
    df,
    expected_columns=["Price", "Returns"],
    min_rows=100
)
```

## Mocking Strategy

### External API Calls

All external API calls are mocked to:
- Speed up tests (no network latency)
- Avoid rate limiting
- Ensure reproducible results
- Work offline

**Mocked Services:**
- `yfinance`: Stock data API
- `Supabase`: Database
- `Prophet`: Time series model (optional, can test with real data)

### Mock Examples

```python
def test_with_mocks(mock_yfinance, mock_supabase):
    """Test with external dependencies mocked."""
    # yfinance calls will use mock_yfinance fixture
    result = extract_data(["AAPL"], "2023-01-01", "2023-12-31")
    
    # Supabase calls will use mock_supabase fixture
    save_results_to_supabase(result)
```

## Edge Cases Tested

### Data Extraction
- Missing data points
- Invalid ticker symbols
- Single data point
- All NaN values

### Data Processing
- Empty portfolios
- Misaligned date ranges
- Data beyond lookback period

### Prophet Model
- Constant prices (zero volatility)
- Extreme volatility
- Short time series

### Portfolio Optimization
- Single asset portfolios
- Zero variance returns
- Negative returns
- Extreme constraints

### Database
- Missing credentials
- NaN values
- Large portfolios (100+ assets)

## Writing New Tests

### Test Structure

```python
import pytest
from src.module import function_to_test

@pytest.mark.unit  # Add category marker
class TestFunctionName:
    """Test suite for function_to_test."""
    
    def test_happy_path(self, sample_data):
        """Test normal operation."""
        result = function_to_test(sample_data)
        assert result is not None
    
    def test_error_case(self):
        """Test error handling."""
        with pytest.raises(ValueError):
            function_to_test(invalid_input)
```

### Best Practices

1. **One assertion per test** (or related assertions for same concept)
2. **Descriptive test names** that explain what is being tested
3. **Use fixtures** for common setup
4. **Mock external dependencies** (yfinance, Supabase, Prophet)
5. **Test both success and failure paths**
6. **Add docstrings** explaining test purpose
7. **Use type hints** in test functions

### Example: Adding a New Test

```python
@pytest.mark.integration
class TestNewFeature:
    """Test new feature X."""
    
    def test_feature_basic_operation(self, sample_processed_data):
        """Test that feature X works with normal data."""
        from src.new_module import new_feature
        
        result = new_feature(sample_processed_data)
        
        assert result is not None
        assert len(result) > 0
    
    def test_feature_with_edge_case(self):
        """Test that feature X handles edge cases."""
        from src.new_module import new_feature
        
        with pytest.raises(ValueError):
            new_feature({})
```

## Continuous Integration

Tests run automatically on CircleCI:

- **Lint**: `poetry run ruff check src tests`
- **Type Check**: `poetry run mypy src`
- **Tests**: `poetry run pytest --cov=src`

See `.circleci/config.yml` for details.

## Troubleshooting

### Import Errors

```bash
# Ensure project is properly installed
poetry install

# Verify Python path
poetry run python -c "import src; print(src.__file__)"
```

### Mock Not Working

- Check fixture name matches parameter
- Ensure patch path matches actual import
- Verify mock is being used before cleanup

### Slow Tests

```bash
# Run only fast tests
poetry run pytest -m "not slow"

# Find slowest tests
poetry run pytest --durations=10
```

### Coverage Not Updated

```bash
# Clear coverage cache
rm -rf .coverage htmlcov/

# Regenerate coverage
poetry run pytest --cov=src --cov-report=html
```

## Test Metrics

### Current Coverage

Monitor and update coverage metrics:

```bash
# Get summary
poetry run coverage report

# Get detailed report by file
poetry run coverage report --skip-covered

# Generate HTML report
poetry run coverage html
```

### Target Metrics

- **Line Coverage**: 85%+
- **Branch Coverage**: 75%+
- **Function Coverage**: 90%+

## Next Steps

See [Phase 1 Checklist](../todo.md#phase-1-testing--quality-assurance-high-priority) for remaining testing tasks.
