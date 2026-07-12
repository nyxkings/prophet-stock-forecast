"""Unified evaluation report for forecast accuracy, portfolio risk, and benchmarks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.backtesting import BacktestResult, BacktestSummary


@dataclass
class EvaluationReport:
    """Standard metrics used by CLI, CI smoke tests, and production scoring."""

    source: str
    start_date: str | None = None
    end_date: str | None = None
    num_observations: int = 0
    price_mape: float = 0.0
    price_rmse: float = 0.0
    price_mae: float = 0.0
    price_r2: float = 0.0
    return_mape: float = 0.0
    portfolio_sharpe: float = 0.0
    portfolio_volatility: float = 0.0
    portfolio_max_drawdown: float = 0.0
    cumulative_actual_return: float = 0.0
    cumulative_predicted_return: float = 0.0
    benchmarks: dict[str, float | None] = field(default_factory=dict)
    excess_returns: dict[str, float | None] = field(default_factory=dict)
    forecast_comparison: dict[str, float] = field(default_factory=dict)
    strategy_comparison: dict[str, dict[str, float | None]] = field(default_factory=dict)
    statistical_summary: dict[str, float | None] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize report for JSON / artifacts."""
        return asdict(self)

    def to_markdown(self) -> str:
        """Human-readable summary for CLI / reports."""
        lines = [
            "# Evaluation Report",
            f"- Source: {self.source}",
            f"- Period: {self.start_date or 'n/a'} → {self.end_date or 'n/a'}",
            f"- Observations: {self.num_observations}",
            f"- Price MAPE: {self.price_mape:.2f}%",
            f"- Price RMSE: ${self.price_rmse:.2f}",
            f"- Price MAE: ${self.price_mae:.2f}",
            f"- Price R²: {self.price_r2:.4f}",
            f"- Return MAPE: {self.return_mape:.4f}",
            f"- Portfolio Sharpe: {self.portfolio_sharpe:.2f}",
            f"- Volatility: {self.portfolio_volatility:.4f}",
            f"- Max drawdown: {self.portfolio_max_drawdown:.2%}",
            f"- Cumulative actual return: {self.cumulative_actual_return:.2%}",
            f"- Cumulative predicted return: {self.cumulative_predicted_return:.2%}",
        ]
        if self.benchmarks:
            lines.append("- Benchmarks:")
            for name, value in self.benchmarks.items():
                rendered = f"{value:.2%}" if value is not None else "n/a"
                lines.append(f"  - {name}: {rendered}")
        if self.excess_returns:
            lines.append("- Excess returns vs benchmarks:")
            for name, value in self.excess_returns.items():
                rendered = f"{value:.2%}" if value is not None else "n/a"
                lines.append(f"  - vs {name}: {rendered}")
        if self.forecast_comparison:
            lines.append("- Forecast comparison (avg MAPE %):")
            for name, value in self.forecast_comparison.items():
                lines.append(f"  - {name}: {value:.2f}%")
        if self.strategy_comparison:
            lines.append("- Strategy comparison:")
            for name, metrics in self.strategy_comparison.items():
                cum = metrics.get("cumulative_return")
                sharpe = metrics.get("sharpe_ratio")
                excess = metrics.get("excess_vs_equal_weight")
                cum_s = f"{cum:.2%}" if cum is not None else "n/a"
                sharpe_s = f"{sharpe:.2f}" if sharpe is not None else "n/a"
                excess_s = f"{excess:.2%}" if excess is not None else "n/a"
                lines.append(
                    f"  - {name}: cumulative={cum_s}, Sharpe={sharpe_s}, "
                    f"excess vs EW={excess_s}"
                )
        if self.statistical_summary:
            lines.append("- Statistical summary:")
            for name, value in self.statistical_summary.items():
                if value is None:
                    rendered = "n/a"
                elif "rate" in name or "win" in name:
                    rendered = f"{value:.1%}"
                else:
                    rendered = f"{value:.4f}"
                lines.append(f"  - {name}: {rendered}")
        for note in self.notes:
            lines.append(f"- Note: {note}")
        return "\n".join(lines)

    def write_json(self, path: str | Path) -> Path:
        """Write report JSON to disk."""
        output = Path(path)
        output.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return output


