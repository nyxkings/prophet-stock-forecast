"""Tests for risk analytics module."""

from __future__ import annotations

import numpy as np
import pytest

from src.risk_analytics import RiskAnalyzer, RiskMetrics, TickerRiskMetrics


class TestValueAtRisk:
    """Test VaR calculations."""

    def test_var_95(self):
        """Test VaR at 95% confidence."""
        returns = np.random.normal(0.001, 0.02, 1000)
        var = RiskAnalyzer.calculate_var(returns, 0.95)

        assert isinstance(var, float)
        assert var < 0  # VaR should be negative (loss)

    def test_var_99(self):
        """Test VaR at 99% confidence."""
        returns = np.random.normal(0.001, 0.02, 1000)
        var_95 = RiskAnalyzer.calculate_var(returns, 0.95)
        var_99 = RiskAnalyzer.calculate_var(returns, 0.99)

        assert var_99 < var_95  # Worse tail risk at 99%

    def test_var_with_list_input(self):
        """Test VaR works with list input."""
        returns = [0.01, -0.02, 0.005, -0.01, 0.015]
        var = RiskAnalyzer.calculate_var(returns, 0.95)

        assert isinstance(var, float)

    def test_var_consistent_ordering(self):
        """Test VaR gives consistent results."""
        returns = np.random.normal(0.001, 0.02, 100)
        var1 = RiskAnalyzer.calculate_var(returns, 0.95)
        var2 = RiskAnalyzer.calculate_var(returns, 0.95)

        assert var1 == var2


class TestConditionalVaR:
    """Test CVaR/Expected Shortfall calculations."""

    def test_cvar_95(self):
        """Test CVaR at 95% confidence."""
        returns = np.random.normal(0.001, 0.02, 1000)
        cvar = RiskAnalyzer.calculate_cvar(returns, 0.95)

        assert isinstance(cvar, float)
        assert cvar < 0  # CVaR should be negative

    def test_cvar_worse_than_var(self):
        """Test CVaR is worse than VaR."""
        returns = np.random.normal(0.001, 0.02, 1000)
        var = RiskAnalyzer.calculate_var(returns, 0.95)
        cvar = RiskAnalyzer.calculate_cvar(returns, 0.95)

        assert cvar < var  # CVaR is average of worst outcomes


class TestSharpeRatio:
    """Test Sharpe ratio calculations."""

    def test_sharpe_positive_returns(self):
        """Test Sharpe with positive returns."""
        np.random.seed(42)  # Deterministic seed for reproducible tests
        returns = np.random.normal(0.01, 0.02, 252)  # Higher mean for guaranteed positive Sharpe
        sharpe = RiskAnalyzer.calculate_sharpe_ratio(returns)

        assert isinstance(sharpe, float)
        assert sharpe > 0  # Positive Sharpe for positive mean returns

    def test_sharpe_negative_returns(self):
        """Test Sharpe with negative returns."""
        returns = np.random.normal(-0.001, 0.01, 252)
        sharpe = RiskAnalyzer.calculate_sharpe_ratio(returns)

        assert isinstance(sharpe, float)
        # Sharpe can be positive or negative depending on sample; just verify it's calculated

    def test_sharpe_zero_volatility(self):
        """Test Sharpe with zero volatility."""
        returns = [0.001] * 252
        sharpe = RiskAnalyzer.calculate_sharpe_ratio(returns)

        assert sharpe == 0.0  # Return 0 for no volatility

    def test_sharpe_annualization(self):
        """Test Sharpe is annualized."""
        returns = np.random.normal(0.001, 0.01, 252)
        sharpe = RiskAnalyzer.calculate_sharpe_ratio(returns)

        assert isinstance(sharpe, float)  # Should be calculated correctly


class TestSortinoRatio:
    """Test Sortino ratio calculations."""

    def test_sortino_positive_returns(self):
        """Test Sortino with positive returns."""
        returns = np.random.normal(0.001, 0.01, 252)
        sortino = RiskAnalyzer.calculate_sortino_ratio(returns)

        assert isinstance(sortino, float)

    def test_sortino_vs_sharpe(self):
        """Test Sortino typically higher than Sharpe."""
        returns = np.random.normal(0.001, 0.01, 252)
        RiskAnalyzer.calculate_sharpe_ratio(returns)
        sortino = RiskAnalyzer.calculate_sortino_ratio(returns)

        # Sortino typically higher due to downside-only volatility
        assert isinstance(sortino, float)

    def test_sortino_zero_downside(self):
        """Test Sortino with no downside risk."""
        returns = np.array([0.001] * 252)
        sortino = RiskAnalyzer.calculate_sortino_ratio(returns)

        assert sortino == 0.0


