"""Tests for portfolio analysis workflow helpers."""

import numpy as np
import pandas as pd
import pytest

from src.portfolio_analysis import (
    analyze_portfolio_risk,
    compute_weighted_portfolio_returns,
    expected_returns_from_date_df,
    format_backtest_summary,
    weights_from_date_df,
)
from src.backtesting import BacktestSummary


class TestPortfolioAnalysisHelpers:
    def test_weights_from_date_df(self) -> None:
        df = pd.DataFrame(
            {
                "ticker": ["AAPL", "MSFT"],
                "portfolio_weight": [0.6, 0.4],
            }
        )
        assert weights_from_date_df(df) == {"AAPL": 0.6, "MSFT": 0.4}

    def test_expected_returns_from_date_df(self) -> None:
        df = pd.DataFrame(
            {
                "ticker": ["AAPL", "MSFT"],
                "predicted_return": [0.01, -0.02],
            }
        )
        assert expected_returns_from_date_df(df) == {"AAPL": 0.01, "MSFT": -0.02}

    def test_compute_weighted_portfolio_returns(self) -> None:
        dates = pd.date_range("2024-01-01", periods=3, freq="D")
        returns_data = {
            "AAPL": pd.DataFrame(
                {"Returns": [0.01, 0.02, -0.01]},
                index=[d.date() for d in dates],
            ),
            "MSFT": pd.DataFrame(
                {"Returns": [0.005, -0.01, 0.02]},
                index=[d.date() for d in dates],
            ),
        }
        weights = {"AAPL": 0.5, "MSFT": 0.5}
        portfolio_returns = compute_weighted_portfolio_returns(weights, returns_data)
        assert len(portfolio_returns) == 3
        assert np.isclose(portfolio_returns[0], 0.0075)

    def test_analyze_portfolio_risk(self) -> None:
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        rng = np.random.default_rng(0)
        returns_data = {
            "AAPL": pd.DataFrame(
                {"Returns": rng.normal(0.001, 0.01, 30)},
                index=[d.date() for d in dates],
            ),
            "MSFT": pd.DataFrame(
                {"Returns": rng.normal(0.0005, 0.012, 30)},
                index=[d.date() for d in dates],
            ),
        }
        weights = {"AAPL": 0.7, "MSFT": 0.3}
        metrics, concentration = analyze_portfolio_risk(weights, returns_data)
        assert metrics.sharpe_ratio != 0.0
        assert concentration["herfindahl_index"] > 0

    def test_format_backtest_summary(self) -> None:
        summary = BacktestSummary(
            start_date="2024-01-01",
            end_date="2024-03-01",
            num_days=10,
            num_trades=5,
            total_days_tested=10,
            avg_price_mape=1.5,
            std_price_mape=0.2,
            min_price_mape=1.0,
            max_price_mape=2.0,
            avg_return_mape=2.0,
            std_return_mape=0.3,
            min_return_mape=1.5,
            max_return_mape=2.5,
            cumulative_predicted_return=0.05,
            cumulative_actual_return=0.04,
            strategy_outperformance=0.01,
            avg_portfolio_predicted_return=0.001,
            avg_portfolio_actual_return=0.0008,
            portfolio_sharpe_ratio=1.2,
            portfolio_volatility=0.15,
            portfolio_max_drawdown=-0.05,
        )
        text = format_backtest_summary(summary)
        assert "Backtest summary" in text
        assert "Portfolio Sharpe: 1.20" in text

    def test_analyze_portfolio_risk_raises_without_data(self) -> None:
        with pytest.raises(ValueError, match="No overlapping historical returns"):
            analyze_portfolio_risk({"AAPL": 1.0}, {})
