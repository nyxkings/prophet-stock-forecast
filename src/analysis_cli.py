"""CLI for backtesting and portfolio risk/sector analysis."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.backtesting import Backtester
from src.main import run_optimisation
from src.portfolio_analysis import (
    analyze_portfolio_risk,
    analyze_portfolio_sectors,
    format_backtest_summary,
    load_returns_data,
    save_backtest_report,
    sector_analysis_to_records,
)
from src.settings import END_DATE, PORTFOLIO_TICKERS, START_DATE

logger = logging.getLogger(__name__)

ANALYSIS_COMMANDS = frozenset(
    {"backtest", "risk", "sector", "analyze", "score-outcomes", "evaluate", "compare"}
)


def build_parser() -> argparse.ArgumentParser:
    """Build the analysis CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Advanced portfolio analysis commands (backtest, risk, sector, evaluate)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest = subparsers.add_parser("backtest", help="Run walk-forward backtest")
    backtest.add_argument("--tickers", nargs="+", default=PORTFOLIO_TICKERS)
    backtest.add_argument("--start", default=None, help="Backtest start date (YYYY-MM-DD)")
    backtest.add_argument("--end", default=END_DATE, help="Backtest end date (YYYY-MM-DD)")
    backtest.add_argument("--training-days", type=int, default=252)
    backtest.add_argument(
        "--output",
        default="backtest_report.csv",
        help="CSV path for per-date backtest results",
    )
    backtest.add_argument(
        "--evaluation-output",
        default="evaluation_report.json",
        help="JSON path for unified evaluation report",
    )

    for name, help_text in (
        ("risk", "Risk metrics (VaR, CVaR, Sharpe) for current portfolio"),
        ("sector", "Sector allocation and concentration analysis"),
        ("analyze", "Run risk and sector analysis together"),
    ):
        cmd = subparsers.add_parser(name, help=help_text)
        cmd.add_argument("--tickers", nargs="+", default=PORTFOLIO_TICKERS)
        cmd.add_argument("--start", default=START_DATE, help="Historical data start date")
        cmd.add_argument("--end", default=END_DATE, help="Historical data end date")

    score = subparsers.add_parser(
        "score-outcomes",
        help="Fill actual outcomes for previously saved Supabase predictions (soft-fail)",
    )
    score.add_argument(
        "--lookback-days",
        type=int,
        default=14,
        help="Only score rows with as_of_date within this many days",
    )

    evaluate = subparsers.add_parser(
        "evaluate",
        help="Write unified evaluation report (smoke by default; optional stored outcomes)",
    )
    evaluate.add_argument(
        "--mode",
        choices=["smoke", "stored", "backtest"],
        default="smoke",
        help="smoke=CI fixture; stored=Supabase scored rows; backtest=short walk-forward",
    )
    evaluate.add_argument(
        "--output",
        default="evaluation_report.json",
        help="JSON path for evaluation report",
    )
    evaluate.add_argument("--tickers", nargs="+", default=PORTFOLIO_TICKERS)
    evaluate.add_argument("--start", default=None, help="Backtest start (mode=backtest)")
    evaluate.add_argument("--end", default=END_DATE, help="Backtest end (mode=backtest)")
    evaluate.add_argument("--training-days", type=int, default=252)

    compare = subparsers.add_parser(
        "compare",
        help="Walk-forward comparison: Prophet vs forecast baselines and portfolio alternatives",
    )
    compare.add_argument("--tickers", nargs="+", default=PORTFOLIO_TICKERS)
    compare.add_argument("--start", default=None, help="Backtest start date (YYYY-MM-DD)")
    compare.add_argument("--end", default=END_DATE, help="Backtest end date (YYYY-MM-DD)")
    compare.add_argument("--training-days", type=int, default=252)
    compare.add_argument(
        "--output",
        default="comparative_evaluation.json",
        help="JSON path for comparative evaluation report",
    )

    return parser