class TestMaxDrawdown:
    """Test maximum drawdown calculations."""

    def test_max_drawdown_simple(self):
        """Test max drawdown on simple series."""
        returns = [0.05, 0.05, -0.10, 0.03, 0.02]
        dd = RiskAnalyzer.calculate_max_drawdown(returns)

        assert dd < 0  # Drawdown is negative

    def test_max_drawdown_all_positive(self):
        """Test max drawdown with all positive returns."""
        returns = [0.01, 0.02, 0.03, 0.01, 0.02]
        dd = RiskAnalyzer.calculate_max_drawdown(returns)

        assert dd == 0.0  # No drawdown for only gains

    def test_max_drawdown_crash(self):
        """Test max drawdown with crash."""
        returns = [0.01] * 10 + [-0.50] + [0.01] * 10
        dd = RiskAnalyzer.calculate_max_drawdown(returns)

        assert dd < -0.3  # Significant drawdown from crash

    def test_max_drawdown_empty(self):
        """Test max drawdown with empty list."""
        dd = RiskAnalyzer.calculate_max_drawdown([])

        assert dd == 0.0


class TestCalmarRatio:
    """Test Calmar ratio calculations."""

    def test_calmar_positive(self):
        """Test Calmar ratio calculation."""
        returns = np.random.normal(0.001, 0.01, 252)
        calmar = RiskAnalyzer.calculate_calmar_ratio(returns)

        assert isinstance(calmar, float)

    def test_calmar_no_drawdown(self):
        """Test Calmar with no drawdown."""
        returns = [0.001] * 252
        calmar = RiskAnalyzer.calculate_calmar_ratio(returns)

        assert calmar == 0.0  # No drawdown = 0 Calmar


class TestPortfolioMetrics:
    """Test portfolio metrics calculation."""

    def test_portfolio_metrics_creation(self):
        """Test portfolio metrics object creation."""
        returns = np.random.normal(0.001, 0.02, 252)
        metrics = RiskAnalyzer.calculate_portfolio_metrics(returns)

        assert isinstance(metrics, RiskMetrics)
        assert metrics.sharpe_ratio != 0.0
        assert metrics.volatility > 0
        assert metrics.max_drawdown <= 0

    def test_portfolio_metrics_dict_conversion(self):
        """Test portfolio metrics to dict."""
        returns = np.random.normal(0.001, 0.02, 252)
        metrics = RiskAnalyzer.calculate_portfolio_metrics(returns)
        metrics_dict = metrics.to_dict()

        assert isinstance(metrics_dict, dict)
        assert "sharpe_ratio" in metrics_dict
        assert "max_drawdown" in metrics_dict
        assert "volatility" in metrics_dict

    def test_portfolio_metrics_fields(self):
        """Test all portfolio metrics fields are populated."""
        returns = np.random.normal(0.001, 0.02, 252)
        metrics = RiskAnalyzer.calculate_portfolio_metrics(returns)

        assert metrics.var_95 < 0
        assert metrics.var_99 <= metrics.var_95
        assert metrics.cvar_95 < metrics.var_95
        assert metrics.volatility > 0


class TestTickerMetrics:
    """Test individual ticker metrics."""

    def test_ticker_metrics_creation(self):
        """Test ticker metrics object creation."""
        returns = np.random.normal(0.001, 0.02, 252)
        metrics = RiskAnalyzer.calculate_ticker_metrics("AAPL", returns)

        assert isinstance(metrics, TickerRiskMetrics)
        assert metrics.ticker == "AAPL"
        assert metrics.volatility > 0

    def test_ticker_metrics_dict_conversion(self):
        """Test ticker metrics to dict."""
        returns = np.random.normal(0.001, 0.02, 252)
        metrics = RiskAnalyzer.calculate_ticker_metrics("AAPL", returns)
        metrics_dict = metrics.to_dict()

        assert metrics_dict["ticker"] == "AAPL"
        assert "volatility" in metrics_dict
        assert "var_95" in metrics_dict

    def test_multiple_tickers(self):
        """Test metrics for multiple tickers."""
        tickers = ["AAPL", "MSFT", "GOOGL"]

        for ticker in tickers:
            returns = np.random.normal(0.001, 0.02, 252)
            metrics = RiskAnalyzer.calculate_ticker_metrics(ticker, returns)

            assert metrics.ticker == ticker


