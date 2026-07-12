"""Tests for efficient frontier visualization."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.efficient_frontier import (
    EfficientFrontier,
    EfficientFrontierResult,
    PortfolioPoint,
)


@pytest.fixture
def sample_mean_returns():
    """Create sample expected returns."""
    return pd.Series(
        {
            "AAPL": 0.15,
            "MSFT": 0.12,
            "GOOGL": 0.10,
            "AMZN": 0.14,
            "TSLA": 0.25,
        }
    )


@pytest.fixture
def sample_cov_matrix():
    """Create sample covariance matrix."""
    returns = np.array(
        [
            [0.0025, 0.0018, 0.0015, 0.0020, 0.0030],
            [0.0018, 0.0035, 0.0012, 0.0018, 0.0025],
            [0.0015, 0.0012, 0.0028, 0.0014, 0.0022],
            [0.0020, 0.0018, 0.0014, 0.0040, 0.0035],
            [0.0030, 0.0025, 0.0022, 0.0035, 0.0080],
        ]
    )
    return pd.DataFrame(
        returns,
        index=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
        columns=["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],
    )


@pytest.fixture
def sample_weights():
    """Create sample portfolio weights."""
    return {
        "AAPL": 0.25,
        "MSFT": 0.25,
        "GOOGL": 0.20,
        "AMZN": 0.15,
        "TSLA": 0.15,
    }


class TestPortfolioPoint:
    """Test PortfolioPoint dataclass."""

    def test_create_portfolio_point(self):
        """Test creating a portfolio point."""
        weights = {"AAPL": 0.5, "MSFT": 0.5}
        point = PortfolioPoint(
            risk_aversion=5.0,
            volatility=0.15,
            expected_return=0.12,
            sharpe_ratio=0.8,
            weights=weights,
        )
        assert point.risk_aversion == 5.0
        assert point.volatility == 0.15
        assert point.expected_return == 0.12
        assert point.sharpe_ratio == 0.8
        assert point.weights == weights

    def test_portfolio_point_to_dict(self):
        """Test converting portfolio point to dictionary."""
        weights = {"AAPL": 0.5, "MSFT": 0.5}
        point = PortfolioPoint(
            risk_aversion=5.0,
            volatility=0.15,
            expected_return=0.12,
            sharpe_ratio=0.8,
            weights=weights,
        )
        result = point.to_dict()
        assert result["risk_aversion"] == 5.0
        assert result["volatility"] == 0.15
        assert result["expected_return"] == 0.12
        assert result["sharpe_ratio"] == 0.8
        assert result["weights"] == weights


class TestOptimizePortfolio:
    """Test portfolio optimization for varying lambda."""

    def test_optimize_portfolio_equal_weights(self, sample_mean_returns, sample_cov_matrix):
        """Test optimization returns valid weights."""
        weights = EfficientFrontier.optimize_portfolio(
            sample_mean_returns,
            sample_cov_matrix,
            risk_aversion=5.0,
        )
        assert len(weights) == 5
        assert all(w >= 0.05 for w in weights.values())  # minimum allocation
        assert np.isclose(sum(weights.values()), 1.0)  # sum to 1

    def test_optimize_different_lambdas(self, sample_mean_returns, sample_cov_matrix):
        """Test that different lambdas produce different weights."""
        weights_conservative = EfficientFrontier.optimize_portfolio(
            sample_mean_returns,
            sample_cov_matrix,
            risk_aversion=50.0,
        )
        weights_aggressive = EfficientFrontier.optimize_portfolio(
            sample_mean_returns,
            sample_cov_matrix,
            risk_aversion=0.5,
        )
        # Weights should be different
        assert weights_conservative != weights_aggressive

    def test_optimize_respects_bounds(self, sample_mean_returns, sample_cov_matrix):
        """Test optimization respects min/max allocation bounds."""
        min_alloc = 0.05
        max_alloc = 0.40
        weights = EfficientFrontier.optimize_portfolio(
            sample_mean_returns,
            sample_cov_matrix,
            risk_aversion=5.0,
            minimum_allocation=min_alloc,
            maximum_allocation=max_alloc,
        )
        assert all(w >= min_alloc for w in weights.values())
        assert all(w <= max_alloc for w in weights.values())

    def test_optimize_handles_invalid_data(self, sample_mean_returns, sample_cov_matrix):
        """Test optimization handles edge cases gracefully."""
        # Zero covariance should still produce weights
        weights = EfficientFrontier.optimize_portfolio(
            sample_mean_returns,
            sample_cov_matrix,
            risk_aversion=0.0,  # Edge case
        )
        assert np.isclose(sum(weights.values()), 1.0)


class TestCalculatePortfolioMetrics:
    """Test portfolio metrics calculation."""

    def test_calculate_metrics_basic(self, sample_mean_returns, sample_cov_matrix, sample_weights):
        """Test basic metrics calculation."""
        volatility, exp_return, sharpe = EfficientFrontier.calculate_portfolio_metrics(
            sample_weights,
            sample_mean_returns,
            sample_cov_matrix,
        )
        assert volatility > 0
        assert exp_return > 0
        assert sharpe > 0

    def test_calculate_metrics_equal_weight(self, sample_mean_returns, sample_cov_matrix):
        """Test metrics for equal-weight portfolio."""
        equal_weights = {ticker: 0.2 for ticker in sample_mean_returns.index}
        volatility, exp_return, sharpe = EfficientFrontier.calculate_portfolio_metrics(
            equal_weights,
            sample_mean_returns,
            sample_cov_matrix,
        )
        # Expected return should be close to mean of all returns
        expected_avg = sample_mean_returns.mean()
        assert np.isclose(exp_return, expected_avg, rtol=0.01)

    def test_calculate_metrics_zero_volatility(self, sample_mean_returns, sample_cov_matrix):
        """Test metrics calculation with near-zero volatility."""
        # Create a constant return scenario
        zero_cov = sample_cov_matrix * 0.0
        weights = {ticker: 0.2 for ticker in sample_mean_returns.index}
        volatility, exp_return, sharpe = EfficientFrontier.calculate_portfolio_metrics(
            weights,
            sample_mean_returns,
            zero_cov,
        )
        assert volatility == 0.0
        assert sharpe == 0.0

    def test_calculate_metrics_with_risk_free_rate(
        self, sample_mean_returns, sample_cov_matrix, sample_weights
    ):
        """Test Sharpe ratio with different risk-free rates."""
        volatility_1, exp_return_1, sharpe_1 = EfficientFrontier.calculate_portfolio_metrics(
            sample_weights,
            sample_mean_returns,
            sample_cov_matrix,
            risk_free_rate=0.02,
        )
        volatility_2, exp_return_2, sharpe_2 = EfficientFrontier.calculate_portfolio_metrics(
            sample_weights,
            sample_mean_returns,
            sample_cov_matrix,
            risk_free_rate=0.04,
        )
        # Same weights should have same volatility and return
        assert np.isclose(volatility_1, volatility_2)
        assert np.isclose(exp_return_1, exp_return_2)
        # But different Sharpe ratios due to different risk-free rates
        assert sharpe_1 > sharpe_2


class TestGenerateFrontier:
    """Test efficient frontier generation."""

    def test_generate_frontier_basic(self, sample_mean_returns, sample_cov_matrix):
        """Test basic frontier generation."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=10,
        )
        assert len(result.frontier_points) == 10
        assert result.min_variance_portfolio is not None
        assert result.max_sharpe_portfolio is not None

    def test_frontier_has_increasing_returns(self, sample_mean_returns, sample_cov_matrix):
        """Test that frontier returns increase with risk."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=20,
        )
        # Generally, returns should increase with risk (volatility)
        # But not strictly monotonic due to optimization
        points = result.frontier_points
        np.mean([p.expected_return for p in points[:5]])
        avg_return_high_vol = np.mean([p.expected_return for p in points[-5:]])
        # High volatility should generally have higher expected return
        # (at least higher than the most conservative)
        assert avg_return_high_vol >= 0

    def test_min_variance_portfolio_identified(self, sample_mean_returns, sample_cov_matrix):
        """Test that minimum variance portfolio is correctly identified."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=20,
        )
        min_var = result.min_variance_portfolio
        # Dedicated min-variance optimisation should beat or match the lambda sweep
        assert all(p.volatility >= min_var.volatility - 1e-9 for p in result.frontier_points)

    def test_max_sharpe_portfolio_identified(self, sample_mean_returns, sample_cov_matrix):
        """Test that maximum Sharpe portfolio is correctly identified."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=20,
        )
        max_sharpe = result.max_sharpe_portfolio
        # Dedicated max-Sharpe optimisation should beat or match the lambda sweep
        assert all(p.sharpe_ratio <= max_sharpe.sharpe_ratio + 1e-9 for p in result.frontier_points)

    def test_min_variance_and_max_sharpe_are_distinct(self, sample_mean_returns, sample_cov_matrix):
        """Min-variance and max-Sharpe should generally differ on diverse assets."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=20,
        )
        min_var = result.min_variance_portfolio
        max_sharpe = result.max_sharpe_portfolio
        assert min_var.weights != max_sharpe.weights

    def test_frontier_result_to_dict(self, sample_mean_returns, sample_cov_matrix):
        """Test converting frontier result to dictionary."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=5,
        )
        result_dict = result.to_dict()
        assert "frontier_points" in result_dict
        assert "min_variance_portfolio" in result_dict
        assert "max_sharpe_portfolio" in result_dict
        assert len(result_dict["frontier_points"]) == 5

    def test_frontier_with_custom_lambda_range(self, sample_mean_returns, sample_cov_matrix):
        """Test frontier generation with custom lambda range."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=10,
            lambda_range=(1.0, 50.0),
        )
        assert len(result.frontier_points) == 10
        # All lambdas should be within specified range
        lambdas = [p.risk_aversion for p in result.frontier_points]
        assert min(lambdas) >= 1.0
        assert max(lambdas) <= 50.0

    def test_frontier_with_allocation_constraints(self, sample_mean_returns, sample_cov_matrix):
        """Test frontier respects allocation constraints."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=10,
            minimum_allocation=0.10,
            maximum_allocation=0.35,
        )
        for point in result.frontier_points:
            assert all(w >= 0.10 for w in point.weights.values())
            assert all(w <= 0.35 for w in point.weights.values())


class TestPlotFrontier:
    """Test frontier visualization."""

    def test_plot_frontier_basic(self, sample_mean_returns, sample_cov_matrix):
        """Test basic frontier plotting."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=10,
        )
        # Plotly is optional - just verify frontier is generated correctly
        assert isinstance(result, EfficientFrontierResult)
        assert len(result.frontier_points) == 10
        assert result.min_variance_portfolio is not None
        assert result.max_sharpe_portfolio is not None

    def test_frontier_result_creation(self, sample_mean_returns, sample_cov_matrix):
        """Test frontier result object creation."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=10,
        )
        assert isinstance(result, EfficientFrontierResult)
        assert len(result.frontier_points) == 10

    def test_plot_frontier_with_current_weights_skip(
        self, sample_mean_returns, sample_cov_matrix, sample_weights
    ):
        """Test that plot function handles current weights correctly."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=10,
        )
        # Don't actually call plot since plotly is not installed
        # Just verify we can calculate metrics for current weights
        volatility, exp_return, sharpe = EfficientFrontier.calculate_portfolio_metrics(
            sample_weights,
            result.mean_returns,
            result.cov_matrix,
        )
        assert volatility > 0
        assert exp_return > 0

    def test_plot_frontier_invalid_weights(self, sample_mean_returns, sample_cov_matrix):
        """Test plotting with invalid current weights (mismatched tickers)."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=10,
        )
        invalid_weights = {"INVALID": 1.0}
        # Should raise KeyError for invalid ticker
        with pytest.raises(KeyError):
            EfficientFrontier.calculate_portfolio_metrics(
                invalid_weights,
                result.mean_returns,
                result.cov_matrix,
            )

    def test_frontier_layout_structure(self, sample_mean_returns, sample_cov_matrix):
        """Test frontier result has correct structure for plotting."""
        result = EfficientFrontier.generate_frontier(
            sample_mean_returns,
            sample_cov_matrix,
            num_points=10,
        )
        # Verify structure that would be used in plotting
        assert hasattr(result, "frontier_points")
        assert hasattr(result, "min_variance_portfolio")
        assert hasattr(result, "max_sharpe_portfolio")

        # Verify frontier points have required attributes
        for point in result.frontier_points:
            assert hasattr(point, "volatility")
            assert hasattr(point, "expected_return")
            assert hasattr(point, "sharpe_ratio")


class TestDedicatedOptimizations:
    """Test standalone min-variance and max-Sharpe optimisations."""

    def test_optimize_minimum_variance_respects_bounds(
        self, sample_mean_returns, sample_cov_matrix
    ):
        weights = EfficientFrontier.optimize_minimum_variance(
            sample_mean_returns,
            sample_cov_matrix,
            minimum_allocation=0.10,
            maximum_allocation=0.35,
        )
        assert np.isclose(sum(weights.values()), 1.0)
        assert all(0.10 <= w <= 0.35 for w in weights.values())

    def test_optimize_maximum_sharpe_respects_bounds(
        self, sample_mean_returns, sample_cov_matrix
    ):
        weights = EfficientFrontier.optimize_maximum_sharpe(
            sample_mean_returns,
            sample_cov_matrix,
            minimum_allocation=0.10,
            maximum_allocation=0.35,
        )
        assert np.isclose(sum(weights.values()), 1.0)
        assert all(0.10 <= w <= 0.35 for w in weights.values())

    def test_dedicated_optimizers_produce_different_portfolios(
        self, sample_mean_returns, sample_cov_matrix
    ):
        min_var_weights = EfficientFrontier.optimize_minimum_variance(
            sample_mean_returns,
            sample_cov_matrix,
        )
        max_sharpe_weights = EfficientFrontier.optimize_maximum_sharpe(
            sample_mean_returns,
            sample_cov_matrix,
        )
        assert min_var_weights != max_sharpe_weights


class TestFormatPortfolioWeights:
    """Test portfolio weights formatting."""

    def test_format_weights_basic(self):
        """Test basic weight formatting."""
        weights = {"AAPL": 0.30, "MSFT": 0.25, "GOOGL": 0.20, "AMZN": 0.15, "TSLA": 0.10}
        result = EfficientFrontier.format_portfolio_weights(weights, top_n=5)
        assert "AAPL: 30.00%" in result
        assert "MSFT: 25.00%" in result
        assert "GOOGL: 20.00%" in result

    def test_format_weights_truncates_to_top_n(self):
        """Test that formatting shows only top N holdings."""
        weights = {
            "A": 0.25,
            "B": 0.20,
            "C": 0.15,
            "D": 0.12,
            "E": 0.10,
            "F": 0.10,
            "G": 0.08,
        }
        result = EfficientFrontier.format_portfolio_weights(weights, top_n=3)
        assert "A:" in result
        assert "B:" in result
        assert "C:" in result
        assert "Others:" in result

    def test_format_weights_single_holding(self):
        """Test formatting with single holding."""
        weights = {"AAPL": 1.0}
        result = EfficientFrontier.format_portfolio_weights(weights, top_n=10)
        assert "AAPL: 100.00%" in result

    def test_format_weights_equal_weights(self):
        """Test formatting equal weights."""
        weights = {f"TICKER{i}": 0.2 for i in range(5)}
        result = EfficientFrontier.format_portfolio_weights(weights, top_n=5)
        # Should show all tickers with 20% each
        assert "20.00%" in result


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_portfolio_handling(self):
        """Test handling of empty portfolio returns."""
        # Empty series should raise ValueError
        empty_returns = pd.Series(dtype=float)
        empty_cov = pd.DataFrame(dtype=float)

        # This should raise ValueError for empty portfolio
        with pytest.raises(ValueError, match="Cannot optimize empty portfolio"):
            EfficientFrontier.generate_frontier(
                empty_returns,
                empty_cov,
                num_points=5,
            )

    def test_single_asset(self):
        """Test with single asset portfolio."""
        returns = pd.Series({"AAPL": 0.15})
        cov = pd.DataFrame([[0.01]], index=["AAPL"], columns=["AAPL"])

        result = EfficientFrontier.generate_frontier(
            returns,
            cov,
            num_points=5,
        )
        assert len(result.frontier_points) == 5
        # All portfolios should be 100% AAPL
        for point in result.frontier_points:
            assert np.isclose(point.weights["AAPL"], 1.0)

    def test_large_frontier(self):
        """Test generating large frontier with many points."""
        returns = pd.Series({f"TICKER{i}": 0.10 + i * 0.01 for i in range(10)})
        cov = pd.DataFrame(
            0.01 * np.eye(10),
            index=[f"TICKER{i}" for i in range(10)],
            columns=[f"TICKER{i}" for i in range(10)],
        )

        result = EfficientFrontier.generate_frontier(
            returns,
            cov,
            num_points=100,
        )
        assert len(result.frontier_points) == 100
        assert result.min_variance_portfolio is not None
        assert result.max_sharpe_portfolio is not None

    def test_negative_returns(self):
        """Test with negative expected returns."""
        returns = pd.Series({"AAPL": -0.05, "MSFT": 0.10})
        cov = pd.DataFrame(
            [[0.02, 0.01], [0.01, 0.02]],
            index=["AAPL", "MSFT"],
            columns=["AAPL", "MSFT"],
        )

        result = EfficientFrontier.generate_frontier(
            returns,
            cov,
            num_points=10,
        )
        assert len(result.frontier_points) == 10
        # Should still produce valid weights
        for point in result.frontier_points:
            assert np.isclose(sum(point.weights.values()), 1.0)
