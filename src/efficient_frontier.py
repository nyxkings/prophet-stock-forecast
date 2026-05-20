"""Efficient frontier visualization for portfolio optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.risk_analytics import RiskAnalyzer


@dataclass
class PortfolioPoint:
    """Single point on efficient frontier."""

    risk_aversion: float  # Lambda parameter
    volatility: float  # Portfolio standard deviation
    expected_return: float  # Portfolio expected return
    sharpe_ratio: float  # Sharpe ratio
    weights: dict[str, float]  # Portfolio weights

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "risk_aversion": self.risk_aversion,
            "volatility": self.volatility,
            "expected_return": self.expected_return,
            "sharpe_ratio": self.sharpe_ratio,
            "weights": self.weights,
        }


@dataclass
class EfficientFrontierResult:
    """Complete efficient frontier analysis."""

    frontier_points: list[PortfolioPoint]
    min_variance_portfolio: PortfolioPoint
    max_sharpe_portfolio: PortfolioPoint
    mean_returns: pd.Series
    cov_matrix: pd.DataFrame

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "frontier_points": [p.to_dict() for p in self.frontier_points],
            "min_variance_portfolio": self.min_variance_portfolio.to_dict(),
            "max_sharpe_portfolio": self.max_sharpe_portfolio.to_dict(),
        }


class EfficientFrontier:
    """Generate and analyze efficient frontier."""

    @staticmethod
    def optimize_portfolio(
        mean_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        risk_aversion: float,
        minimum_allocation: float = 0.05,
        maximum_allocation: float = 1.0,
    ) -> dict[str, float]:
        """Optimize portfolio for given risk aversion parameter.

        Args:
            mean_returns: Expected returns for each asset
            cov_matrix: Covariance matrix of returns
            risk_aversion: Risk aversion coefficient (lambda)
            minimum_allocation: Minimum allocation for each asset
            maximum_allocation: Maximum allocation for each asset

        Returns:
            Dictionary mapping ticker to optimal weight

        Raises:
            ValueError: If portfolio is empty or invalid
        """
        tickers = list(mean_returns.index)
        num_assets = len(tickers)

        if num_assets == 0:
            raise ValueError("Cannot optimize empty portfolio")

        # Objective: minimise -(return - (lambda/2) * variance)
        def objective(weights: np.ndarray) -> float:
            port_return = float(np.dot(weights, mean_returns))
            port_var = float(np.dot(weights.T, np.dot(cov_matrix, weights)))
            return -(port_return - 0.5 * risk_aversion * port_var)

        # Constraint: sum(weights) == 1
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1}]

        # Bounds
        bounds = tuple((minimum_allocation, maximum_allocation) for _ in range(num_assets))

        # Initial guess: equal weights
        initial_weights = np.array([1 / num_assets] * num_assets)

        # Optimize
        result = minimize(
            objective, initial_weights, method="SLSQP", bounds=bounds, constraints=constraints
        )

        if not result.success:
            # Return equal-weight fallback
            return {ticker: 1 / num_assets for ticker in tickers}

        return {ticker: float(w) for ticker, w in zip(tickers, result.x, strict=True)}

    @staticmethod
    def calculate_portfolio_metrics(
        weights: dict[str, float],
        mean_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        risk_free_rate: float = 0.02,
    ) -> tuple[float, float, float]:
        """Calculate portfolio volatility, expected return, and Sharpe ratio.

        Args:
            weights: Portfolio weights
            mean_returns: Expected returns
            cov_matrix: Covariance matrix
            risk_free_rate: Risk-free rate

        Returns:
            Tuple of (volatility, expected_return, sharpe_ratio)
        """
        # Ensure weights are in same order as mean_returns
        w = np.array([weights[ticker] for ticker in mean_returns.index])

        # Expected return
        exp_return = float(np.dot(w, mean_returns))

        # Volatility (annualized)
        variance = float(np.dot(w.T, np.dot(cov_matrix, w)))
        volatility = float(np.sqrt(variance))

        # Sharpe ratio
        excess_return = exp_return - risk_free_rate
        sharpe = excess_return / volatility if volatility > 0 else 0.0

        return volatility, exp_return, sharpe

    @staticmethod
    def generate_frontier(
        mean_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        num_points: int = 50,
        lambda_range: tuple[float, float] = (0.1, 100),
        minimum_allocation: float = 0.05,
        maximum_allocation: float = 1.0,
        risk_free_rate: float = 0.02,
    ) -> EfficientFrontierResult:
        """Generate efficient frontier by varying risk aversion parameter.

        Args:
            mean_returns: Expected returns for each asset
            cov_matrix: Covariance matrix of returns
            num_points: Number of points to generate
            lambda_range: Tuple of (min_lambda, max_lambda)
            minimum_allocation: Minimum allocation per asset
            maximum_allocation: Maximum allocation per asset
            risk_free_rate: Risk-free rate

        Returns:
            EfficientFrontierResult containing frontier points and key portfolios
        """
        # Generate lambda values on log scale
        lambdas = np.logspace(
            np.log10(lambda_range[0]),
            np.log10(lambda_range[1]),
            num_points,
        )

        frontier_points = []
        sharpe_ratios = []

        for lam in lambdas:
            # Optimize for this lambda
            weights = EfficientFrontier.optimize_portfolio(
                mean_returns,
                cov_matrix,
                lam,
                minimum_allocation,
                maximum_allocation,
            )

            # Calculate metrics
            volatility, exp_return, sharpe = EfficientFrontier.calculate_portfolio_metrics(
                weights, mean_returns, cov_matrix, risk_free_rate
            )

            point = PortfolioPoint(
                risk_aversion=lam,
                volatility=volatility,
                expected_return=exp_return,
                sharpe_ratio=sharpe,
                weights=weights,
            )
            frontier_points.append(point)
            sharpe_ratios.append(sharpe)

        # Find minimum variance portfolio (highest lambda = most conservative)
        min_var = max(frontier_points, key=lambda p: p.risk_aversion)

        # Find maximum Sharpe portfolio
        max_sharpe = max(frontier_points, key=lambda p: p.sharpe_ratio)

        return EfficientFrontierResult(
            frontier_points=frontier_points,
            min_variance_portfolio=min_var,
            max_sharpe_portfolio=max_sharpe,
            mean_returns=mean_returns,
            cov_matrix=cov_matrix,
        )

    @staticmethod
    def plot_frontier(
        frontier_result: EfficientFrontierResult,
        current_weights: dict[str, float] | None = None,
    ) -> Any:
        """Create interactive Plotly visualization of efficient frontier.

        Args:
            frontier_result: EfficientFrontierResult from generate_frontier
            current_weights: Current portfolio weights to highlight

        Returns:
            Plotly Figure object
        """
        try:
            import plotly.graph_objects as go
        except ImportError:
            raise ImportError("plotly is required for frontier visualization")

        # Extract frontier data
        volatilities = [p.volatility for p in frontier_result.frontier_points]
        returns = [p.expected_return for p in frontier_result.frontier_points]
        sharpe_ratios = [p.sharpe_ratio for p in frontier_result.frontier_points]

        # Create figure
        fig = go.Figure()

        # Plot frontier curve
        fig.add_trace(
            go.Scatter(
                x=volatilities,
                y=returns,
                mode="lines",
                name="Efficient Frontier",
                line=dict(color="blue", width=2),
                hovertemplate="<b>Volatility:</b> %{x:.4f}<br>"
                "<b>Expected Return:</b> %{y:.4f}<br>"
                "<extra></extra>",
            )
        )

        # Plot individual points with Sharpe ratio coloring
        fig.add_trace(
            go.Scatter(
                x=volatilities,
                y=returns,
                mode="markers",
                name="Portfolio Points",
                marker=dict(
                    size=6,
                    color=sharpe_ratios,
                    colorscale="Viridis",
                    showscale=True,
                    colorbar=dict(title="Sharpe Ratio"),
                ),
                hovertemplate="<b>Volatility:</b> %{x:.4f}<br>"
                "<b>Expected Return:</b> %{y:.4f}<br>"
                "<b>Sharpe Ratio:</b> %{marker.color:.4f}<br>"
                "<extra></extra>",
            )
        )

        # Highlight minimum variance portfolio
        min_var = frontier_result.min_variance_portfolio
        fig.add_trace(
            go.Scatter(
                x=[min_var.volatility],
                y=[min_var.expected_return],
                mode="markers",
                name="Min Variance Portfolio",
                marker=dict(size=15, color="red", symbol="star"),
                hovertemplate="<b>Min Variance Portfolio</b><br>"
                f"<b>Volatility:</b> {min_var.volatility:.4f}<br>"
                f"<b>Expected Return:</b> {min_var.expected_return:.4f}<br>"
                f"<b>Sharpe Ratio:</b> {min_var.sharpe_ratio:.4f}<br>"
                "<extra></extra>",
            )
        )

        # Highlight maximum Sharpe portfolio
        max_sharpe = frontier_result.max_sharpe_portfolio
        fig.add_trace(
            go.Scatter(
                x=[max_sharpe.volatility],
                y=[max_sharpe.expected_return],
                mode="markers",
                name="Max Sharpe Portfolio",
                marker=dict(size=15, color="gold", symbol="diamond"),
                hovertemplate="<b>Max Sharpe Portfolio</b><br>"
                f"<b>Volatility:</b> {max_sharpe.volatility:.4f}<br>"
                f"<b>Expected Return:</b> {max_sharpe.expected_return:.4f}<br>"
                f"<b>Sharpe Ratio:</b> {max_sharpe.sharpe_ratio:.4f}<br>"
                "<extra></extra>",
            )
        )

        # Plot current portfolio if provided
        if current_weights:
            try:
                volatility, exp_return, sharpe = EfficientFrontier.calculate_portfolio_metrics(
                    current_weights,
                    frontier_result.mean_returns,
                    frontier_result.cov_matrix,
                )
                fig.add_trace(
                    go.Scatter(
                        x=[volatility],
                        y=[exp_return],
                        mode="markers",
                        name="Current Portfolio",
                        marker=dict(size=15, color="green", symbol="circle"),
                        hovertemplate="<b>Current Portfolio</b><br>"
                        f"<b>Volatility:</b> {volatility:.4f}<br>"
                        f"<b>Expected Return:</b> {exp_return:.4f}<br>"
                        f"<b>Sharpe Ratio:</b> {sharpe:.4f}<br>"
                        "<extra></extra>",
                    )
                )
            except KeyError:
                # Skip if weights don't match tickers
                pass

        # Update layout
        fig.update_layout(
            title="Efficient Frontier - Risk vs Return",
            xaxis_title="Portfolio Volatility (Risk)",
            yaxis_title="Expected Return",
            hovermode="closest",
            height=600,
            template="plotly_white",
        )

        return fig

    @staticmethod
    def format_portfolio_weights(weights: dict[str, float], top_n: int = 10) -> str:
        """Format portfolio weights as readable string.

        Args:
            weights: Portfolio weights
            top_n: Number of top holdings to display

        Returns:
            Formatted string
        """
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        top_weights = sorted_weights[:top_n]

        lines = ["Portfolio Weights:"]
        total_shown = 0.0
        for ticker, weight in top_weights:
            lines.append(f"  {ticker}: {weight*100:.2f}%")
            total_shown += weight

        if len(sorted_weights) > top_n:
            remaining = 1.0 - total_shown
            lines.append(f"  Others: {remaining*100:.2f}%")

        return "\n".join(lines)
