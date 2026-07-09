"""Unified evaluation report for forecast accuracy, portfolio risk, and benchmarks."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.backtesting import BacktestSummary


@dataclass
class EvaluationReport:
    """Standard metrics used by CLI, CI smoke tests, and production scoring."""

    source: str
    start_date: str | None = None
    end_date: str | None = None
    num_observations: int = 0
    price_mape: float = 0.0
    return_mape: float = 0.0
    portfolio_sharpe: float = 0.0
    portfolio_volatility: float = 0.0
    portfolio_max_drawdown: float = 0.0
    cumulative_actual_return: float = 0.0
    cumulative_predicted_return: float = 0.0
    benchmarks: dict[str, float | None] = field(default_factory=dict)
    excess_returns: dict[str, float | None] = field(default_factory=dict)
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
        for note in self.notes:
            lines.append(f"- Note: {note}")
        return "\n".join(lines)

    def write_json(self, path: str | Path) -> Path:
        """Write report JSON to disk."""
        output = Path(path)
        output.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return output


def build_report_from_backtest(
    summary: BacktestSummary, source: str = "backtest"
) -> EvaluationReport:
    """Build a unified report from an existing BacktestSummary."""
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
            if act_p != 0:
                price_errors.append(abs(pred_p - act_p) / abs(act_p) * 100)
        if predicted_return is not None and actual_return is not None:
            return_errors.append(abs(float(predicted_return) - float(actual_return)))

    return EvaluationReport(
        source=source,
        start_date=min(dates) if dates else None,
        end_date=max(dates) if dates else None,
        num_observations=len(rows),
        price_mape=float(np.mean(price_errors)) if price_errors else 0.0,
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
        notes=["Synthetic smoke report; not live market performance."],
    )
