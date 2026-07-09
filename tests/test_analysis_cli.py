"""Tests for analysis CLI dispatch."""

from unittest.mock import patch

from src.analysis_cli import ANALYSIS_COMMANDS, dispatch


class TestAnalysisCli:
    def test_dispatch_returns_false_for_default_optimize_argv(self) -> None:
        assert dispatch([]) is False
        assert dispatch(["--help"]) is False

    def test_dispatch_handles_backtest(self) -> None:
        with patch("src.analysis_cli.run_backtest_command") as mock_run:
            handled = dispatch(["backtest", "--start", "2024-01-01", "--end", "2024-03-01"])
        assert handled is True
        mock_run.assert_called_once()

    def test_analysis_commands_frozen_set(self) -> None:
        assert "backtest" in ANALYSIS_COMMANDS
        assert "analyze" in ANALYSIS_COMMANDS
        assert "score-outcomes" in ANALYSIS_COMMANDS
        assert "evaluate" in ANALYSIS_COMMANDS

    def test_dispatch_handles_analyze(self) -> None:
        with patch("src.analysis_cli.run_analyze_command") as mock_run:
            handled = dispatch(["analyze"])
        assert handled is True
        mock_run.assert_called_once()

    def test_dispatch_handles_evaluate(self) -> None:
        with patch("src.analysis_cli.run_evaluate_command") as mock_run:
            handled = dispatch(["evaluate", "--mode", "smoke"])
        assert handled is True
        mock_run.assert_called_once()

    def test_dispatch_handles_score_outcomes(self) -> None:
        with patch("src.analysis_cli.run_score_outcomes_command") as mock_run:
            handled = dispatch(["score-outcomes"])
        assert handled is True
        mock_run.assert_called_once()
