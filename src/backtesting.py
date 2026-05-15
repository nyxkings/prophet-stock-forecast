"""Backtesting framework for portfolio optimization strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from src.main import run_optimisation
from src.settings import PORTFOLIO_TICKERS


@dataclass
class BacktestResult:
    """Result of a single backtest date."""

    date: str
    predicted_prices: dict[str, float]
    predicted_returns: dict[str, float]
    predicted_weights: dict[str, float]
    actual_prices: dict[str, float]
    actual_returns: dict[str, float]
    prediction_errors: dict[str, float]
    price_mape: float
    return_mape: float
    portfolio_predicted_return: float
    portfolio_actual_return: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "date": self.date,
            "predicted_prices": self.predicted_prices,
            "predicted_returns": self.predicted_returns,
            "predicted_weights": self.predicted_weights,
            "actual_prices": self.actual_prices,
            "actual_returns": self.actual_returns,
            "prediction_errors": self.prediction_errors,
            "price_mape": self.price_mape,
            "return_mape": self.return_mape,
            "portfolio_predicted_return": self.portfolio_predicted_return,
            "portfolio_actual_return": self.portfolio_actual_return,
        }


@dataclass
class BacktestSummary:
    """Summary of backtest results."""

    start_date: str
    end_date: str
    num_days: int
    num_trades: int
    total_days_tested: int

    # Price prediction metrics
    avg_price_mape: float
    std_price_mape: float
    min_price_mape: float
    max_price_mape: float

    # Return prediction metrics
    avg_return_mape: float
    std_return_mape: float
    min_return_mape: float
    max_return_mape: float

    # Portfolio performance
    cumulative_predicted_return: float
    cumulative_actual_return: float
    strategy_outperformance: float
    avg_portfolio_predicted_return: float
    avg_portfolio_actual_return: float

    # Risk metrics
    portfolio_sharpe_ratio: float
    portfolio_volatility: float
    portfolio_max_drawdown: float

    # Per-ticker metrics
    ticker_mape: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "num_days": self.num_days,
            "num_trades": self.num_trades,
            "total_days_tested": self.total_days_tested,
            "avg_price_mape": self.avg_price_mape,
            "std_price_mape": self.std_price_mape,
            "min_price_mape": self.min_price_mape,
            "max_price_mape": self.max_price_mape,
            "avg_return_mape": self.avg_return_mape,
            "std_return_mape": self.std_return_mape,
            "min_return_mape": self.min_return_mape,
            "max_return_mape": self.max_return_mape,
            "cumulative_predicted_return": self.cumulative_predicted_return,
            "cumulative_actual_return": self.cumulative_actual_return,
            "strategy_outperformance": self.strategy_outperformance,
            "avg_portfolio_predicted_return": self.avg_portfolio_predicted_return,
            "avg_portfolio_actual_return": self.avg_portfolio_actual_return,
            "portfolio_sharpe_ratio": self.portfolio_sharpe_ratio,
            "portfolio_volatility": self.portfolio_volatility,
            "portfolio_max_drawdown": self.portfolio_max_drawdown,
            "ticker_mape": self.ticker_mape,
        }


class Backtester:
    """Backtest portfolio optimization strategy over historical data."""

    def __init__(self, tickers: list[str] | None = None):
        """Initialize backtester.

        Args:
            tickers: List of tickers to backtest (defaults to PORTFOLIO_TICKERS)
        """
        self.tickers = tickers or PORTFOLIO_TICKERS
        self.results: list[BacktestResult] = []

    def run(
        self,
        start_date: str,
        end_date: str,
        training_days: int = 252,
    ) -> BacktestSummary:
        """Run backtest over date range.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            training_days: Days of history to use for training (default: 252 = 1 year)

        Returns:
            BacktestSummary with performance metrics
        """
        self.results = []

        # Parse dates
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        # Get all dates
        all_dates = pd.bdate_range(start=start, end=end)

        # Extract actual data for entire period
        try:
            import yfinance as yf

            actual_data = yf.download(
                " ".join(self.tickers),
                start=start,
                end=end,
                progress=False,
            )
        except Exception:
            # Fallback for single ticker or if download fails
            actual_data = None

        # Test each date
        test_dates = all_dates[::5]  # Test every 5 business days to speed up
        num_trades = 0

        for test_date in test_dates:
            try:
                # Run optimization with history up to this date
                training_start = test_date - timedelta(days=training_days)

                result = run_optimisation(
                    tickers=self.tickers,
                    start_date=training_start.strftime("%Y-%m-%d"),
                    end_date=test_date.strftime("%Y-%m-%d"),
                )

                if not result:
                    continue

                # Get actual next day price (if available)
                next_date = test_date + timedelta(days=1)
                try:
                    next_actual = yf.download(
                        " ".join(self.tickers),
                        start=test_date,
                        end=next_date,
                        progress=False,
                    )

                    if next_actual is not None and len(next_actual) >= 2:
                        actual_prices = {}
                        actual_returns = {}

                        for ticker in self.tickers:
                            if ticker in next_actual.columns:
                                close_prices = next_actual[("Close", ticker)] if isinstance(
                                    next_actual.columns, pd.MultiIndex
                                ) else next_actual[ticker] if ticker in next_actual.columns else None

                                if close_prices is not None and len(close_prices) >= 2:
                                    today_price = close_prices.iloc[0]
                                    tomorrow_price = close_prices.iloc[1]
                                    actual_prices[ticker] = tomorrow_price
                                    actual_returns[ticker] = (
                                        tomorrow_price - today_price
                                    ) / today_price
                            else:
                                actual_prices[ticker] = result["predicted_prices"].get(
                                    ticker, 0
                                )
                                actual_returns[ticker] = result[
                                    "predicted_returns"
                                ].get(ticker, 0)

                        # Calculate metrics
                        backtest_result = self._calculate_result(
                            test_date.strftime("%Y-%m-%d"),
                            result,
                            actual_prices,
                            actual_returns,
                        )

                        self.results.append(backtest_result)
                        num_trades += 1
                except Exception:
                    continue

            except Exception:
                continue

        # Generate summary
        return self._generate_summary(start_date, end_date, num_trades)

    def _calculate_result(
        self,
        date: str,
        prediction: dict[str, Any],
        actual_prices: dict[str, float],
        actual_returns: dict[str, float],
    ) -> BacktestResult:
        """Calculate result for a single backtest date."""
        predicted_prices = prediction.get("predicted_prices", {})
        predicted_returns = prediction.get("predicted_returns", {})
        predicted_weights = prediction.get("weights", {})

        # Calculate prediction errors
        prediction_errors = {}
        price_errors = []
        return_errors = []

        for ticker in self.tickers:
            if ticker in predicted_prices and ticker in actual_prices:
                pred_price = predicted_prices[ticker]
                actual_price = actual_prices[ticker]

                if actual_price != 0:
                    error = abs(pred_price - actual_price) / actual_price * 100
                    prediction_errors[ticker] = error
                    price_errors.append(error)

                if ticker in predicted_returns and ticker in actual_returns:
                    pred_return = predicted_returns[ticker]
                    actual_return = actual_returns[ticker]
                    return_error = abs(pred_return - actual_return)
                    return_errors.append(return_error)

        price_mape = float(np.mean(price_errors)) if price_errors else 0.0
        return_mape = float(np.mean(return_errors)) if return_errors else 0.0

        # Calculate portfolio returns
        portfolio_predicted_return = sum(
            predicted_weights.get(ticker, 0) * predicted_returns.get(ticker, 0)
            for ticker in self.tickers
        )
        portfolio_actual_return = sum(
            predicted_weights.get(ticker, 0) * actual_returns.get(ticker, 0)
            for ticker in self.tickers
        )

        return BacktestResult(
            date=date,
            predicted_prices=predicted_prices,
            predicted_returns=predicted_returns,
            predicted_weights=predicted_weights,
            actual_prices=actual_prices,
            actual_returns=actual_returns,
            prediction_errors=prediction_errors,
            price_mape=price_mape,
            return_mape=return_mape,
            portfolio_predicted_return=portfolio_predicted_return,
            portfolio_actual_return=portfolio_actual_return,
        )

    def _generate_summary(
        self,
        start_date: str,
        end_date: str,
        num_trades: int,
    ) -> BacktestSummary:
        """Generate backtest summary from results."""
        if not self.results:
            return BacktestSummary(
                start_date=start_date,
                end_date=end_date,
                num_days=0,
                num_trades=num_trades,
                total_days_tested=0,
                avg_price_mape=0.0,
                std_price_mape=0.0,
                min_price_mape=0.0,
                max_price_mape=0.0,
                avg_return_mape=0.0,
                std_return_mape=0.0,
                min_return_mape=0.0,
                max_return_mape=0.0,
                cumulative_predicted_return=0.0,
                cumulative_actual_return=0.0,
                strategy_outperformance=0.0,
                avg_portfolio_predicted_return=0.0,
                avg_portfolio_actual_return=0.0,
                portfolio_sharpe_ratio=0.0,
                portfolio_volatility=0.0,
                portfolio_max_drawdown=0.0,
            )

        # Aggregate metrics
        price_mapes = [r.price_mape for r in self.results]
        return_mapes = [r.return_mape for r in self.results]
        predicted_returns = [r.portfolio_predicted_return for r in self.results]
        actual_returns = [r.portfolio_actual_return for r in self.results]

        # Calculate Sharpe ratio (annualized)
        mean_return = float(np.mean(actual_returns)) if actual_returns else 0.0
        std_return = float(np.std(actual_returns)) if actual_returns else 1.0
        sharpe_ratio = (mean_return * 252 / (std_return * np.sqrt(252))) if std_return > 0 else 0.0

        # Calculate max drawdown
        cumulative_returns = np.cumprod([1 + r for r in actual_returns])
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = float(np.min(drawdown)) if len(drawdown) > 0 else 0.0

        # Per-ticker MAPE
        ticker_mape = {}
        for ticker in self.tickers:
            ticker_errors = [
                r.prediction_errors.get(ticker, 0) for r in self.results
                if ticker in r.prediction_errors
            ]
            if ticker_errors:
                ticker_mape[ticker] = float(np.mean(ticker_errors))

        return BacktestSummary(
            start_date=start_date,
            end_date=end_date,
            num_days=(pd.to_datetime(end_date) - pd.to_datetime(start_date)).days,
            num_trades=num_trades,
            total_days_tested=len(self.results),
            avg_price_mape=float(np.mean(price_mapes)) if price_mapes else 0.0,
            std_price_mape=float(np.std(price_mapes)) if price_mapes else 0.0,
            min_price_mape=float(np.min(price_mapes)) if price_mapes else 0.0,
            max_price_mape=float(np.max(price_mapes)) if price_mapes else 0.0,
            avg_return_mape=float(np.mean(return_mapes)) if return_mapes else 0.0,
            std_return_mape=float(np.std(return_mapes)) if return_mapes else 0.0,
            min_return_mape=float(np.min(return_mapes)) if return_mapes else 0.0,
            max_return_mape=float(np.max(return_mapes)) if return_mapes else 0.0,
            cumulative_predicted_return=float(np.prod([1 + r for r in predicted_returns]) - 1)
            if predicted_returns
            else 0.0,
            cumulative_actual_return=float(np.prod([1 + r for r in actual_returns]) - 1)
            if actual_returns
            else 0.0,
            strategy_outperformance=float(
                np.prod([1 + r for r in actual_returns]) / np.prod([1 + r for r in predicted_returns])
                - 1
            )
            if (predicted_returns and actual_returns)
            else 0.0,
            avg_portfolio_predicted_return=float(np.mean(predicted_returns))
            if predicted_returns
            else 0.0,
            avg_portfolio_actual_return=float(np.mean(actual_returns)) if actual_returns else 0.0,
            portfolio_sharpe_ratio=sharpe_ratio,
            portfolio_volatility=float(np.std(actual_returns) * np.sqrt(252)) if actual_returns else 0.0,
            portfolio_max_drawdown=max_drawdown,
            ticker_mape=ticker_mape,
        )

    def results_to_dataframe(self) -> pd.DataFrame:
        """Convert results to DataFrame."""
        if not self.results:
            return pd.DataFrame()

        data = []
        for result in self.results:
            data.append({
                "date": result.date,
                "price_mape": result.price_mape,
                "return_mape": result.return_mape,
                "predicted_return": result.portfolio_predicted_return,
                "actual_return": result.portfolio_actual_return,
            })

        return pd.DataFrame(data)
