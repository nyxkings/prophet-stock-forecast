"""Tests for unified evaluation module and outcome scoring helpers."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.backtesting import Backtester, BacktestResult, BacktestSummary
from src.database import save_results_to_supabase, score_previous_predictions
from src.evaluation import (
    EvaluationReport,
    build_report_from_backtest,
    build_report_from_stored_outcomes,
    build_smoke_report,
)


def _sample_summary(**overrides: object) -> BacktestSummary:
    data = {
        "start_date": "2024-01-01",
        "end_date": "2024-03-01",
        "num_days": 60,
        "num_trades": 10,
        "total_days_tested": 10,
        "avg_price_mape": 2.0,
        "std_price_mape": 0.5,
        "min_price_mape": 1.0,
        "max_price_mape": 3.0,
        "avg_return_mape": 0.01,
        "std_return_mape": 0.002,
        "min_return_mape": 0.001,
        "max_return_mape": 0.02,
        "cumulative_predicted_return": 0.03,
        "cumulative_actual_return": 0.025,
        "strategy_outperformance": -0.005,
        "avg_portfolio_predicted_return": 0.003,
        "avg_portfolio_actual_return": 0.0025,
        "portfolio_sharpe_ratio": 1.2,
        "portfolio_volatility": 0.18,
        "portfolio_max_drawdown": -0.04,
        "ticker_mape": {"AAPL": 1.5},
        "benchmark_equal_weight_return": 0.02,
        "benchmark_buy_hold_equal_weight_return": 0.019,
        "benchmark_spy_return": 0.015,
        "excess_return_vs_equal_weight": 0.005,
        "excess_return_vs_buy_hold_equal_weight": 0.006,
        "excess_return_vs_spy": 0.01,
    }
    data.update(overrides)
    return BacktestSummary(**data)  # type: ignore[arg-type]


class TestEvaluationReport:
    def test_smoke_report_schema(self, tmp_path: Path) -> None:
        report = build_smoke_report()
        assert report.source == "smoke"
        assert report.num_observations > 0
        assert "equal_weight" in report.benchmarks
        assert "spy" in report.excess_returns
        path = report.write_json(tmp_path / "evaluation_report.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["price_mape"] == report.price_mape
        assert "Portfolio Sharpe" in report.to_markdown()

    def test_build_from_backtest(self) -> None:
        summary = _sample_summary()
        report = build_report_from_backtest(summary)
        assert report.source == "backtest"
        assert report.price_mape == 2.0
        assert report.benchmarks["spy"] == 0.015
        assert report.excess_returns["equal_weight"] == 0.005

    def test_build_from_backtest_notes_missing_spy(self) -> None:
        summary = _sample_summary(benchmark_spy_return=None, excess_return_vs_spy=None)
        report = build_report_from_backtest(summary)
        assert any("SPY" in note for note in report.notes)

    def test_build_from_stored_outcomes(self) -> None:
        rows = [
            {
                "as_of_date": "2024-01-02",
                "predicted_price": 100.0,
                "actual_price": 102.0,
                "predicted_return": 0.01,
                "actual_return": 0.02,
            },
            {
                "as_of_date": "2024-01-03",
                "predicted_price": 200.0,
                "actual_price": 198.0,
                "predicted_return": -0.005,
                "actual_return": -0.01,
            },
        ]
        report = build_report_from_stored_outcomes(rows)
        assert report.num_observations == 2
        assert report.price_mape > 0
        assert report.price_rmse > 0
        assert report.price_mae > 0
        assert report.start_date == "2024-01-02"

    def test_build_from_empty_outcomes(self) -> None:
        report = build_report_from_stored_outcomes([])
        assert report.num_observations == 0
        assert report.notes


class TestBenchmarkHelpers:
    def test_equal_weight_benchmark_from_results(self) -> None:
        backtester = Backtester(tickers=["AAPL", "MSFT"])
        backtester.results = [
            BacktestResult(
                date="2024-01-02",
                predicted_prices={"AAPL": 100, "MSFT": 200},
                predicted_returns={"AAPL": 0.01, "MSFT": 0.02},
                predicted_weights={"AAPL": 0.5, "MSFT": 0.5},
                actual_prices={"AAPL": 101, "MSFT": 202},
                actual_returns={"AAPL": 0.02, "MSFT": 0.04},
                prediction_errors={"AAPL": 1.0, "MSFT": 1.0},
                price_mape=1.0,
                return_mape=0.01,
                portfolio_predicted_return=0.015,
                portfolio_actual_return=0.03,
            ),
            BacktestResult(
                date="2024-01-03",
                predicted_prices={"AAPL": 101, "MSFT": 202},
                predicted_returns={"AAPL": 0.0, "MSFT": 0.0},
                predicted_weights={"AAPL": 0.5, "MSFT": 0.5},
                actual_prices={"AAPL": 100, "MSFT": 200},
                actual_returns={"AAPL": -0.01, "MSFT": -0.01},
                prediction_errors={"AAPL": 1.0, "MSFT": 1.0},
                price_mape=1.0,
                return_mape=0.01,
                portfolio_predicted_return=0.0,
                portfolio_actual_return=-0.01,
            ),
        ]
        summary = backtester._generate_summary(
            "2024-01-01", "2024-01-10", num_trades=2, include_benchmarks=True
        )
        assert summary.benchmark_equal_weight_return is not None
        assert summary.excess_return_vs_equal_weight is not None
        # With equal weights matching strategy weights on these samples, excess ~ 0
        assert abs(summary.excess_return_vs_equal_weight) < 1e-9

    def test_spy_unavailable_is_none(self) -> None:
        backtester = Backtester(tickers=["AAPL"])
        backtester.results = [
            BacktestResult(
                date="2024-01-02",
                predicted_prices={"AAPL": 100},
                predicted_returns={"AAPL": 0.01},
                predicted_weights={"AAPL": 1.0},
                actual_prices={"AAPL": 101},
                actual_returns={"AAPL": 0.01},
                prediction_errors={"AAPL": 1.0},
                price_mape=1.0,
                return_mape=0.0,
                portfolio_predicted_return=0.01,
                portfolio_actual_return=0.01,
            )
        ]
        with patch.object(Backtester, "_spy_buy_hold_return", return_value=None):
            summary = backtester._generate_summary(
                "2024-01-01", "2024-01-10", 1, include_benchmarks=True
            )
        assert summary.benchmark_spy_return is None
        assert summary.benchmark_equal_weight_return is not None


class TestSaveResultsAdditiveFields:
    @patch("src.database.get_supabase_client")
    def test_save_includes_optional_outcome_fields(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock()
        mock_get_client.return_value = mock_client

        result = {
            "date": date(2024, 1, 31),
            "prediction_date": date(2024, 2, 1),
            "predictions": {"AAPL": 150.25},
            "predicted_returns": {"AAPL": 0.02},
            "weights": {"AAPL": 1.0},
            "current_prices": {"AAPL": 147.3},
            "actual_prices_last_month": {"AAPL": [146.0, 147.3]},
        }
        save_results_to_supabase(result)
        row = mock_table.insert.call_args[0][0][0]
        assert row["current_price"] == 147.3
        assert row["prediction_target_date"] == "2024-02-01"
        assert row["actual_price"] is None
        assert row["scored_at"] is None

    @patch("src.database.get_supabase_client")
    def test_save_falls_back_without_outcome_columns(self, mock_get_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.side_effect = [
            Exception("Could not find the 'current_price' column of 'stock_optimisation_store'"),
            MagicMock(),
        ]
        mock_get_client.return_value = mock_client

        result = {
            "date": date(2024, 1, 31),
            "predictions": {"AAPL": 150.25},
            "predicted_returns": {"AAPL": 0.02},
            "weights": {"AAPL": 1.0},
            "current_prices": {"AAPL": 147.3},
            "actual_prices_last_month": {"AAPL": [147.3]},
        }
        save_results_to_supabase(result)
        assert mock_insert.execute.call_count == 2
        legacy_row = mock_table.insert.call_args_list[1][0][0][0]
        assert "current_price" not in legacy_row
        assert legacy_row["predicted_price"] == 150.25


class TestScorePreviousPredictions:
    @patch("src.database._close_price_on_or_after", return_value=160.0)
    @patch("src.database.get_supabase_client")
    def test_score_updates_row(
        self,
        mock_get_client: MagicMock,
        _mock_price: MagicMock,
    ) -> None:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        select_chain = MagicMock()
        mock_client.table.return_value.select.return_value = select_chain
        select_chain.is_.return_value.order.return_value.limit.return_value.execute.return_value = (
            MagicMock(
                data=[
                    {
                        "id": "row-1",
                        "as_of_date": date.today().isoformat(),
                        "ticker": "AAPL",
                        "predicted_price": 155.0,
                        "predicted_return": 0.01,
                        "current_price": 150.0,
                        "prediction_target_date": "2020-01-02",
                        "actual_price": None,
                        "actual_prices_last_month": "[150.0]",
                    }
                ]
            )
        )
        update_chain = MagicMock()
        mock_client.table.return_value.update.return_value = update_chain
        update_chain.eq.return_value.execute.return_value = MagicMock()

        # Force target day in the past by using as_of far in past relative to today
        select_chain.is_.return_value.order.return_value.limit.return_value.execute.return_value = (
            MagicMock(
                data=[
                    {
                        "id": "row-1",
                        "as_of_date": "2024-06-01",
                        "ticker": "AAPL",
                        "predicted_price": 155.0,
                        "predicted_return": 0.01,
                        "current_price": 150.0,
                        "prediction_target_date": "2024-06-02",
                        "actual_price": None,
                        "actual_prices_last_month": "[150.0]",
                    }
                ]
            )
        )

        summary = score_previous_predictions(lookback_days=9000)
        assert summary["updated"] == 1
        update_chain.eq.assert_called_with("id", "row-1")

    @patch("src.database.get_supabase_client", return_value=None)
    def test_score_requires_credentials(self, _mock_client: MagicMock) -> None:
        try:
            score_previous_predictions()
            raised = False
        except ValueError:
            raised = True
        assert raised


class TestEvaluationReportDataclass:
    def test_to_dict_roundtrip_keys(self) -> None:
        report = EvaluationReport(source="unit", price_mape=1.0)
        assert report.to_dict()["source"] == "unit"