def _default_backtest_start() -> str:
    return (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")


def _run_optimisation_for_analysis(
    tickers: list[str],
    start_date: str,
    end_date: str,
) -> tuple[dict[str, float], dict[str, float], dict]:
    result = run_optimisation(tickers=tickers, start_date=start_date, end_date=end_date)
    if not result:
        raise RuntimeError("Optimisation failed; cannot run portfolio analysis.")

    returns_data = load_returns_data(tickers, start_date=start_date, end_date=end_date)
    return result["weights"], result["predicted_returns"], returns_data


def run_backtest_command(args: argparse.Namespace) -> None:
    """Execute backtest command."""
    from src.evaluation import build_report_from_backtest

    start_date = args.start or _default_backtest_start()
    backtester = Backtester(tickers=args.tickers)
    summary = backtester.run(
        start_date=start_date,
        end_date=args.end,
        training_days=args.training_days,
    )
    print(format_backtest_summary(summary))
    report_path = save_backtest_report(backtester, args.output)
    print(f"\nBacktest report saved to {report_path}")

    evaluation = build_report_from_backtest(summary, results=backtester.results)
    eval_path = evaluation.write_json(args.evaluation_output)
    print(f"Evaluation report saved to {eval_path}")


def run_compare_command(args: argparse.Namespace) -> None:
    """Run comparative evaluation with Prophet vs baselines and alternative strategies."""
    from src.evaluation import build_report_from_backtest

    start_date = args.start or _default_backtest_start()
    backtester = Backtester(tickers=args.tickers)
    summary = backtester.run(
        start_date=start_date,
        end_date=args.end,
        training_days=args.training_days,
    )
    print(format_backtest_summary(summary))
    report = build_report_from_backtest(summary, source="comparative", results=backtester.results)
    path = report.write_json(args.output)
    print(report.to_markdown())
    print(f"\nComparative evaluation saved to {path}")


def run_risk_command(args: argparse.Namespace) -> None:
    """Execute risk analysis command."""
    weights, _, returns_data = _run_optimisation_for_analysis(args.tickers, args.start, args.end)
    metrics, concentration = analyze_portfolio_risk(weights, returns_data)
    print("Portfolio risk metrics")
    print(f"  VaR 95%: {metrics.var_95:.4f}")
    print(f"  VaR 99%: {metrics.var_99:.4f}")
    print(f"  CVaR 95%: {metrics.cvar_95:.4f}")
    print(f"  CVaR 99%: {metrics.cvar_99:.4f}")
    print(f"  Sharpe ratio: {metrics.sharpe_ratio:.2f}")
    print(f"  Volatility (ann.): {metrics.volatility:.4f}")
    print(f"  Max drawdown: {metrics.max_drawdown:.2%}")
    print("Concentration")
    print(f"  Herfindahl index: {concentration['herfindahl_index']:.4f}")
    print(f"  Effective assets: {concentration['effective_assets']:.2f}")


def run_sector_command(args: argparse.Namespace) -> None:
    """Execute sector analysis command."""
    weights, expected_returns, returns_data = _run_optimisation_for_analysis(
        args.tickers, args.start, args.end
    )
    analysis = analyze_portfolio_sectors(
        weights,
        returns_data=returns_data,
        expected_returns=expected_returns,
    )
    print("Sector analysis")
    print(f"  Concentration level: {analysis.sector_concentration_level}")
    print(f"  HHI: {analysis.herfindahl_index:.4f}")
    print(f"  Effective sectors: {analysis.effective_number_of_sectors:.2f}")
    print(f"  Largest sector: {analysis.largest_sector}")
    for record in sector_analysis_to_records(analysis):
        print(
            f"  {record['sector']}: {record['allocation'] * 100:.1f}% "
            f"({record['holdings']} holdings)"
        )


def run_analyze_command(args: argparse.Namespace) -> None:
    """Execute combined risk and sector analysis."""
    run_risk_command(args)
    print()
    run_sector_command(args)


def run_score_outcomes_command(args: argparse.Namespace) -> None:
    """Score previous predictions (soft-fail wrapper used by daily job / CLI)."""
    from src.database import score_previous_predictions

    try:
        summary = score_previous_predictions(lookback_days=args.lookback_days)
        print(
            "Outcome scoring: "
            f"attempted={summary.get('attempted', 0)} "
            f"updated={summary.get('updated', 0)} "
            f"skipped={summary.get('skipped', 0)} "
            f"errors={summary.get('errors', 0)}"
        )
    except Exception as exc:
        logger.warning("Outcome scoring failed: %s", exc)
        print(f"Warning: outcome scoring skipped: {exc}")


def run_evaluate_command(args: argparse.Namespace) -> None:
    """Write a unified evaluation report without blocking on market failures."""
    from src.evaluation import (
        build_report_from_backtest,
        build_report_from_stored_outcomes,
        build_smoke_report,
    )

    output = Path(args.output)
    if args.mode == "smoke":
        report = build_smoke_report()
    elif args.mode == "stored":
        try:
            from src.database import fetch_scored_outcomes

            rows = fetch_scored_outcomes()
            report = build_report_from_stored_outcomes(rows)
        except Exception as exc:
            logger.warning("Stored evaluation unavailable (%s); writing smoke report.", exc)
            report = build_smoke_report()
            report.notes.append(f"Fell back to smoke report: {exc}")
    else:
        start_date = args.start or _default_backtest_start()
        try:
            backtester = Backtester(tickers=args.tickers)
            summary = backtester.run(
                start_date=start_date,
                end_date=args.end,
                training_days=args.training_days,
            )
            report = build_report_from_backtest(summary, results=backtester.results)
        except Exception as exc:
            logger.warning("Backtest evaluation failed (%s); writing smoke report.", exc)
            report = build_smoke_report()
            report.notes.append(f"Fell back to smoke report: {exc}")

    path = report.write_json(output)
    print(report.to_markdown())
    print(f"\nEvaluation report saved to {path}")


def dispatch(argv: list[str]) -> bool:
    """
    Run an analysis command if argv names one.

    Returns:
        True if argv was handled, False to fall through to default optimise CLI.
    """
    if not argv or argv[0] not in ANALYSIS_COMMANDS:
        return False

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "backtest":
        run_backtest_command(args)
    elif args.command == "risk":
        run_risk_command(args)
    elif args.command == "sector":
        run_sector_command(args)
    elif args.command == "analyze":
        run_analyze_command(args)
    elif args.command == "score-outcomes":
        run_score_outcomes_command(args)
    elif args.command == "evaluate":
        run_evaluate_command(args)
    elif args.command == "compare":
        run_compare_command(args)
    return True


def main(argv: list[str] | None = None) -> None:
    """Entry point for `python -m src.analysis_cli`."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not dispatch(argv):
        build_parser().print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
