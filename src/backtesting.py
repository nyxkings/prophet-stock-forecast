"""Backtesting framework for portfolio optimization strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from src.settings import PORTFOLIO_TICKERS


# run_optimisation is imported lazily inside Backtester.run so the Streamlit
# dashboard (which imports evaluation → backtesting types) does not pull in
# Prophet at import time — required for Streamlit Cloud deploys.


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

    # Comparative evaluation (Prophet vs baselines)
    naive_price_mape: float = 0.0
    drift_price_mape: float = 0.0
    portfolio_historical_mpt_return: float = 0.0
    portfolio_equal_weight_return: float = 0.0

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
            "naive_price_mape": self.naive_price_mape,
            "drift_price_mape": self.drift_price_mape,
            "portfolio_historical_mpt_return": self.portfolio_historical_mpt_return,
            "portfolio_equal_weight_return": self.portfolio_equal_weight_return,
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

    # Optional benchmark comparisons (additive; None if unavailable)
    benchmark_equal_weight_return: float | None = None
    benchmark_buy_hold_equal_weight_return: float | None = None
    benchmark_spy_return: float | None = None
    excess_return_vs_equal_weight: float | None = None
    excess_return_vs_buy_hold_equal_weight: float | None = None
    excess_return_vs_spy: float | None = None

    # Comparative forecast accuracy vs baselines
    avg_naive_price_mape: float = 0.0
    avg_drift_price_mape: float = 0.0
    prophet_mape_improvement_vs_naive: float = 0.0
    prophet_win_rate_vs_naive: float = 0.0
    prophet_win_rate_vs_drift: float = 0.0

    # Comparative strategy performance
    cumulative_historical_mpt_return: float | None = None
    excess_return_vs_historical_mpt: float | None = None
    strategy_win_rate_vs_equal_weight: float | None = None
    strategy_win_rate_vs_historical_mpt: float | None = None
    historical_mpt_sharpe_ratio: float | None = None

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
            "benchmark_equal_weight_return": self.benchmark_equal_weight_return,
            "benchmark_buy_hold_equal_weight_return": self.benchmark_buy_hold_equal_weight_return,
            "benchmark_spy_return": self.benchmark_spy_return,
            "excess_return_vs_equal_weight": self.excess_return_vs_equal_weight,
            "excess_return_vs_buy_hold_equal_weight": self.excess_return_vs_buy_hold_equal_weight,
            "excess_return_vs_spy": self.excess_return_vs_spy,
            "avg_naive_price_mape": self.avg_naive_price_mape,
            "avg_drift_price_mape": self.avg_drift_price_mape,
            "prophet_mape_improvement_vs_naive": self.prophet_mape_improvement_vs_naive,
            "prophet_win_rate_vs_naive": self.prophet_win_rate_vs_naive,
            "prophet_win_rate_vs_drift": self.prophet_win_rate_vs_drift,
            "cumulative_historical_mpt_return": self.cumulative_historical_mpt_return,
            "excess_return_vs_historical_mpt": self.excess_return_vs_historical_mpt,
            "strategy_win_rate_vs_equal_weight": self.strategy_win_rate_vs_equal_weight,
            "strategy_win_rate_vs_historical_mpt": self.strategy_win_rate_vs_historical_mpt,
            "historical_mpt_sharpe_ratio": self.historical_mpt_sharpe_ratio,
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
        from src.main import run_optimisation

        self.results = []

        # Parse dates
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        # Get all dates
        all_dates = pd.bdate_range(start=start, end=end)

        # Extract actual data for entire period
        try:
            import yfinance as yf

            yf.download(
                " ".join(self.tickers),
                start=start,
                end=end,
                progress=False,
            )
        except Exception:
            # Fallback for single ticker or if download fails
            pass

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

                # Get actual next trading day prices (never fall back to predictions)
                from src.market_calendar import next_trading_day

                as_of = test_date.date() if hasattr(test_date, "date") else test_date
                target = next_trading_day(as_of)
                try:
                    actual_prices, actual_returns = self._fetch_actual_outcomes(
                        as_of=as_of,
                        target=target,
                    )
                    if not actual_prices or len(actual_prices) < len(self.tickers):
                        continue

                    comparative = self._comparative_metrics(
                        result,
                        actual_prices,
                        actual_returns,
                        training_start,
                        test_date,
                    )
                    backtest_result = self._calculate_result(
                        test_date.strftime("%Y-%m-%d"),
                        result,
                        actual_prices,
                        actual_returns,
                        comparative=comparative,
                    )

                    self.results.append(backtest_result)
                    num_trades += 1
                except Exception:
                    continue

            except Exception:
                continue

        # Generate summary (includes optional benchmarks)
        return self._generate_summary(
            start_date,
            end_date,
            num_trades,
            include_benchmarks=True,
        )

    def _close_series(self, frame: pd.DataFrame, ticker: str) -> pd.Series | None:
        """Extract a Close price series for one ticker from a yfinance download."""
        if frame is None or frame.empty:
            return None
        if isinstance(frame.columns, pd.MultiIndex):
            if ("Close", ticker) in frame.columns:
                series = frame[("Close", ticker)]
            elif (ticker, "Close") in frame.columns:
                series = frame[(ticker, "Close")]
            else:
                return None
        elif "Close" in frame.columns:
            series = frame["Close"]
        elif ticker in frame.columns:
            series = frame[ticker]
        else:
            return None
        return series.dropna()

    def _fetch_actual_outcomes(
        self,
        as_of: date,
        target: date,
    ) -> tuple[dict[str, float], dict[str, float]]:
        """
        Download realised prices for ``as_of`` and the next trading day ``target``.

        Returns empty dicts when either session is missing — callers must skip the date
        rather than substituting predicted values (which zeroed MAPE previously).
        """
        import yfinance as yf

        fetch_start = as_of - timedelta(days=5)
        fetch_end = target + timedelta(days=3)
        raw = yf.download(
            " ".join(self.tickers),
            start=fetch_start,
            end=fetch_end,
            progress=False,
            auto_adjust=True,
        )
        if raw is None or raw.empty:
            return {}, {}

        actual_prices: dict[str, float] = {}
        actual_returns: dict[str, float] = {}
        as_of_ts = pd.Timestamp(as_of)
        target_ts = pd.Timestamp(target)

        for ticker in self.tickers:
            closes = self._close_series(raw, ticker)
            if closes is None or closes.empty:
                continue
            # Align timezone-naive index for comparison
            idx = closes.index.tz_localize(None) if closes.index.tz is not None else closes.index
            closes = closes.copy()
            closes.index = idx

            on_or_before = closes.loc[closes.index <= as_of_ts]
            on_or_after_target = closes.loc[closes.index >= target_ts]
            if on_or_before.empty or on_or_after_target.empty:
                continue

            today_price = float(on_or_before.iloc[-1])
            tomorrow_price = float(on_or_after_target.iloc[0])
            if today_price == 0:
                continue
            actual_prices[ticker] = tomorrow_price
            actual_returns[ticker] = (tomorrow_price - today_price) / today_price

        return actual_prices, actual_returns

    def _equal_weight_period_returns(self) -> list[float]:
        """Equal-weight portfolio returns for each evaluated backtest date."""
        n = len(self.tickers)
        if n == 0:
            return []
        weight = 1.0 / n
        return [
            sum(weight * result.actual_returns.get(ticker, 0.0) for ticker in self.tickers)
            for result in self.results
        ]

    def _buy_hold_equal_weight_return(self) -> float | None:
        """
        Cumulative buy-and-hold equal-weight return from first to last evaluated date.

        Uses equal-weight across tickers on the first sample's start prices implied by
        actual returns chain reconstruction where possible; falls back to cumulative
        product of equal-weight period returns (same as rebalanced) when chain fails.
        """
        period_returns = self._equal_weight_period_returns()
        if not period_returns:
            return None
        # Approximate buy-and-hold as cumulative product of average asset returns
        # reconstructed per ticker over the sample dates, then equal-weight those.
        per_ticker_cum: list[float] = []
        for ticker in self.tickers:
            series = [r.actual_returns.get(ticker) for r in self.results]
            if any(value is None for value in series):
                continue
            path = 1.0
            for value in series:
                path *= 1.0 + float(value)  # type: ignore[arg-type]
            per_ticker_cum.append(path - 1.0)
        if not per_ticker_cum:
            return float(np.prod([1.0 + r for r in period_returns]) - 1.0)
        return float(np.mean(per_ticker_cum))

    def _spy_buy_hold_return(self, start_date: str, end_date: str) -> float | None:
        """Cumulative SPY buy-and-hold return over the backtest window (soft-fail)."""
        try:
            import yfinance as yf

            frame = yf.download(
                "SPY",
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
            )
            if frame is None or frame.empty or "Close" not in frame.columns:
                return None
            closes = frame["Close"].dropna()
            if len(closes) < 2:
                return None
            start_price = float(closes.iloc[0])
            end_price = float(closes.iloc[-1])
            if start_price == 0:
                return None
            return (end_price - start_price) / start_price
        except Exception:
            return None

    def _comparative_metrics(
        self,
        prediction: dict[str, Any],
        actual_prices: dict[str, float],
        actual_returns: dict[str, float],
        training_start: pd.Timestamp,
        test_date: pd.Timestamp,
    ) -> dict[str, float]:
        """Compute Prophet-vs-baseline forecast and strategy metrics for one date."""
        from src.extractor import extract_data
        from src.forecast_baselines import compare_forecast_mapes, implied_current_prices
        from src.processor import preprocess_data
        from src.strategy_comparison import (
            equal_weight_weights,
            historical_mean_mpt_weights,
            portfolio_period_return,
        )

        defaults = {
            "naive_price_mape": 0.0,
            "drift_price_mape": 0.0,
            "portfolio_historical_mpt_return": 0.0,
            "portfolio_equal_weight_return": 0.0,
        }
        try:
            portfolio_data = preprocess_data(
                extract_data(
                    self.tickers,
                    start_date=training_start.strftime("%Y-%m-%d"),
                    end_date=test_date.strftime("%Y-%m-%d"),
                )
            )
            if not portfolio_data:
                return defaults

            predicted_prices = prediction.get("predictions", {})
            predicted_returns = prediction.get("predicted_returns", {})
            current_prices = implied_current_prices(predicted_prices, predicted_returns)
            mean_returns = {
                ticker: float(df["Returns"].mean())
                for ticker, df in portfolio_data.items()
                if "Returns" in df.columns and not df["Returns"].dropna().empty
            }
            forecast_mapes = compare_forecast_mapes(
                actual_prices,
                predicted_prices,
                current_prices,
                mean_returns,
            )
            hist_weights = historical_mean_mpt_weights(portfolio_data)
            eq_weights = equal_weight_weights(self.tickers)
            return {
                "naive_price_mape": forecast_mapes["naive"],
                "drift_price_mape": forecast_mapes["drift"],
                "portfolio_historical_mpt_return": portfolio_period_return(
                    hist_weights, actual_returns
                ),
                "portfolio_equal_weight_return": portfolio_period_return(
                    eq_weights, actual_returns
                ),
            }
        except Exception:
            return defaults

    def _calculate_result(
        self,
        date: str,
        prediction: dict[str, Any],
        actual_prices: dict[str, float],
        actual_returns: dict[str, float],
        comparative: dict[str, float] | None = None,
    ) -> BacktestResult:
        """Calculate result for a single backtest date."""
        predicted_prices = prediction.get("predicted_prices") or prediction.get("predictions", {})
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

        comparative = comparative or {}

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
            naive_price_mape=float(comparative.get("naive_price_mape", 0.0)),
            drift_price_mape=float(comparative.get("drift_price_mape", 0.0)),
            portfolio_historical_mpt_return=float(
                comparative.get("portfolio_historical_mpt_return", 0.0)
            ),
            portfolio_equal_weight_return=float(
                comparative.get("portfolio_equal_weight_return", 0.0)
            ),
        )

    def _generate_summary(
        self,
        start_date: str,
        end_date: str,
        num_trades: int,
        include_benchmarks: bool = False,
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
                r.prediction_errors.get(ticker, 0)
                for r in self.results
                if ticker in r.prediction_errors
            ]
            if ticker_errors:
                ticker_mape[ticker] = float(np.mean(ticker_errors))

        cumulative_actual = (
            float(np.prod([1 + r for r in actual_returns]) - 1) if actual_returns else 0.0
        )

        bench_eq: float | None = None
        bench_bh: float | None = None
        bench_spy: float | None = None
        excess_eq: float | None = None
        excess_bh: float | None = None
        excess_spy: float | None = None

        if include_benchmarks and self.results:
            eq_returns = self._equal_weight_period_returns()
            if eq_returns:
                bench_eq = float(np.prod([1.0 + r for r in eq_returns]) - 1.0)
                excess_eq = cumulative_actual - bench_eq
            bench_bh = self._buy_hold_equal_weight_return()
            if bench_bh is not None:
                excess_bh = cumulative_actual - bench_bh
            bench_spy = self._spy_buy_hold_return(start_date, end_date)
            if bench_spy is not None:
                excess_spy = cumulative_actual - bench_spy

        # Comparative forecast and strategy aggregates
        from src.forecast_baselines import prophet_improvement_vs_baseline, win_rate
        from src.strategy_comparison import annualised_sharpe, strategy_win_rate

        prophet_mapes = [r.price_mape for r in self.results]
        naive_mapes = [r.naive_price_mape for r in self.results]
        drift_mapes = [r.drift_price_mape for r in self.results]
        hist_mpt_returns = [r.portfolio_historical_mpt_return for r in self.results]
        eq_period_returns = [r.portfolio_equal_weight_return for r in self.results]

        avg_prophet_mape = float(np.mean(prophet_mapes)) if prophet_mapes else 0.0
        avg_naive_mape = float(np.mean(naive_mapes)) if naive_mapes else 0.0
        avg_drift_mape = float(np.mean(drift_mapes)) if drift_mapes else 0.0
        cumulative_hist_mpt = (
            float(np.prod([1.0 + r for r in hist_mpt_returns]) - 1.0)
            if hist_mpt_returns
            else None
        )
        excess_hist_mpt = (
            cumulative_actual - cumulative_hist_mpt
            if cumulative_hist_mpt is not None
            else None
        )

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
            cumulative_actual_return=cumulative_actual,
            strategy_outperformance=float(
                np.prod([1 + r for r in actual_returns])
                / np.prod([1 + r for r in predicted_returns])
                - 1
            )
            if (predicted_returns and actual_returns)
            else 0.0,
            avg_portfolio_predicted_return=float(np.mean(predicted_returns))
            if predicted_returns
            else 0.0,
            avg_portfolio_actual_return=float(np.mean(actual_returns)) if actual_returns else 0.0,
            portfolio_sharpe_ratio=sharpe_ratio,
            portfolio_volatility=float(np.std(actual_returns) * np.sqrt(252))
            if actual_returns
            else 0.0,
            portfolio_max_drawdown=max_drawdown,
            ticker_mape=ticker_mape,
            benchmark_equal_weight_return=bench_eq,
            benchmark_buy_hold_equal_weight_return=bench_bh,
            benchmark_spy_return=bench_spy,
            excess_return_vs_equal_weight=excess_eq,
            excess_return_vs_buy_hold_equal_weight=excess_bh,
            excess_return_vs_spy=excess_spy,
            avg_naive_price_mape=avg_naive_mape,
            avg_drift_price_mape=avg_drift_mape,
            prophet_mape_improvement_vs_naive=prophet_improvement_vs_baseline(
                avg_prophet_mape, avg_naive_mape
            ),
            prophet_win_rate_vs_naive=win_rate(prophet_mapes, naive_mapes),
            prophet_win_rate_vs_drift=win_rate(prophet_mapes, drift_mapes),
            cumulative_historical_mpt_return=cumulative_hist_mpt,
            excess_return_vs_historical_mpt=excess_hist_mpt,
            strategy_win_rate_vs_equal_weight=strategy_win_rate(
                actual_returns, eq_period_returns
            ),
            strategy_win_rate_vs_historical_mpt=strategy_win_rate(
                actual_returns, hist_mpt_returns
            ),
            historical_mpt_sharpe_ratio=annualised_sharpe(hist_mpt_returns),
        )

    def results_to_dataframe(self) -> pd.DataFrame:
        """Convert results to DataFrame."""
        if not self.results:
            return pd.DataFrame()

        data = []
        for result in self.results:
            data.append(
                {
                    "date": result.date,
                    "price_mape": result.price_mape,
                    "return_mape": result.return_mape,
                    "predicted_return": result.portfolio_predicted_return,
                    "actual_return": result.portfolio_actual_return,
                }
            )

        return pd.DataFrame(data)
