"""CLI for backtesting and portfolio risk/sector analysis."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta

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

ANALYSIS_COMMANDS = frozenset({"backtest", "risk", "sector", "analyze"})


def build_parser() -> argparse.ArgumentParser:
    """Build the analysis CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Advanced portfolio analysis commands (backtest, risk, sector)."
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

    for name, help_text in (
        ("risk", "Risk metrics (VaR, CVaR, Sharpe) for current portfolio"),
        ("sector", "Sector allocation and concentration analysis"),
        ("analyze", "Run risk and sector analysis together"),
    ):
        cmd = subparsers.add_parser(name, help=help_text)
        cmd.add_argument("--tickers", nargs="+", default=PORTFOLIO_TICKERS)
        cmd.add_argument("--start", default=START_DATE, help="Historical data start date")
        cmd.add_argument("--end", default=END_DATE, help="Historical data end date")

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
    return True


def main(argv: list[str] | None = None) -> None:
    """Entry point for `python -m src.analysis_cli`."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not dispatch(argv):
        build_parser().print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
