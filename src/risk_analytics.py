"""Risk analytics for portfolio optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class RiskMetrics:
    """Risk analysis metrics."""

    var_95: float  # Value at Risk at 95% confidence
    var_99: float  # Value at Risk at 99% confidence
    cvar_95: float  # Conditional Value at Risk (Expected Shortfall) at 95%
    cvar_99: float  # Conditional Value at Risk at 99%
    sharpe_ratio: float  # Annualized Sharpe ratio
    sortino_ratio: float  # Downside Sharpe ratio
    max_drawdown: float  # Maximum drawdown
    calmar_ratio: float  # Return / Max Drawdown
    volatility: float  # Annualized volatility
    skewness: float  # Distribution skewness
    kurtosis: float  # Distribution kurtosis
    beta: float  # Market beta (optional)
    alpha: float  # Jensen's alpha (optional)

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "cvar_99": self.cvar_99,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "calmar_ratio": self.calmar_ratio,
            "volatility": self.volatility,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "beta": self.beta,
            "alpha": self.alpha,
        }


@dataclass
class TickerRiskMetrics:
    """Risk metrics for individual ticker."""

    ticker: str
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    volatility: float
    skewness: float
    kurtosis: float
    return_mean: float
    return_std: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ticker": self.ticker,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "cvar_99": self.cvar_99,
            "volatility": self.volatility,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "return_mean": self.return_mean,
            "return_std": self.return_std,
        }


class RiskAnalyzer:
    """Analyze portfolio and asset risk metrics."""

    @staticmethod
    def calculate_var(
        returns: np.ndarray | list[float],
        confidence_level: float = 0.95,
    ) -> float:
        """Calculate Value at Risk (VaR).

        Args:
            returns: Array of returns
            confidence_level: Confidence level (0.95 or 0.99)

        Returns:
            VaR at specified confidence level
        """
        returns_array = np.array(returns)
        return float(np.percentile(returns_array, (1 - confidence_level) * 100))

    @staticmethod
    def calculate_cvar(
        returns: np.ndarray | list[float],
        confidence_level: float = 0.95,
    ) -> float:
        """Calculate Conditional Value at Risk (CVaR/Expected Shortfall).

        Args:
            returns: Array of returns
            confidence_level: Confidence level (0.95 or 0.99)

        Returns:
            CVaR at specified confidence level
        """
        returns_array = np.array(returns)
        var = np.percentile(returns_array, (1 - confidence_level) * 100)
        return float(np.mean(returns_array[returns_array <= var]))

    @staticmethod
    def calculate_sharpe_ratio(
        returns: np.ndarray | list[float],
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate annualized Sharpe ratio.

        Args:
            returns: Array of returns (daily)
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year (default: 252)

        Returns:
            Annualized Sharpe ratio
        """
        returns_array = np.array(returns)
        excess_returns = returns_array - (risk_free_rate / periods_per_year)

        if len(excess_returns) == 0 or np.std(excess_returns) == 0:
            return 0.0

        return float(
            (np.mean(excess_returns) / np.std(excess_returns)) * np.sqrt(periods_per_year)
        )

    @staticmethod
    def calculate_sortino_ratio(
        returns: np.ndarray | list[float],
        risk_free_rate: float = 0.02,
        periods_per_year: int = 252,
    ) -> float:
        """Calculate annualized Sortino ratio (downside risk only).

        Args:
            returns: Array of returns
            risk_free_rate: Annual risk-free rate
            periods_per_year: Trading periods per year

        Returns:
            Annualized Sortino ratio
        """
        returns_array = np.array(returns)
        excess_returns = returns_array - (risk_free_rate / periods_per_year)

        # Only consider downside volatility (negative returns)
        downside_returns = np.minimum(excess_returns, 0)
        downside_volatility = np.sqrt(np.mean(downside_returns**2))

        if downside_volatility == 0:
            return 0.0

        return float(
            (np.mean(excess_returns) / downside_volatility) * np.sqrt(periods_per_year)
        )

    @staticmethod
    def calculate_max_drawdown(returns: np.ndarray | list[float]) -> float:
        """Calculate maximum drawdown.

        Args:
            returns: Array of returns

        Returns:
            Maximum drawdown (negative value)
        """
        returns_array = np.array(returns)
        cumulative_returns = np.cumprod(1 + returns_array)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max) / running_max

        return float(np.min(drawdown)) if len(drawdown) > 0 else 0.0

    @staticmethod
    def calculate_calmar_ratio(
        returns: np.ndarray | list[float],
        periods_per_year: int = 252,
    ) -> float:
        """Calculate Calmar ratio (Return / Max Drawdown).

        Args:
            returns: Array of returns
            periods_per_year: Trading periods per year

        Returns:
            Calmar ratio
        """
        returns_array = np.array(returns)
        annual_return = np.mean(returns_array) * periods_per_year
        max_drawdown = RiskAnalyzer.calculate_max_drawdown(returns_array)

        if max_drawdown == 0:
            return 0.0

        return float(annual_return / abs(max_drawdown))

    @staticmethod
    def calculate_portfolio_metrics(
        returns: np.ndarray | list[float],
        risk_free_rate: float = 0.02,
    ) -> RiskMetrics:
        """Calculate all risk metrics for a portfolio.

        Args:
            returns: Array of returns
            risk_free_rate: Annual risk-free rate

        Returns:
            RiskMetrics object with all calculations
        """
        returns_array = np.array(returns)

        return RiskMetrics(
            var_95=RiskAnalyzer.calculate_var(returns_array, 0.95),
            var_99=RiskAnalyzer.calculate_var(returns_array, 0.99),
            cvar_95=RiskAnalyzer.calculate_cvar(returns_array, 0.95),
            cvar_99=RiskAnalyzer.calculate_cvar(returns_array, 0.99),
            sharpe_ratio=RiskAnalyzer.calculate_sharpe_ratio(returns_array, risk_free_rate),
            sortino_ratio=RiskAnalyzer.calculate_sortino_ratio(
                returns_array, risk_free_rate
            ),
            max_drawdown=RiskAnalyzer.calculate_max_drawdown(returns_array),
            calmar_ratio=RiskAnalyzer.calculate_calmar_ratio(returns_array),
            volatility=float(np.std(returns_array) * np.sqrt(252)),
            skewness=float(stats.skew(returns_array)) if len(returns_array) > 2 else 0.0,
            kurtosis=float(stats.kurtosis(returns_array))
            if len(returns_array) > 3
            else 0.0,
            beta=0.0,  # Set to market comparison
            alpha=0.0,  # Set to market comparison
        )

    @staticmethod
    def calculate_ticker_metrics(
        ticker: str,
        returns: np.ndarray | list[float],
    ) -> TickerRiskMetrics:
        """Calculate risk metrics for individual ticker.

        Args:
            ticker: Ticker symbol
            returns: Array of returns

        Returns:
            TickerRiskMetrics object
        """
        returns_array = np.array(returns)

        return TickerRiskMetrics(
            ticker=ticker,
            var_95=RiskAnalyzer.calculate_var(returns_array, 0.95),
            var_99=RiskAnalyzer.calculate_var(returns_array, 0.99),
            cvar_95=RiskAnalyzer.calculate_cvar(returns_array, 0.95),
            cvar_99=RiskAnalyzer.calculate_cvar(returns_array, 0.99),
            volatility=float(np.std(returns_array) * np.sqrt(252)),
            skewness=float(stats.skew(returns_array)) if len(returns_array) > 2 else 0.0,
            kurtosis=float(stats.kurtosis(returns_array))
            if len(returns_array) > 3
            else 0.0,
            return_mean=float(np.mean(returns_array) * 252),
            return_std=float(np.std(returns_array) * np.sqrt(252)),
        )

    @staticmethod
    def calculate_portfolio_concentration(weights: dict[str, float]) -> dict[str, float]:
        """Calculate portfolio concentration metrics.

        Args:
            weights: Portfolio weights by ticker

        Returns:
            Concentration metrics
        """
        weights_array = np.array(list(weights.values()))

        return {
            "herfindahl_index": float(np.sum(weights_array**2)),
            "max_weight": float(np.max(weights_array)),
            "min_weight": float(np.min(weights_array)),
            "effective_assets": float(1 / np.sum(weights_array**2)),
        }

    @staticmethod
    def calculate_correlation_matrix(
        returns_dict: dict[str, np.ndarray | list[float]]
    ) -> dict[str, Any]:
        """Calculate correlation matrix for assets.

        Args:
            returns_dict: Dictionary of returns by ticker

        Returns:
            Correlation matrix and summary statistics
        """
        # Create DataFrame from returns
        df = pd.DataFrame(returns_dict)

        correlation_matrix = df.corr()

        return {
            "correlation_matrix": correlation_matrix.to_dict(),
            "avg_correlation": float(
                correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, k=1)].mean()
            ),
            "min_correlation": float(
                correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, k=1)].min()
            ),
            "max_correlation": float(
                correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, k=1)].max()
            ),
        }

    @staticmethod
    def calculate_diversification_ratio(
        weights: dict[str, float],
        volatilities: dict[str, float],
        portfolio_volatility: float,
    ) -> float:
        """Calculate diversification ratio.

        Higher ratio indicates better diversification.

        Args:
            weights: Portfolio weights by ticker
            volatilities: Individual asset volatilities
            portfolio_volatility: Overall portfolio volatility

        Returns:
            Diversification ratio
        """
        weighted_vol = sum(
            weights.get(ticker, 0) * volatilities.get(ticker, 0)
            for ticker in weights
        )

        if portfolio_volatility == 0:
            return 0.0

        return float(weighted_vol / portfolio_volatility)