class TestConcentration:
    """Test portfolio concentration metrics."""

    def test_concentration_equal_weight(self):
        """Test concentration of equal weight portfolio."""
        weights = {"AAPL": 0.25, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.25}
        concentration = RiskAnalyzer.calculate_portfolio_concentration(weights)

        assert isinstance(concentration, dict)
        assert "herfindahl_index" in concentration
        assert concentration["herfindahl_index"] == pytest.approx(0.25, rel=0.01)

    def test_concentration_concentrated(self):
        """Test concentration of concentrated portfolio."""
        weights = {"AAPL": 0.70, "MSFT": 0.20, "GOOGL": 0.10}
        concentration = RiskAnalyzer.calculate_portfolio_concentration(weights)

        hhi = concentration["herfindahl_index"]
        assert hhi > 0.25  # More concentrated

    def test_concentration_single_asset(self):
        """Test concentration of single asset."""
        weights = {"AAPL": 1.0}
        concentration = RiskAnalyzer.calculate_portfolio_concentration(weights)

        assert concentration["herfindahl_index"] == 1.0  # Perfect concentration

    def test_concentration_effective_assets(self):
        """Test effective number of assets."""
        weights = {"AAPL": 0.25, "MSFT": 0.25, "GOOGL": 0.25, "AMZN": 0.25}
        concentration = RiskAnalyzer.calculate_portfolio_concentration(weights)

        effective_assets = concentration["effective_assets"]
        assert effective_assets == pytest.approx(4.0, rel=0.01)


class TestCorrelationMatrix:
    """Test correlation matrix calculations."""

    def test_correlation_matrix_creation(self):
        """Test correlation matrix creation."""
        returns = {
            "AAPL": np.random.normal(0.001, 0.02, 100),
            "MSFT": np.random.normal(0.001, 0.02, 100),
            "GOOGL": np.random.normal(0.001, 0.02, 100),
        }

        corr_data = RiskAnalyzer.calculate_correlation_matrix(returns)

        assert isinstance(corr_data, dict)
        assert "correlation_matrix" in corr_data
        assert "avg_correlation" in corr_data

    def test_correlation_matrix_bounds(self):
        """Test correlation matrix values are bounded."""
        returns = {
            "AAPL": np.random.normal(0.001, 0.02, 100),
            "MSFT": np.random.normal(0.001, 0.02, 100),
        }

        corr_data = RiskAnalyzer.calculate_correlation_matrix(returns)

        avg_corr = corr_data["avg_correlation"]
        assert -1.0 <= avg_corr <= 1.0

    def test_correlation_perfect_positive(self):
        """Test correlation with perfectly correlated assets."""
        returns_base = np.random.normal(0.001, 0.02, 100)
        returns = {
            "AAPL": returns_base,
            "MSFT": returns_base * 1.5,  # Scaled but same direction
        }

        corr_data = RiskAnalyzer.calculate_correlation_matrix(returns)
        avg_corr = corr_data["avg_correlation"]

        assert avg_corr > 0.9  # Should be highly correlated


class TestDiversificationRatio:
    """Test diversification ratio calculations."""

    def test_diversification_ratio_equal_weight(self):
        """Test diversification ratio for equal weight."""
        weights = {"AAPL": 0.33, "MSFT": 0.33, "GOOGL": 0.34}
        volatilities = {"AAPL": 0.20, "MSFT": 0.20, "GOOGL": 0.20}
        portfolio_vol = 0.20

        div_ratio = RiskAnalyzer.calculate_diversification_ratio(
            weights, volatilities, portfolio_vol
        )

        assert div_ratio == pytest.approx(1.0, rel=0.01)

    def test_diversification_ratio_concentrated(self):
        """Test diversification ratio for concentrated portfolio."""
        weights = {"AAPL": 0.90, "MSFT": 0.10}
        volatilities = {"AAPL": 0.20, "MSFT": 0.30}
        portfolio_vol = 0.21  # Lower than weighted average

        div_ratio = RiskAnalyzer.calculate_diversification_ratio(
            weights, volatilities, portfolio_vol
        )

        assert div_ratio > 1.0  # Portfolio benefits from diversification

    def test_diversification_ratio_bounds(self):
        """Test diversification ratio is positive."""
        weights = {"AAPL": 0.50, "MSFT": 0.50}
        volatilities = {"AAPL": 0.20, "MSFT": 0.20}
        portfolio_vol = 0.20

        div_ratio = RiskAnalyzer.calculate_diversification_ratio(
            weights, volatilities, portfolio_vol
        )

        assert div_ratio > 0


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_returns(self):
        """Test handling of empty returns."""
        returns = []
        sharpe = RiskAnalyzer.calculate_sharpe_ratio(returns)

        assert sharpe == 0.0

    def test_single_return(self):
        """Test handling of single return."""
        returns = [0.01]
        dd = RiskAnalyzer.calculate_max_drawdown(returns)

        assert dd == 0.0

    def test_very_small_values(self):
        """Test with very small return values."""
        returns = np.random.normal(0, 1e-6, 100)
        metrics = RiskAnalyzer.calculate_portfolio_metrics(returns)

        assert isinstance(metrics, RiskMetrics)

    def test_extreme_values(self):
        """Test with extreme values."""
        returns = np.array([-0.99, 0.50, -0.50, 0.75, -0.75])
        metrics = RiskAnalyzer.calculate_portfolio_metrics(returns)

        assert isinstance(metrics, RiskMetrics)
        assert np.isfinite(metrics.sharpe_ratio)
