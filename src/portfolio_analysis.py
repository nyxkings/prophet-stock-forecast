"""Shared helpers wiring backtesting, risk, and sector modules into the workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.backtesting import Backtester, BacktestSummary
from src.extractor import extract_data
from src.processor import preprocess_data
from src.risk_analytics import RiskAnalyzer, RiskMetrics
from src.sector_analysis import PortfolioSectorAnalysis, SectorAnalyzer
from src.settings import END_DATE, START_DATE


def weights_from_date_df(date_df: pd.DataFrame) -> dict[str, float]:
    """Build a weights dict from a per-ticker dashboard DataFrame."""
    return {
        str(row["ticker"]): float(row["portfolio_weight"])
        for _, row in date_df.iterrows()
        if pd.notna(row.get("portfolio_weight"))
    }


def expected_returns_from_date_df(date_df: pd.DataFrame) -> dict[str, float]:
    """Build expected returns from stored predicted_return values."""
    return {
        str(row["ticker"]): float(row["predicted_return"])
        for _, row in date_df.iterrows()
        if pd.notna(row.get("predicted_return"))
    }


def load_returns_data(
    tickers: list[str],
    start_date: str = START_DATE,
    end_date: str = END_DATE,
) -> dict[str, pd.DataFrame]:
    """Load aligned historical DataFrames with Returns columns."""
    return preprocess_data(extract_data(tickers, start_date=start_date, end_date=end_date))


def compute_weighted_portfolio_returns(
    weights: dict[str, float],
    returns_data: dict[str, pd.DataFrame],
) -> np.ndarray:
    """Compute daily portfolio returns as a weighted sum of asset returns."""
    tickers = [ticker for ticker in weights if ticker in returns_data]
    if not tickers:
        return np.array([])

    returns_df = pd.DataFrame(
        {ticker: returns_data[ticker]["Returns"] for ticker in tickers}
    ).dropna()
    if returns_df.empty:
        return np.array([])

    weight_series = pd.Series(weights)[tickers]
    portfolio_returns = (returns_df * weight_series).sum(axis=1).to_numpy()
    return np.asarray(portfolio_returns)


def run_backtest(
    tickers: list[str],
    start_date: str,
    end_date: str,
    training_days: int = 252,
) -> BacktestSummary:
    """Execute walk-forward backtest over the given date range."""
    backtester = Backtester(tickers=tickers)
    return backtester.run(
        start_date=start_date,
        end_date=end_date,
        training_days=training_days,
    )


def format_backtest_summary(summary: BacktestSummary) -> str:
    """Format backtest summary metrics for CLI output."""
    lines = [
        "Backtest summary",
        f"  Period: {summary.start_date} → {summary.end_date}",
        f"  Trades evaluated: {summary.num_trades}",
        f"  Avg price MAPE: {summary.avg_price_mape:.2f}%",
        f"  Avg return MAPE: {summary.avg_return_mape:.2f}%",
        f"  Portfolio Sharpe: {summary.portfolio_sharpe_ratio:.2f}",
        f"  Portfolio volatility: {summary.portfolio_volatility:.4f}",
        f"  Max drawdown: {summary.portfolio_max_drawdown:.2%}",
        f"  Cumulative actual return: {summary.cumulative_actual_return:.2%}",
        f"  Strategy outperformance: {summary.strategy_outperformance:.2%}",
    ]
    return "\n".join(lines)


def save_backtest_report(
    backtester: Backtester,
    output_path: str | Path,
) -> Path:
    """Write per-date backtest results to CSV."""
    path = Path(output_path)
    backtester.results_to_dataframe().to_csv(path, index=False)
    return path


def analyze_portfolio_risk(
    weights: dict[str, float],
    returns_data: dict[str, pd.DataFrame],
) -> tuple[RiskMetrics, dict[str, float]]:
    """Compute portfolio risk metrics and concentration from historical returns."""
    portfolio_returns = compute_weighted_portfolio_returns(weights, returns_data)
    if len(portfolio_returns) == 0:
        raise ValueError("No overlapping historical returns available for portfolio risk analysis.")

    metrics = RiskAnalyzer.calculate_portfolio_metrics(portfolio_returns)
    concentration = RiskAnalyzer.calculate_portfolio_concentration(weights)
    return metrics, concentration


def analyze_portfolio_sectors(
    weights: dict[str, float],
    returns_data: dict[str, pd.DataFrame] | None = None,
    expected_returns: dict[str, float] | None = None,
) -> PortfolioSectorAnalysis:
    """Run sector exposure and concentration analysis."""
    return SectorAnalyzer.analyze_portfolio_sectors(
        weights,
        returns_data=returns_data,
        expected_returns=expected_returns,
    )


def risk_metrics_to_dict(metrics: RiskMetrics) -> dict[str, float]:
    """Serialize RiskMetrics for display."""
    return metrics.to_dict()


def sector_analysis_to_records(analysis: PortfolioSectorAnalysis) -> list[dict[str, Any]]:
    """Flatten sector analysis for tabular display."""
    records: list[dict[str, Any]] = []
    for sector, metrics in analysis.sector_metrics.items():
        records.append(
            {
                "sector": sector,
                "allocation": metrics.allocation,
                "holdings": metrics.number_of_holdings,
                "volatility": metrics.volatility,
                "expected_return": metrics.expected_return,
            }
        )
    return records
