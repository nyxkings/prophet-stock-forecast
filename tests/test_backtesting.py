"""Tests for backtesting framework."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.backtesting import BacktestResult, BacktestSummary, Backtester


class TestBacktestResult:
    """Test BacktestResult dataclass."""

    def test_result_creation(self):
        """Test creating a backtest result."""
        result = BacktestResult(
            date="2026-05-14",
            predicted_prices={"AAPL": 150.0, "MSFT": 300.0},
            predicted_returns={"AAPL": 0.02, "MSFT": 0.03},
            predicted_weights={"AAPL": 0.5, "MSFT": 0.5},
            actual_prices={"AAPL": 151.0, "MSFT": 298.0},
            actual_returns={"AAPL": 0.0067, "MSFT": -0.0067},
            prediction_errors={"AAPL": 0.67, "MSFT": 0.67},
            price_mape=0.67,
            return_mape=0.01267,
            portfolio_predicted_return=0.025,
            portfolio_actual_return=0.0,
        )

        assert result.date == "2026-05-14"
        assert result.price_mape == 0.67
        assert result.portfolio_predicted_return == 0.025

    def test_result_to_dict(self):
        """Test converting result to dictionary."""
        result = BacktestResult(
            date="2026-05-14",
            predicted_prices={"AAPL": 150.0},
            predicted_returns={"AAPL": 0.02},
            predicted_weights={"AAPL": 1.0},
            actual_prices={"AAPL": 151.0},
            actual_returns={"AAPL": 0.0067},
            prediction_errors={"AAPL": 0.67},
            price_mape=0.67,
            return_mape=0.01267,
            portfolio_predicted_return=0.02,
            portfolio_actual_return=0.0067,
        )

        result_dict = result.to_dict()

        assert result_dict["date"] == "2026-05-14"
        assert "price_mape" in result_dict
        assert isinstance(result_dict["predicted_prices"], dict)


class TestBacktestSummary:
    """Test BacktestSummary dataclass."""

    def test_summary_creation(self):
        """Test creating a backtest summary."""
        summary = BacktestSummary(
            start_date="2026-01-01",
            end_date="2026-05-14",
            num_days=134,
            num_trades=20,
            total_days_tested=20,
            avg_price_mape=2.5,
            std_price_mape=1.2,
            min_price_mape=0.5,
            max_price_mape=5.0,
            avg_return_mape=0.015,
            std_return_mape=0.008,
            min_return_mape=0.001,
            max_return_mape=0.03,
            cumulative_predicted_return=0.05,
            cumulative_actual_return=0.04,
            strategy_outperformance=-0.01,
            avg_portfolio_predicted_return=0.002,
            avg_portfolio_actual_return=0.001,
            portfolio_sharpe_ratio=1.5,
            portfolio_volatility=0.12,
            portfolio_max_drawdown=-0.05,
            ticker_mape={"AAPL": 2.0, "MSFT": 3.0},
        )

        assert summary.num_days == 134
        assert summary.avg_price_mape == 2.5
        assert summary.portfolio_sharpe_ratio == 1.5

    def test_summary_to_dict(self):
        """Test converting summary to dictionary."""
        summary = BacktestSummary(
            start_date="2026-01-01",
            end_date="2026-05-14",
            num_days=134,
            num_trades=20,
            total_days_tested=20,
            avg_price_mape=2.5,
            std_price_mape=1.2,
            min_price_mape=0.5,
            max_price_mape=5.0,
            avg_return_mape=0.015,
            std_return_mape=0.008,
            min_return_mape=0.001,
            max_return_mape=0.03,
            cumulative_predicted_return=0.05,
            cumulative_actual_return=0.04,
            strategy_outperformance=-0.01,
            avg_portfolio_predicted_return=0.002,
            avg_portfolio_actual_return=0.001,
            portfolio_sharpe_ratio=1.5,
            portfolio_volatility=0.12,
            portfolio_max_drawdown=-0.05,
        )

        summary_dict = summary.to_dict()

        assert summary_dict["num_days"] == 134
        assert "portfolio_sharpe_ratio" in summary_dict
        assert "ticker_mape" in summary_dict


class TestBacktester:
    """Test Backtester class."""

    def test_backtester_initialization(self):
        """Test backtester creation."""
        bt = Backtester()

        assert bt.tickers is not None
        assert len(bt.tickers) > 0
        assert bt.results == []

    def test_backtester_custom_tickers(self):
        """Test backtester with custom tickers."""
        custom_tickers = ["AAPL", "MSFT", "GOOGL"]
        bt = Backtester(tickers=custom_tickers)

        assert bt.tickers == custom_tickers

    def test_calculate_result(self):
        """Test calculating a backtest result."""
        bt = Backtester()

        prediction = {
            "predicted_prices": {"AAPL": 150.0, "MSFT": 300.0},
            "predicted_returns": {"AAPL": 0.02, "MSFT": 0.03},
            "weights": {"AAPL": 0.5, "MSFT": 0.5, "GOOGL": 0.0},
        }

        actual_prices = {"AAPL": 151.0, "MSFT": 298.0}
        actual_returns = {"AAPL": 0.0067, "MSFT": -0.0067}

        result = bt._calculate_result(
            "2026-05-14",
            prediction,
            actual_prices,
            actual_returns,
        )

        assert result.date == "2026-05-14"
        assert result.price_mape >= 0
        assert result.portfolio_predicted_return == 0.025

    def test_calculate_result_with_errors(self):
        """Test result calculation with prediction errors."""
        bt = Backtester()

        prediction = {
            "predicted_prices": {"AAPL": 150.0},
            "predicted_returns": {"AAPL": 0.05},
            "weights": {"AAPL": 1.0},
        }

        actual_prices = {"AAPL": 140.0}  # 6.67% error
        actual_returns = {"AAPL": -0.067}

        result = bt._calculate_result(
            "2026-05-14",
            prediction,
            actual_prices,
            actual_returns,
        )

        assert result.price_mape > 0
        assert "AAPL" in result.prediction_errors

    def test_generate_empty_summary(self):
        """Test generating summary with no results."""
        bt = Backtester()

        summary = bt._generate_summary("2026-01-01", "2026-05-14", 0)

        # num_days calculation: days between start and end
        assert summary.num_days >= 0
        assert summary.num_trades == 0
        assert summary.avg_price_mape == 0.0

    def test_results_to_dataframe(self):
        """Test converting results to DataFrame."""
        bt = Backtester()

        # Add some mock results
        result = BacktestResult(
            date="2026-05-14",
            predicted_prices={"AAPL": 150.0},
            predicted_returns={"AAPL": 0.02},
            predicted_weights={"AAPL": 1.0},
            actual_prices={"AAPL": 151.0},
            actual_returns={"AAPL": 0.0067},
            prediction_errors={"AAPL": 0.67},
            price_mape=0.67,
            return_mape=0.01267,
            portfolio_predicted_return=0.02,
            portfolio_actual_return=0.0067,
        )

        bt.results.append(result)

        df = bt.results_to_dataframe()

        assert len(df) == 1
        assert "date" in df.columns
        assert "price_mape" in df.columns

    def test_results_to_dataframe_empty(self):
        """Test converting empty results to DataFrame."""
        bt = Backtester()

        df = bt.results_to_dataframe()

        assert df.empty


class TestBacktestingMetrics:
    """Test backtest metric calculations."""

    def test_price_mape_calculation(self):
        """Test MAPE calculation for prices."""
        bt = Backtester()

        prediction = {
            "predicted_prices": {"AAPL": 100.0},
            "predicted_returns": {"AAPL": 0.0},
            "weights": {"AAPL": 1.0},
        }

        actual_prices = {"AAPL": 110.0}  # (100-110)/110 * 100 = 9.09% error
        actual_returns = {"AAPL": 0.1}

        result = bt._calculate_result(
            "2026-05-14",
            prediction,
            actual_prices,
            actual_returns,
        )

        assert pytest.approx(result.price_mape, rel=0.02) == 9.09

    def test_portfolio_return_calculation(self):
        """Test portfolio return calculation."""
        bt = Backtester()

        prediction = {
            "predicted_prices": {"AAPL": 150.0, "MSFT": 300.0},
            "predicted_returns": {"AAPL": 0.02, "MSFT": 0.04},
            "weights": {"AAPL": 0.6, "MSFT": 0.4},
        }

        actual_prices = {"AAPL": 151.0, "MSFT": 298.0}
        actual_returns = {"AAPL": 0.0067, "MSFT": -0.0067}

        result = bt._calculate_result(
            "2026-05-14",
            prediction,
            actual_prices,
            actual_returns,
        )

        # Portfolio predicted return: 0.6 * 0.02 + 0.4 * 0.04 = 0.028
        assert pytest.approx(result.portfolio_predicted_return, rel=0.01) == 0.028

        # Portfolio actual return: 0.6 * 0.0067 + 0.4 * -0.0067 = 0.00134
        assert pytest.approx(result.portfolio_actual_return, rel=0.01) == 0.00134

    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation in summary."""
        bt = Backtester()

        # Add consistent positive returns
        for i in range(10):
            result = BacktestResult(
                date=f"2026-05-{14-i:02d}",
                predicted_prices={"AAPL": 150.0},
                predicted_returns={"AAPL": 0.02},
                predicted_weights={"AAPL": 1.0},
                actual_prices={"AAPL": 151.0},
                actual_returns={"AAPL": 0.01},
                prediction_errors={"AAPL": 0.67},
                price_mape=0.67,
                return_mape=0.01,
                portfolio_predicted_return=0.02,
                portfolio_actual_return=0.01,
            )
            bt.results.append(result)

        summary = bt._generate_summary("2026-05-04", "2026-05-14", 10)

        # With positive consistent returns, Sharpe ratio should be positive
        assert summary.portfolio_sharpe_ratio > 0

    def test_max_drawdown_calculation(self):
        """Test max drawdown calculation."""
        bt = Backtester()

        # Mix of positive and negative returns to create drawdown
        returns_sequence = [0.02, 0.01, -0.03, -0.02, 0.01, 0.01]

        for i, ret in enumerate(returns_sequence):
            result = BacktestResult(
                date=f"2026-05-{14-i:02d}",
                predicted_prices={"AAPL": 150.0},
                predicted_returns={"AAPL": ret},
                predicted_weights={"AAPL": 1.0},
                actual_prices={"AAPL": 151.0},
                actual_returns={"AAPL": ret},
                prediction_errors={"AAPL": 0.0},
                price_mape=0.0,
                return_mape=0.0,
                portfolio_predicted_return=ret,
                portfolio_actual_return=ret,
            )
            bt.results.append(result)

        summary = bt._generate_summary("2026-05-08", "2026-05-14", len(returns_sequence))

        # Max drawdown should be negative (at least some decline)
        assert summary.portfolio_max_drawdown <= 0

    def test_ticker_mape_aggregation(self):
        """Test per-ticker MAPE aggregation."""
        bt = Backtester(tickers=["AAPL", "MSFT"])

        # Add results with known errors
        result1 = BacktestResult(
            date="2026-05-14",
            predicted_prices={"AAPL": 100.0, "MSFT": 200.0},
            predicted_returns={"AAPL": 0.0, "MSFT": 0.0},
            predicted_weights={"AAPL": 0.5, "MSFT": 0.5},
            actual_prices={"AAPL": 110.0, "MSFT": 220.0},
            actual_returns={"AAPL": 0.1, "MSFT": 0.1},
            prediction_errors={"AAPL": 10.0, "MSFT": 10.0},
            price_mape=10.0,
            return_mape=0.1,
            portfolio_predicted_return=0.0,
            portfolio_actual_return=0.1,
        )

        result2 = BacktestResult(
            date="2026-05-13",
            predicted_prices={"AAPL": 100.0, "MSFT": 200.0},
            predicted_returns={"AAPL": 0.0, "MSFT": 0.0},
            predicted_weights={"AAPL": 0.5, "MSFT": 0.5},
            actual_prices={"AAPL": 105.0, "MSFT": 235.0},
            actual_returns={"AAPL": 0.05, "MSFT": 0.175},
            prediction_errors={"AAPL": 5.0, "MSFT": 17.5},
            price_mape=11.25,
            return_mape=0.113,
            portfolio_predicted_return=0.0,
            portfolio_actual_return=0.1125,
        )

        bt.results = [result1, result2]

        summary = bt._generate_summary("2026-05-13", "2026-05-14", 2)

        # AAPL average error: (10 + 5) / 2 = 7.5
        assert pytest.approx(summary.ticker_mape.get("AAPL", 0), rel=0.01) == 7.5

        # MSFT average error: (10 + 17.5) / 2 = 13.75
        assert pytest.approx(summary.ticker_mape.get("MSFT", 0), rel=0.01) == 13.75


