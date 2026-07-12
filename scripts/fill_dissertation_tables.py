#!/usr/bin/env python3
"""Fill Table 5.11 placeholders in DISSERTATION_RESULTS_AND_EVALUATION.txt from JSON."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISSERTATION = ROOT / "DISSERTATION_RESULTS_AND_EVALUATION.txt"
DEFAULT_JSON = ROOT / "comparative_evaluation.json"


def _pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def _num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def fill_table(report: dict) -> str:
    benchmarks = report.get("benchmarks") or {}
    excess = report.get("excess_returns") or {}
    forecast = report.get("forecast_comparison") or {}
    strategy = report.get("strategy_comparison") or {}

    prophet_mape = forecast.get("prophet")
    naive_mape = forecast.get("naive_random_walk")
    mape_vs_naive = (
        f"Prophet {_num(prophet_mape)}% vs naive {_num(naive_mape)}%"
        if prophet_mape is not None and naive_mape is not None
        else "[see JSON output]"
    )

    prophet_mpt = strategy.get("prophet_mpt") or {}
    hist_mpt = strategy.get("historical_mean_mpt") or {}
    strategy_line = (
        f"Prophet-MPT {_pct(prophet_mpt.get('cumulative_return'))} / "
        f"Sharpe {_num(prophet_mpt.get('sharpe_ratio'))}; "
        f"hist-μ {_pct(hist_mpt.get('cumulative_return'))} / "
        f"Sharpe {_num(hist_mpt.get('sharpe_ratio'))}"
        if prophet_mpt or hist_mpt
        else "[see JSON output]"
    )

    rows = {
        "Status at time of writing": "COMPLETE",
        "Avg. price MAPE (%)": f"{_num(report.get('price_mape'))}%",
        "Avg. return MAPE": _num(report.get("return_mape"), 4),
        "Portfolio Sharpe ratio": _num(report.get("portfolio_sharpe")),
        "Portfolio volatility (annualised)": _num(report.get("portfolio_volatility"), 4),
        "Maximum drawdown": _pct(report.get("portfolio_max_drawdown")),
        "Cumulative actual return": _pct(report.get("cumulative_actual_return")),
        "Cumulative predicted return": _pct(report.get("cumulative_predicted_return")),
        "Equal-weight benchmark return": _pct(benchmarks.get("equal_weight")),
        "SPY buy-and-hold return": _pct(benchmarks.get("spy")),
        "Excess return vs equal-weight": _pct(excess.get("equal_weight")),
        "Excess return vs SPY": _pct(excess.get("spy")),
        "Prophet MAPE vs naive random walk": mape_vs_naive,
        "Prophet-MPT vs historical-μ MPT": strategy_line,
    }
    return rows


def apply_rows(text: str, rows: dict[str, str]) -> str:
    for metric, value in rows.items():
        # Match table rows like: | Metric ... | old value | notes |
        pattern = rf"(\| {re.escape(metric)}\s+\|)([^|]*)(\|)"
        replacement = rf"\1 {value:<18} \3"
        text, n = re.subn(pattern, replacement, text, count=1)
        if n == 0:
            print(f"warning: could not find row for {metric!r}", file=sys.stderr)
    return text


def main() -> int:
    json_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_JSON
    if not json_path.exists():
        print(f"missing report: {json_path}", file=sys.stderr)
        return 1

    report = json.loads(json_path.read_text())
    rows = fill_table(report)
    text = DISSERTATION.read_text()
    updated = apply_rows(text, rows)

    # Fix status note date
    updated = updated.replace("Run 11 Jul 2026", "Run 11 Jul 2026 (complete)")
    updated = updated.replace(
        "NOTE: Aggregate walk-forward metrics are written to comparative_evaluation.json\n"
        "and evaluation_report.json after the compare/backtest run completes. Replace\n"
        "the [see JSON output] placeholders below with printed values from that file.",
        "NOTE: Table 5.11 values below were filled from comparative_evaluation.json\n"
        f"({json_path.name}). Observations: {report.get('num_observations', 'n/a')}.",
    )

    DISSERTATION.write_text(updated)
    print(f"Updated {DISSERTATION.name} from {json_path.name}")
    for metric, value in rows.items():
        print(f"  {metric}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