def build_report_from_backtest(
    summary: BacktestSummary,
    source: str = "backtest",
    results: list[BacktestResult] | None = None,
) -> EvaluationReport:
    """Build a unified report from an existing BacktestSummary."""
    from src.strategy_comparison import summarise_strategies

    benchmarks = {
        "equal_weight": summary.benchmark_equal_weight_return,
        "buy_and_hold_equal_weight": summary.benchmark_buy_hold_equal_weight_return,
        "spy": summary.benchmark_spy_return,
    }
    excess = {
        "equal_weight": summary.excess_return_vs_equal_weight,
        "buy_and_hold_equal_weight": summary.excess_return_vs_buy_hold_equal_weight,
        "spy": summary.excess_return_vs_spy,
    }
    notes: list[str] = []
    if summary.benchmark_spy_return is None:
        notes.append("SPY benchmark unavailable for this run.")

    forecast_comparison = {
        "prophet": summary.avg_price_mape,
        "naive_random_walk": summary.avg_naive_price_mape,
        "drift_historical_mean": summary.avg_drift_price_mape,
    }

    if results:
        prophet_returns = [r.portfolio_actual_return for r in results]
        hist_returns = [r.portfolio_historical_mpt_return for r in results]
        eq_returns = [r.portfolio_equal_weight_return for r in results]
        strategy_comparison = summarise_strategies(
            prophet_mpt_returns=prophet_returns,
            historical_mpt_returns=hist_returns,
            equal_weight_returns=eq_returns,
        )
    else:
        strategy_comparison = {}

    statistical_summary = {
        "prophet_mape_improvement_vs_naive_pp": summary.prophet_mape_improvement_vs_naive,
        "prophet_win_rate_vs_naive": summary.prophet_win_rate_vs_naive,
        "prophet_win_rate_vs_drift": summary.prophet_win_rate_vs_drift,
        "strategy_win_rate_vs_equal_weight": summary.strategy_win_rate_vs_equal_weight,
        "strategy_win_rate_vs_historical_mpt": summary.strategy_win_rate_vs_historical_mpt,
        "excess_return_vs_historical_mpt": summary.excess_return_vs_historical_mpt,
    }

    return EvaluationReport(
        source=source,
        start_date=summary.start_date,
        end_date=summary.end_date,
        num_observations=summary.total_days_tested,
        price_mape=summary.avg_price_mape,
        return_mape=summary.avg_return_mape,
        portfolio_sharpe=summary.portfolio_sharpe_ratio,
        portfolio_volatility=summary.portfolio_volatility,
        portfolio_max_drawdown=summary.portfolio_max_drawdown,
        cumulative_actual_return=summary.cumulative_actual_return,
        cumulative_predicted_return=summary.cumulative_predicted_return,
        benchmarks=benchmarks,
        excess_returns=excess,
        forecast_comparison=forecast_comparison,
        strategy_comparison=strategy_comparison,
        statistical_summary=statistical_summary,
        notes=notes,
    )