class TestBacktestingEdgeCases:
    """Test edge cases in backtesting."""

    def test_empty_results(self):
        """Test with no results."""
        bt = Backtester()

        summary = bt._generate_summary("2026-01-01", "2026-05-14", 0)

        assert summary.avg_price_mape == 0.0
        assert summary.portfolio_sharpe_ratio == 0.0

    def test_zero_volatility(self):
        """Test with zero volatility (constant returns)."""
        bt = Backtester()

        # All returns are the same
        for i in range(5):
            result = BacktestResult(
                date=f"2026-05-{14-i:02d}",
                predicted_prices={"AAPL": 150.0},
                predicted_returns={"AAPL": 0.01},
                predicted_weights={"AAPL": 1.0},
                actual_prices={"AAPL": 151.5},
                actual_returns={"AAPL": 0.01},
                prediction_errors={"AAPL": 0.0},
                price_mape=0.0,
                return_mape=0.0,
                portfolio_predicted_return=0.01,
                portfolio_actual_return=0.01,
            )
            bt.results.append(result)

        summary = bt._generate_summary("2026-05-10", "2026-05-14", 5)

        # With zero volatility, Sharpe ratio should be high (or handle gracefully)
        assert summary.portfolio_sharpe_ratio >= 0

    def test_missing_ticker_data(self):
        """Test handling of missing ticker data."""
        bt = Backtester()

        prediction = {
            "predicted_prices": {"AAPL": 150.0, "MSFT": 300.0},
            "predicted_returns": {"AAPL": 0.02, "MSFT": 0.03},
            "weights": {"AAPL": 0.5, "MSFT": 0.5},
        }

        # Only AAPL actual data available
        actual_prices = {"AAPL": 151.0}
        actual_returns = {"AAPL": 0.0067}

        result = bt._calculate_result(
            "2026-05-14",
            prediction,
            actual_prices,
            actual_returns,
        )

        # Should handle missing MSFT gracefully
        assert result.price_mape >= 0
