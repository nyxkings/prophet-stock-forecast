"""Tests for comparative evaluation in backtesting summaries."""

from __future__ import annotations

from src.backtesting import Backtester, BacktestResult
from src.evaluation import build_report_from_backtest


def _result(**overrides: object) -> BacktestResult:
    data = {
        "date": "2024-01-02",
        "predicted_prices": {"AAPL": 100.0},
        "predicted_returns": {"AAPL": 0.01},
        "predicted_weights": {"AAPL": 1.0},
        "actual_prices": {"AAPL": 101.0},
        "actual_returns": {"AAPL": 0.02},
        "prediction_errors": {"AAPL": 1.0},
        "price_mape": 1.5,
        "return_mape": 0.01,
        "portfolio_predicted_return": 0.01,
        "portfolio_actual_return": 0.02,
        "naive_price_mape": 2.0,
        "drift_price_mape": 1.8,
        "portfolio_historical_mpt_return": 0.015,
        "portfolio_equal_weight_return": 0.02,
    }
    data.update(overrides)
    return BacktestResult(**data)  # type: ignore[arg-type]


class TestComparativeBacktest:
    def test_summary_includes_comparative_fields(self) -> None:
        backtester = Backtester(tickers=["AAPL"])
        backtester.results = [
            _result(),
            _result(
                date="2024-01-03",
                price_mape=1.0,
                naive_price_mape=2.5,
                portfolio_actual_return=0.01,
                portfolio_historical_mpt_return=0.005,
                portfolio_equal_weight_return=0.008,
            ),
        ]
        summary = backtester._generate_summary(
            "2024-01-01", "2024-01-10", num_trades=2, include_benchmarks=True
        )
        assert summary.avg_naive_price_mape > 0
        assert summary.prophet_win_rate_vs_naive >= 0
        assert summary.cumulative_historical_mpt_return is not None

    def test_evaluation_report_includes_comparisons(self) -> None:
        backtester = Backtester(tickers=["AAPL"])
        backtester.results = [_result(), _result(date="2024-01-03", price_mape=0.5)]
        summary = backtester._generate_summary(
            "2024-01-01", "2024-01-10", num_trades=2, include_benchmarks=False
        )
        report = build_report_from_backtest(summary, results=backtester.results)
        assert "prophet" in report.forecast_comparison
        assert "naive_random_walk" in report.forecast_comparison
        assert "prophet_mpt" in report.strategy_comparison
        assert report.statistical_summary["prophet_win_rate_vs_naive"] is not None