def build_report_from_stored_outcomes(
    rows: list[dict[str, Any]],
    source: str = "stored_outcomes",
) -> EvaluationReport:
    """Build a report from scored Supabase prediction rows."""
    import numpy as np

    if not rows:
        return EvaluationReport(source=source, notes=["No scored outcome rows available."])

    price_errors: list[float] = []
    return_errors: list[float] = []
    predicted_prices: list[float] = []
    actual_prices: list[float] = []
    dates: list[str] = []

    for row in rows:
        predicted_price = row.get("predicted_price")
        actual_price = row.get("actual_price")
        predicted_return = row.get("predicted_return")
        actual_return = row.get("actual_return")
        as_of = row.get("as_of_date")
        if as_of is not None:
            dates.append(str(as_of)[:10])

        if predicted_price is not None and actual_price is not None:
            pred_p = float(predicted_price)
            act_p = float(actual_price)
            predicted_prices.append(pred_p)
            actual_prices.append(act_p)
            if act_p != 0:
                price_errors.append(abs(pred_p - act_p) / abs(act_p) * 100)
        if predicted_return is not None and actual_return is not None:
            return_errors.append(abs(float(predicted_return) - float(actual_return)))

    pred_arr = np.array(predicted_prices)
    act_arr = np.array(actual_prices)
    price_rmse = float(np.sqrt(np.mean((act_arr - pred_arr) ** 2))) if len(act_arr) else 0.0
    price_mae = float(np.mean(np.abs(act_arr - pred_arr))) if len(act_arr) else 0.0
    if len(act_arr) > 1:
        ss_res = float(np.sum((act_arr - pred_arr) ** 2))
        ss_tot = float(np.sum((act_arr - np.mean(act_arr)) ** 2))
        price_r2 = 1.0 - ss_res / ss_tot if ss_tot else 0.0
    else:
        price_r2 = 0.0

    return EvaluationReport(
        source=source,
        start_date=min(dates) if dates else None,
        end_date=max(dates) if dates else None,
        num_observations=len(rows),
        price_mape=float(np.mean(price_errors)) if price_errors else 0.0,
        price_rmse=price_rmse,
        price_mae=price_mae,
        price_r2=price_r2,
        return_mape=float(np.mean(return_errors)) if return_errors else 0.0,
        notes=["Portfolio Sharpe/volatility require walk-forward series; use backtest for those."],
    )


def build_smoke_report() -> EvaluationReport:
    """Deterministic report for CI / weekly smoke (no market I/O)."""
    return EvaluationReport(
        source="smoke",
        start_date="2024-01-01",
        end_date="2024-01-31",
        num_observations=5,
        price_mape=1.25,
        return_mape=0.012,
        portfolio_sharpe=1.0,
        portfolio_volatility=0.15,
        portfolio_max_drawdown=-0.05,
        cumulative_actual_return=0.02,
        cumulative_predicted_return=0.025,
        benchmarks={
            "equal_weight": 0.015,
            "buy_and_hold_equal_weight": 0.014,
            "spy": 0.01,
        },
        excess_returns={
            "equal_weight": 0.005,
            "buy_and_hold_equal_weight": 0.006,
            "spy": 0.01,
        },
        forecast_comparison={
            "prophet": 1.25,
            "naive_random_walk": 1.80,
            "drift_historical_mean": 1.55,
        },
        strategy_comparison={
            "prophet_mpt": {
                "cumulative_return": 0.02,
                "sharpe_ratio": 1.0,
                "excess_vs_equal_weight": 0.005,
                "win_rate_vs_equal_weight": 0.6,
            },
            "historical_mean_mpt": {
                "cumulative_return": 0.015,
                "sharpe_ratio": 0.8,
                "excess_vs_equal_weight": 0.0,
                "win_rate_vs_equal_weight": 0.5,
            },
            "equal_weight": {
                "cumulative_return": 0.015,
                "sharpe_ratio": 0.75,
                "excess_vs_equal_weight": 0.0,
                "win_rate_vs_equal_weight": 0.5,
            },
        },
        statistical_summary={
            "prophet_mape_improvement_vs_naive_pp": 0.55,
            "prophet_win_rate_vs_naive": 0.6,
            "prophet_win_rate_vs_drift": 0.55,
            "strategy_win_rate_vs_equal_weight": 0.6,
            "strategy_win_rate_vs_historical_mpt": 0.55,
            "excess_return_vs_historical_mpt": 0.005,
        },
        notes=["Synthetic smoke report; not live market performance."],
    )
