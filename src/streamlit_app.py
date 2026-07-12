"""Streamlit dashboard for Prophet-based portfolio forecasts."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `streamlit run src/streamlit_app.py` (script path) as well as `dashboard.py`.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ruff: noqa: E402
import json
from datetime import date, timedelta
from functools import lru_cache
from typing import cast

import altair as alt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.database import get_supabase_client
from src.efficient_frontier import EfficientFrontier
from src.evaluation import build_report_from_stored_outcomes
from src.mock_data import generate_mock_portfolio_data
from src.optimiser import calculate_mean_variance
from src.portfolio_analysis import (
    analyze_portfolio_risk,
    analyze_portfolio_sectors,
    expected_returns_from_date_df,
    load_returns_data,
    sector_analysis_to_records,
    weights_from_date_df,
)
from src.settings import SUPABASE_TABLE_NAME, ticker_color, ticker_color_map

# ============================================================================
# METRICS CALCULATION FUNCTIONS
# ============================================================================


def calculate_mape(actual: pd.Series, predicted: pd.Series) -> float:
    """Calculate Mean Absolute Percentage Error."""
    mask = actual != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def calculate_rmse(actual: pd.Series, predicted: pd.Series) -> float:
    """Calculate Root Mean Square Error."""
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))


def calculate_mae(actual: pd.Series, predicted: pd.Series) -> float:
    """Calculate Mean Absolute Error."""
    return float(np.mean(np.abs(actual - predicted)))


def calculate_metrics(perf_df: pd.DataFrame, ticker: str | None = None) -> dict[str, float]:
    """Calculate MAPE, RMSE, MAE for a ticker or entire portfolio."""
    if perf_df.empty:
        return {"mape": 0.0, "rmse": 0.0, "mae": 0.0, "count": 0}

    if ticker:
        data = perf_df[perf_df["ticker"] == ticker]
    else:
        data = perf_df

    if data.empty:
        return {"mape": 0.0, "rmse": 0.0, "mae": 0.0, "count": 0}

    return {
        "mape": calculate_mape(data["actual_price"], data["predicted_price"]),
        "rmse": calculate_rmse(data["actual_price"], data["predicted_price"]),
        "mae": calculate_mae(data["actual_price"], data["predicted_price"]),
        "count": len(data),
    }


def calculate_cumulative_returns(perf_df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Calculate cumulative returns from predictions."""
    data = perf_df[perf_df["ticker"] == ticker].sort_values("evaluation_date").copy()
    if data.empty:
        return pd.DataFrame()

    data["actual_return"] = data["actual_price"].pct_change()
    data["predicted_return"] = data["predicted_price"].pct_change()
    data["actual_cumulative"] = (1 + data["actual_return"]).cumprod() - 1
    data["predicted_cumulative"] = (1 + data["predicted_return"]).cumprod() - 1

    return data


def calculate_portfolio_metrics(perf_df: pd.DataFrame) -> dict[str, float]:
    """Calculate portfolio-level metrics using optimised weights when available."""
    if perf_df.empty:
        return {}

    if {"portfolio_weight", "actual_return", "predicted_return"}.issubset(perf_df.columns):
        daily_returns = perf_df.groupby("evaluation_date").apply(
            lambda x: pd.Series(
                {
                    "actual_return": float((x["portfolio_weight"] * x["actual_return"]).sum()),
                    "predicted_return": float(
                        (x["portfolio_weight"] * x["predicted_return"]).sum()
                    ),
                }
            ),
            include_groups=False,
        )
    else:
        daily_returns = perf_df.groupby("evaluation_date").apply(
            lambda x: pd.Series(
                {
                    "actual_return": x["actual_price"].pct_change().mean(),
                    "predicted_return": x["predicted_price"].pct_change().mean(),
                }
            ),
            include_groups=False,
        )

    metrics = {}
    if not daily_returns.empty:
        metrics["sharpe_actual"] = float(
            daily_returns["actual_return"].mean()
            / (daily_returns["actual_return"].std() + 1e-8)
            * np.sqrt(252)
        )
        metrics["sharpe_predicted"] = float(
            daily_returns["predicted_return"].mean()
            / (daily_returns["predicted_return"].std() + 1e-8)
            * np.sqrt(252)
        )
        metrics["volatility_actual"] = float(daily_returns["actual_return"].std() * np.sqrt(252))
        metrics["volatility_predicted"] = float(
            daily_returns["predicted_return"].std() * np.sqrt(252)
        )

    return metrics


@st.cache_data(ttl=300)
def _fetch_supabase_predictions() -> tuple[pd.DataFrame, str]:
    """Load predictions from Supabase, falling back to mock data when needed."""
    client = get_supabase_client()
    if client is None:
        return generate_mock_portfolio_data(), "mock"

    response = (
        client.table(SUPABASE_TABLE_NAME)
        .select("*")
        .order("as_of_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    data = getattr(response, "data", None)
    if not data:
        return generate_mock_portfolio_data(), "mock"

    df = pd.DataFrame(data)
    if "as_of_date" in df.columns:
        df["as_of_date"] = pd.to_datetime(df["as_of_date"]).dt.date
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"])

    df = df.sort_values(["as_of_date", "created_at"], ascending=[True, False])
    # One optimisation run per as_of_date: keep only the latest insert batch.
    # Per-ticker dedupe alone is wrong when a later run has fewer tickers (e.g. Yahoo
    # failures) — older same-day rows for missing tickers would still appear and
    # make portfolio weights sum to > 100%.
    df = _keep_latest_run_per_date(df)

    if "actual_prices_last_month" in df.columns:
        df["actual_prices_last_month"] = df["actual_prices_last_month"].apply(_parse_price_history)

    return df, "supabase"


def _keep_latest_run_per_date(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows from the most recent save batch for each as_of_date."""
    if df.empty:
        return df
    if "created_at" not in df.columns or "as_of_date" not in df.columns:
        return df.drop_duplicates(subset=["as_of_date", "ticker"], keep="first")

    parts: list[pd.DataFrame] = []
    for _, group in df.groupby("as_of_date", sort=False):
        latest = group["created_at"].max()
        # Rows from one insert share nearly the same created_at; older same-day
        # runs are excluded so weights still sum to ~1.0.
        batch = group[group["created_at"] >= latest - pd.Timedelta(minutes=2)].copy()
        batch = batch.sort_values("created_at", ascending=False).drop_duplicates(
            subset=["ticker"], keep="first"
        )
        parts.append(batch)

    if not parts:
        return df.iloc[0:0].copy()
    return pd.concat(parts, ignore_index=True)


def load_supabase_predictions() -> pd.DataFrame:
    """Return latest Supabase rows (one per ticker per date) or mock data if unavailable."""
    df, _source = _fetch_supabase_predictions()
    return df


def _parse_price_history(raw: object) -> list[float]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [float(value) for value in raw]
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if isinstance(decoded, list):
            return [float(value) for value in decoded]
    return []


def _latest_actual_price(row: pd.Series) -> float | None:
    if "actual_price" in row.index and pd.notna(row.get("actual_price")):
        return float(row["actual_price"])
    prices = row.get("actual_prices_last_month", [])
    # Ensure prices are parsed as a list
    if isinstance(prices, str):
        prices = _parse_price_history(prices)
    if prices:
        return float(prices[-1])
    return None


def build_price_history(row: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    prices = row.get("actual_prices_last_month", [])
    # Ensure prices are parsed as a list
    if isinstance(prices, str):
        prices = _parse_price_history(prices)
    if not prices:
        return None

    as_of_date: date = row["as_of_date"]
    n = len(prices)

    actual_index = pd.bdate_range(end=pd.to_datetime(as_of_date), periods=n)
    actual_df = pd.DataFrame({"date": actual_index, "price": prices})

    prediction_date = pd.bdate_range(
        start=pd.to_datetime(as_of_date) + pd.Timedelta(days=1),
        periods=1,
    )[0]
    predicted_df = pd.DataFrame({"date": [prediction_date], "price": [row["predicted_price"]]})

    return actual_df, predicted_df


def _scored_rows_from_df(df: pd.DataFrame) -> list[dict[str, object]]:
    """Rows with realised outcomes filled by score-outcomes."""
    if "actual_price" not in df.columns:
        return []
    scored = df[df["actual_price"].notna()].copy()
    return cast(list[dict[str, object]], scored.to_dict(orient="records"))


def _render_stored_evaluation_summary(df: pd.DataFrame) -> None:
    """Show unified evaluation metrics when Supabase rows are scored."""
    scored_rows = _scored_rows_from_df(df)
    if not scored_rows:
        return

    report = build_report_from_stored_outcomes(scored_rows, source="dashboard")
    st.subheader("Stored Outcome Evaluation")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scored predictions", report.num_observations)
    c2.metric("Price MAPE", f"{report.price_mape:.2f}%")
    c3.metric("Return MAPE", f"{report.return_mape:.4f}")
    if report.start_date and report.end_date:
        c4.metric("Period", f"{report.start_date} → {report.end_date}")
    if report.notes:
        st.caption(" · ".join(report.notes))


@lru_cache(maxsize=1)
def compute_prediction_performance(data_json: str) -> pd.DataFrame:
    """Compare past predictions against actual outcomes using successive days."""
    from io import StringIO

    try:
        df = pd.read_json(StringIO(data_json), orient="records", convert_dates=False)
    except ValueError:
        return pd.DataFrame()

    if df.empty:
        return df

    df["as_of_date"] = pd.to_datetime(df["as_of_date"]).dt.date
    if "actual_prices_last_month" in df.columns:
        df["actual_prices_last_month"] = df["actual_prices_last_month"].apply(_parse_price_history)
    df = df.sort_values(["ticker", "as_of_date"])

    records: list[dict[str, object]] = []
    scored_keys: set[tuple[str, date]] = set()

    if "actual_price" in df.columns:
        for _, row in df.iterrows():
            if pd.isna(row.get("actual_price")):
                continue
            ticker = str(row["ticker"])
            as_of = row["as_of_date"]
            scored_keys.add((ticker, as_of))
            eval_date = row.get("prediction_target_date") or as_of
            if isinstance(eval_date, str):
                eval_date = pd.to_datetime(eval_date).date()
            records.append(
                {
                    "ticker": ticker,
                    "prediction_date": as_of,
                    "evaluation_date": eval_date,
                    "predicted_price": float(row["predicted_price"]),
                    "actual_price": float(row["actual_price"]),
                    "error": float(row["actual_price"]) - float(row["predicted_price"]),
                    "portfolio_weight": float(row.get("portfolio_weight", 0.0)),
                    "predicted_return": float(row.get("predicted_return", 0.0)),
                }
            )

    for ticker, group in df.groupby("ticker"):
        group = group.reset_index(drop=True)
        for idx in range(len(group) - 1):
            current = group.loc[idx]
            if (ticker, current["as_of_date"]) in scored_keys:
                continue

            prices = current.get("actual_prices_last_month")
            if not prices:
                continue

            next_row = group.loc[idx + 1]
            actual_next_price = _latest_price_from_row(next_row)
            if actual_next_price is None:
                continue

            records.append(
                {
                    "ticker": ticker,
                    "prediction_date": current["as_of_date"],
                    "evaluation_date": next_row["as_of_date"],
                    "predicted_price": float(current["predicted_price"]),
                    "actual_price": actual_next_price,
                    "error": actual_next_price - float(current["predicted_price"]),
                    "portfolio_weight": float(current.get("portfolio_weight", 0.0)),
                    "predicted_return": float(current.get("predicted_return", 0.0)),
                }
            )

    perf_df = pd.DataFrame(records)
    if perf_df.empty:
        # Single-run fallback: compare latest prediction to last known actual price
        for ticker, group in df.groupby("ticker"):
            row = group.sort_values("as_of_date").iloc[-1]
            if (str(ticker), row["as_of_date"]) in scored_keys:
                continue
            prices = row.get("actual_prices_last_month")
            if isinstance(prices, str):
                prices = _parse_price_history(prices)
            if not prices:
                continue

            actual_price = float(prices[-1])
            predicted_price = float(row["predicted_price"])
            records.append(
                {
                    "ticker": ticker,
                    "prediction_date": row["as_of_date"],
                    "evaluation_date": row["as_of_date"],
                    "predicted_price": predicted_price,
                    "actual_price": actual_price,
                    "error": actual_price - predicted_price,
                    "portfolio_weight": float(row.get("portfolio_weight", 0.0)),
                    "predicted_return": float(row.get("predicted_return", 0.0)),
                }
            )
        perf_df = pd.DataFrame(records)
        if perf_df.empty:
            return perf_df

    perf_df["absolute_error"] = perf_df["error"].abs()
    perf_df["error_pct"] = perf_df["error"] / perf_df["predicted_price"]
    perf_df["actual_return"] = (perf_df["actual_price"] - perf_df["predicted_price"]) / perf_df[
        "predicted_price"
    ]
    return perf_df


def _latest_price_from_row(row: pd.Series) -> float | None:
    prices = row.get("actual_prices_last_month")
    if isinstance(prices, list) and prices:
        return float(prices[-1])
    return None


def pie_chart(weights_df: pd.DataFrame):
    chart_df = weights_df[["ticker", "portfolio_weight"]].copy()
    chart_df["portfolio_weight"] = pd.to_numeric(chart_df["portfolio_weight"], errors="coerce")
    chart_df = chart_df.dropna(subset=["portfolio_weight"])

    total_weight = chart_df["portfolio_weight"].sum()
    if total_weight <= 0:
        return None

    color_map = ticker_color_map(chart_df["ticker"].astype(str).tolist())
    fig = px.pie(
        chart_df,
        names="ticker",
        values="portfolio_weight",
        hole=0.3,
        color="ticker",
        color_discrete_map=color_map,
    )
    fig.update_traces(textinfo="label+percent", hovertemplate="%{label}: %{value:.2f}")
    fig.update_layout(showlegend=True, legend_title_text="Ticker", height=360)
    return fig


# ============================================================================
# NEW VISUALIZATION FUNCTIONS FOR PHASE 3
# ============================================================================


def create_error_heatmap(perf_df: pd.DataFrame) -> go.Figure | None:
    """Create heatmap of prediction errors by ticker and date."""
    if perf_df.empty:
        return None

    pivot_df = perf_df.pivot_table(
        index="ticker", columns="evaluation_date", values="error_pct", aggfunc="mean"
    )

    if pivot_df.empty:
        return None

    pivot_df = pivot_df * 100  # Convert to percentage

    fig = go.Figure(
        data=go.Heatmap(
            z=pivot_df.values,
            x=pivot_df.columns,
            y=pivot_df.index,
            colorscale="RdBu_r",
            zmid=0,
            hovertemplate="Ticker: %{y}<br>Date: %{x}<br>Error: %{z:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title="Prediction Error Heatmap by Ticker (%)",
        xaxis_title="Evaluation Date",
        yaxis_title="Ticker",
        height=400,
    )
    return fig


def create_correlation_matrix(perf_df: pd.DataFrame) -> go.Figure | None:
    """Create correlation matrix of prediction errors."""
    if perf_df.empty or len(perf_df["ticker"].unique()) < 2:
        return None

    error_by_ticker = perf_df.pivot_table(
        index="evaluation_date", columns="ticker", values="error_pct"
    )

    if error_by_ticker.empty or error_by_ticker.shape[1] < 2:
        return None

    corr_matrix = error_by_ticker.corr()

    fig = go.Figure(
        data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.index,
            colorscale="Viridis",
            zmid=0,
            zmin=-1,
            zmax=1,
            text=np.round(corr_matrix.values, 2),
            texttemplate="%{text}",
            textfont={"size": 10},
            hovertemplate="Ticker 1: %{y}<br>Ticker 2: %{x}<br>Correlation: %{z:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Prediction Error Correlation Matrix",
        height=500,
    )
    return fig


def create_returns_distribution(perf_df: pd.DataFrame, ticker: str) -> go.Figure | None:
    """Create distribution of prediction errors."""
    data = perf_df[perf_df["ticker"] == ticker].copy()
    if data.empty:
        return None

    data["error_pct"] = data["error_pct"] * 100

    colour = ticker_color(ticker)
    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=data["error_pct"],
            name="Error Distribution",
            nbinsx=20,
            marker=dict(color=colour, opacity=0.75),
            hovertemplate="Error Range: %{x:.1f}%<br>Count: %{y}<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"Prediction Error Distribution - {ticker}",
        xaxis_title="Error (%)",
        yaxis_title="Frequency",
        height=350,
        showlegend=False,
    )
    return fig


def create_cumulative_returns_chart(perf_df: pd.DataFrame, ticker: str) -> alt.Chart | None:
    """Create cumulative returns chart."""
    data = calculate_cumulative_returns(perf_df, ticker)
    if data.empty:
        return None

    # Prepare data for Altair
    long_df = pd.DataFrame(
        {
            "Date": list(data["evaluation_date"]) + list(data["evaluation_date"]),
            "Cumulative Return": list(data["actual_cumulative"].fillna(0))
            + list(data["predicted_cumulative"].fillna(0)),
            "Type": ["Actual"] * len(data) + ["Predicted"] * len(data),
        }
    )

    # Actual uses the ticker's shared colour; Predicted uses a contrasting grey
    ticker_hex = ticker_color(ticker)
    chart = (
        alt.Chart(long_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y(
                "Cumulative Return:Q", title="Cumulative Return (%)", scale=alt.Scale(zero=False)
            ),
            color=alt.Color(
                "Type:N",
                title="Type",
                scale=alt.Scale(domain=["Actual", "Predicted"], range=[ticker_hex, "#888888"]),
            ),
            tooltip=["Date:T", "Type:N", alt.Tooltip("Cumulative Return:Q", format=".2f")],
        )
    )

    return cast(alt.Chart, chart)


def create_weight_history_chart(df: pd.DataFrame) -> go.Figure | None:
    """Create portfolio weight history over time."""
    if df.empty or "as_of_date" not in df.columns:
        return None

    df_sorted = df.sort_values("as_of_date")

    fig = go.Figure()
    for ticker in sorted(df_sorted["ticker"].astype(str).unique()):
        ticker_data = df_sorted[df_sorted["ticker"] == ticker].sort_values("as_of_date")
        fig.add_trace(
            go.Scatter(
                x=ticker_data["as_of_date"],
                y=ticker_data["portfolio_weight"],
                name=ticker,
                mode="lines+markers",
                line=dict(color=ticker_color(ticker)),
                marker=dict(color=ticker_color(ticker)),
                hovertemplate="Date: %{x}<br>Weight: %{y:.2f}<extra></extra>",
            )
        )

    fig.update_layout(
        title="Portfolio Weight History",
        xaxis_title="Date",
        yaxis_title="Weight",
        height=400,
        hovermode="x unified",
    )
    return fig


def export_to_csv(perf_df: pd.DataFrame, date_df: pd.DataFrame) -> str:
    """Generate CSV export of analysis data."""
    output = []

    # Add summary statistics
    output.append("# PORTFOLIO FORECAST ANALYSIS")
    output.append(f"# Generated: {pd.Timestamp.now()}\n")

    # Export prediction performance
    output.append("PREDICTION PERFORMANCE")
    output.append(perf_df.to_csv(index=False))
    output.append("\n")

    # Export latest weights
    output.append("LATEST PORTFOLIO WEIGHTS")
    output.append(
        date_df[["ticker", "predicted_price", "predicted_return", "portfolio_weight"]].to_csv(
            index=False
        )
    )

    return "\n".join(output)


def _render_advanced_risk_sector_metrics(date_df: pd.DataFrame) -> None:
    """Compute and display VaR/CVaR and sector exposure for the selected date."""
    cache_key = f"advanced_metrics_{date_df['as_of_date'].iloc[0]}"
    if cache_key in st.session_state:
        cached = st.session_state[cache_key]
        risk_metrics = cached["risk_metrics"]
        concentration = cached["concentration"]
        sector_analysis = cached["sector_analysis"]
    else:
        try:
            weights = weights_from_date_df(date_df)
            expected_returns = expected_returns_from_date_df(date_df)
            with st.spinner("Loading historical returns for risk analysis..."):
                returns_data = load_returns_data(list(weights.keys()))
            risk_metrics, concentration = analyze_portfolio_risk(weights, returns_data)
            sector_analysis = analyze_portfolio_sectors(
                weights,
                returns_data=returns_data,
                expected_returns=expected_returns,
            )
            st.session_state[cache_key] = {
                "risk_metrics": risk_metrics,
                "concentration": concentration,
                "sector_analysis": sector_analysis,
            }
        except Exception as exc:
            st.warning(f"Advanced risk metrics unavailable: {exc}")
            return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VaR 95%", f"{risk_metrics.var_95:.4f}")
    c2.metric("CVaR 95%", f"{risk_metrics.cvar_95:.4f}")
    c3.metric("Sharpe (hist.)", f"{risk_metrics.sharpe_ratio:.2f}")
    c4.metric("Max drawdown", f"{risk_metrics.max_drawdown:.2%}")

    c5, c6, c7 = st.columns(3)
    c5.metric("HHI (weights)", f"{concentration['herfindahl_index']:.4f}")
    c6.metric("Sector concentration", sector_analysis.sector_concentration_level)
    c7.metric("Effective sectors", f"{sector_analysis.effective_number_of_sectors:.1f}")

    sector_df = pd.DataFrame(sector_analysis_to_records(sector_analysis))
    if not sector_df.empty:
        sector_df["allocation_pct"] = sector_df["allocation"] * 100
        st.dataframe(
            sector_df[
                [
                    "sector",
                    "allocation_pct",
                    "holdings",
                    "volatility",
                    "expected_return",
                ]
            ].rename(
                columns={
                    "allocation_pct": "Allocation (%)",
                    "expected_return": "Expected return",
                }
            ),
            hide_index=True,
            use_container_width=True,
        )


def run_dashboard() -> None:
    """Run the enhanced dashboard with tabbed interface."""
    st.set_page_config(page_title="Portfolio Forecast Dashboard", layout="wide")
    st.title("📊 Portfolio Forecast Dashboard")
    st.caption("Advanced portfolio analysis with predictions, metrics, and visualizations.")

    # Load data
    df, data_source = _fetch_supabase_predictions()
    if df.empty:
        st.error("❌ No prediction data available. Unable to load mock data either.")
        return

    if data_source == "mock":
        st.info("💡 Showing mock data (Supabase not configured or empty).")
    else:
        st.success("✅ Loaded live optimisation results from Supabase.")

    # Create two columns: date selector and export button
    col1, col2 = st.columns([3, 1])

    with col1:
        available_dates = sorted(df["as_of_date"].unique(), reverse=True)
        selected_date = st.selectbox(
            "Select as-of date",
            options=available_dates,
            format_func=lambda d: d.strftime("%Y-%m-%d"),
        )

    with col2:
        date_df = df[df["as_of_date"] == selected_date].copy().sort_values("ticker")
        perf_df = compute_prediction_performance(df.to_json(orient="records", date_format="iso"))

        csv_data = export_to_csv(perf_df, date_df)
        st.download_button(
            label="📥 Export CSV",
            data=csv_data,
            file_name=f"portfolio_analysis_{selected_date}.csv",
            mime="text/csv",
        )

    # Create tabbed interface
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📈 Overview",
            "🎯 Prediction Accuracy",
            "📊 Advanced Analytics",
            "⚙️ Performance Metrics",
            "🎯 Efficient Frontier",
        ]
    )

    # ========================================================================
    # TAB 1: OVERVIEW
    # ========================================================================
    with tab1:
        st.subheader("Portfolio Allocation & Predictions")

        col1, col2 = st.columns([1.5, 2])

        with col1:
            pie = pie_chart(date_df)
            if pie is None:
                st.info("Weights are zero or missing for this date.")
            else:
                st.plotly_chart(pie, use_container_width=True)
                weight_sum = float(
                    pd.to_numeric(date_df["portfolio_weight"], errors="coerce").sum()
                )
                st.caption(
                    f"Current portfolio allocation "
                    f"(weights sum to {weight_sum * 100:.1f}% · {len(date_df)} tickers)"
                )

        with col2:
            summary_table = date_df[
                ["ticker", "predicted_price", "predicted_return", "portfolio_weight"]
            ].copy()
            summary_table["predicted_return_pct"] = summary_table["predicted_return"] * 100
            summary_table["portfolio_weight_pct"] = summary_table["portfolio_weight"] * 100

            summary_table = summary_table.rename(
                columns={
                    "ticker": "Ticker",
                    "predicted_price": "Predicted Price",
                    "predicted_return_pct": "Return (%)",
                    "portfolio_weight_pct": "Weight (%)",
                }
            )
            st.dataframe(
                summary_table[["Ticker", "Predicted Price", "Return (%)", "Weight (%)"]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Predicted Price": st.column_config.NumberColumn(format="$%.2f"),
                    "Return (%)": st.column_config.NumberColumn(format="%.2f%%"),
                    "Weight (%)": st.column_config.NumberColumn(format="%.2f%%"),
                },
            )

        # Date range selector for weight history
        st.subheader("Weight History")
        date_range = st.slider(
            "Select date range for weight history",
            min_value=min(df["as_of_date"]),
            max_value=max(df["as_of_date"]),
            value=(max(df["as_of_date"]) - timedelta(days=30), max(df["as_of_date"])),
            format="YYYY-MM-DD",
        )

        weight_df = df[
            (df["as_of_date"] >= date_range[0]) & (df["as_of_date"] <= date_range[1])
        ].copy()
        weight_chart = create_weight_history_chart(weight_df)
        if weight_chart:
            st.plotly_chart(weight_chart, use_container_width=True)
        else:
            st.info("No weight history available for selected date range.")

    # ========================================================================
    # TAB 2: PREDICTION ACCURACY
    # ========================================================================
    with tab2:
        _render_stored_evaluation_summary(df)

        tickers = date_df["ticker"].tolist()
        selected_ticker = st.selectbox(
            "Select ticker for detail analysis", options=tickers, index=0
        )

        ticker_row = date_df.set_index("ticker").loc[selected_ticker]
        latest_actual = _latest_actual_price(ticker_row)

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Latest Actual Price", f"${latest_actual:.2f}" if latest_actual is not None else "—"
            )
        with col2:
            st.metric("Predicted Price", f"${ticker_row['predicted_price']:.2f}")
        with col3:
            st.metric("Predicted Return", f"{ticker_row['predicted_return']*100:.2f}%")
        with col4:
            metrics = calculate_metrics(perf_df, selected_ticker)
            if metrics["count"] > 0:
                st.metric("MAPE (%)", f"{metrics['mape']:.2f}%")

        # Price trend chart
        st.subheader(f"Price Trend · {selected_ticker}")
        ticker_perf_for_trend = perf_df[perf_df["ticker"] == selected_ticker].copy()

        if ticker_perf_for_trend.empty:
            st.info("No historical prediction data available for this ticker yet.")
        else:
            min_price = float(
                ticker_perf_for_trend[["actual_price", "predicted_price"]].min().min()
            )
            max_price = float(
                ticker_perf_for_trend[["actual_price", "predicted_price"]].max().max()
            )
            default_min = min_price * 0.8
            default_max = max_price * 1.2
            slider_min = float(round(default_min * 0.9, 2))
            slider_max = float(round(default_max * 1.1, 2))

            y_min, y_max = st.slider(
                "Price range (y-axis)",
                min_value=slider_min,
                max_value=slider_max,
                value=(float(round(default_min, 2)), float(round(default_max, 2))),
                key=f"price_slider_{selected_ticker}",
            )

            long_df_trend = ticker_perf_for_trend.melt(
                id_vars=["evaluation_date", "prediction_date"],
                value_vars=["actual_price", "predicted_price"],
                var_name="series",
                value_name="price",
            )
            ticker_hex = ticker_color(selected_ticker)
            line_chart_trend = (
                alt.Chart(long_df_trend)
                .mark_line(point=True)
                .encode(
                    x=alt.X("evaluation_date:T", title="Evaluation Date"),
                    y=alt.Y("price:Q", title="Price (USD)", scale=alt.Scale(domain=[y_min, y_max])),
                    color=alt.Color(
                        "series:N",
                        title="Series",
                        scale=alt.Scale(
                            domain=["actual_price", "predicted_price"],
                            range=[ticker_hex, "#888888"],
                        ),
                        legend=alt.Legend(
                            labelExpr="datum.value == 'actual_price' ? 'Actual' : 'Predicted'"
                        ),
                    ),
                    tooltip=[
                        alt.Tooltip("prediction_date:T", title="Prediction Date"),
                        alt.Tooltip("evaluation_date:T", title="Evaluation Date"),
                        alt.Tooltip("series:N", title="Series"),
                        alt.Tooltip("price:Q", title="Price", format=".2f"),
                    ],
                )
            )
            st.altair_chart(line_chart_trend, use_container_width=True)

        # Cumulative returns
        st.subheader(f"Cumulative Returns · {selected_ticker}")
        cumulative_chart = create_cumulative_returns_chart(perf_df, selected_ticker)
        if cumulative_chart:
            st.altair_chart(cumulative_chart, use_container_width=True)
        else:
            st.info("Not enough data to calculate cumulative returns.")

        # Error distribution
        st.subheader(f"Error Distribution · {selected_ticker}")
        error_dist = create_returns_distribution(perf_df, selected_ticker)
        if error_dist:
            st.plotly_chart(error_dist, use_container_width=True)
        else:
            st.info("No error data available.")

        # Detailed performance table
        st.subheader("Detailed Performance Data")
        if perf_df.empty:
            st.info("Not enough historical runs to evaluate predictions yet.")
        else:
            ticker_perf = perf_df[perf_df["ticker"] == selected_ticker].copy()
            if ticker_perf.empty:
                st.info("No historical prediction data for this ticker yet.")
            else:
                ticker_perf["error_pct"] = ticker_perf["error_pct"] * 100
                ticker_perf_display = ticker_perf.rename(
                    columns={
                        "prediction_date": "Prediction Date",
                        "evaluation_date": "Evaluation Date",
                        "predicted_price": "Predicted Price",
                        "actual_price": "Actual Price",
                        "error": "Error",
                        "absolute_error": "Abs Error",
                        "error_pct": "Error (%)",
                    }
                )
                st.dataframe(
                    ticker_perf_display[
                        [
                            "Prediction Date",
                            "Evaluation Date",
                            "Predicted Price",
                            "Actual Price",
                            "Error",
                            "Abs Error",
                            "Error (%)",
                        ]
                    ],
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Predicted Price": st.column_config.NumberColumn(format="$%.2f"),
                        "Actual Price": st.column_config.NumberColumn(format="$%.2f"),
                        "Error": st.column_config.NumberColumn(format="$%.2f"),
                        "Abs Error": st.column_config.NumberColumn(format="$%.2f"),
                        "Error (%)": st.column_config.NumberColumn(format="%.2f%%"),
                    },
                )

    # ========================================================================
    # TAB 3: ADVANCED ANALYTICS
    # ========================================================================
    with tab3:
        if perf_df.empty:
            st.info("Not enough data for advanced analytics. Run the pipeline multiple times.")
        else:
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Prediction Error Heatmap")
                heatmap = create_error_heatmap(perf_df)
                if heatmap:
                    st.plotly_chart(heatmap, use_container_width=True)
                else:
                    st.info("Not enough data for heatmap.")

            with col2:
                st.subheader("Error Correlation Matrix")
                corr_chart = create_correlation_matrix(perf_df)
                if corr_chart:
                    st.plotly_chart(corr_chart, use_container_width=True)
                else:
                    st.info("Not enough tickers or data for correlation analysis.")

    # ========================================================================
    # TAB 4: PERFORMANCE METRICS
    # ========================================================================
    with tab4:
        st.subheader("Portfolio Performance Metrics")

        if perf_df.empty:
            st.info("Not enough data to calculate metrics.")
        else:
            # Overall portfolio metrics
            portfolio_metrics = calculate_portfolio_metrics(perf_df)

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                overall_metrics = calculate_metrics(perf_df)
                st.metric("Overall MAPE", f"{overall_metrics['mape']:.2f}%")

            with col2:
                st.metric("Overall RMSE", f"${overall_metrics['rmse']:.2f}")

            with col3:
                st.metric("Overall MAE", f"${overall_metrics['mae']:.2f}")

            with col4:
                st.metric("Predictions Made", f"{overall_metrics['count']}")

            # Per-ticker metrics
            st.subheader("Per-Ticker Metrics")

            metrics_data = []
            for ticker in sorted(perf_df["ticker"].unique()):
                ticker_metrics = calculate_metrics(perf_df, ticker)
                metrics_data.append(
                    {
                        "Ticker": ticker,
                        "MAPE (%)": ticker_metrics["mape"],
                        "RMSE": ticker_metrics["rmse"],
                        "MAE": ticker_metrics["mae"],
                        "Predictions": ticker_metrics["count"],
                    }
                )

            metrics_df = pd.DataFrame(metrics_data)
            st.dataframe(
                metrics_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "MAPE (%)": st.column_config.NumberColumn(format="%.2f%%"),
                    "RMSE": st.column_config.NumberColumn(format="$%.2f"),
                    "MAE": st.column_config.NumberColumn(format="$%.2f"),
                },
            )

            # Sharpe ratio and volatility if available
            if portfolio_metrics:
                st.subheader("Risk Metrics")

                col1, col2, col3, col4 = st.columns(4)

                if "sharpe_actual" in portfolio_metrics:
                    with col1:
                        st.metric(
                            "Sharpe Ratio (Actual)", f"{portfolio_metrics['sharpe_actual']:.2f}"
                        )

                if "sharpe_predicted" in portfolio_metrics:
                    with col2:
                        st.metric(
                            "Sharpe Ratio (Predicted)",
                            f"{portfolio_metrics['sharpe_predicted']:.2f}",
                        )

                if "volatility_actual" in portfolio_metrics:
                    with col3:
                        st.metric(
                            "Volatility (Actual)", f"{portfolio_metrics['volatility_actual']:.2f}"
                        )

                if "volatility_predicted" in portfolio_metrics:
                    with col4:
                        st.metric(
                            "Volatility (Predicted)",
                            f"{portfolio_metrics['volatility_predicted']:.2f}",
                        )

            st.subheader("VaR, CVaR & Sector Exposure")
            st.caption(
                "Uses historical returns and the selected date's portfolio weights "
                "(via risk_analytics.py and sector_analysis.py)."
            )
            _render_advanced_risk_sector_metrics(date_df)

    # ========================================================================
    # TAB 5: EFFICIENT FRONTIER
    # ========================================================================
    with tab5:
        st.subheader("Efficient Frontier Analysis")
        st.markdown(
            """Explore the risk-return tradeoff across different portfolio allocations.
            The efficient frontier shows optimal portfolios for different risk preferences."""
        )

        # Get expected returns and covariance from latest data
        try:
            weights = weights_from_date_df(date_df)
            expected_returns = expected_returns_from_date_df(date_df)

            if len(weights) < 2:
                st.warning("Need at least 2 assets to generate frontier.")
            else:
                with st.spinner("Loading historical returns for efficient frontier..."):
                    returns_data = load_returns_data(list(weights.keys()))

                mean_returns, cov_matrix = calculate_mean_variance(
                    returns_data,
                    expected_returns=expected_returns,
                )

                num_points = st.slider(
                    "Number of frontier points", min_value=10, max_value=100, value=50, step=10
                )

                frontier_result = EfficientFrontier.generate_frontier(
                    mean_returns,
                    cov_matrix,
                    num_points=num_points,
                )

                st.subheader("Risk vs Return")

                fig = EfficientFrontier.plot_frontier(frontier_result, weights)
                st.plotly_chart(fig, use_container_width=True)

                min_var = frontier_result.min_variance_portfolio
                max_sharpe = frontier_result.max_sharpe_portfolio

                st.subheader("Portfolio Allocations")

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Minimum Variance Portfolio**")
                    st.metric("Volatility", f"{min_var.volatility:.4f}")
                    st.metric("Expected Return", f"{min_var.expected_return:.4f}")
                    st.metric("Sharpe Ratio", f"{min_var.sharpe_ratio:.4f}")

                    st.markdown("**Weights:**")
                    min_var_weights_df = pd.DataFrame(
                        list(min_var.weights.items()), columns=["Ticker", "Weight"]
                    )
                    min_var_weights_df["Weight"] = min_var_weights_df["Weight"] * 100
                    min_var_weights_df = min_var_weights_df.sort_values("Weight", ascending=False)
                    st.dataframe(
                        min_var_weights_df,
                        hide_index=True,
                        column_config={"Weight": st.column_config.NumberColumn(format="%.2f%%")},
                    )

                with col2:
                    st.markdown("**Maximum Sharpe Ratio Portfolio**")
                    st.metric("Volatility", f"{max_sharpe.volatility:.4f}")
                    st.metric("Expected Return", f"{max_sharpe.expected_return:.4f}")
                    st.metric("Sharpe Ratio", f"{max_sharpe.sharpe_ratio:.4f}")

                    st.markdown("**Weights:**")
                    max_sharpe_weights_df = pd.DataFrame(
                        list(max_sharpe.weights.items()), columns=["Ticker", "Weight"]
                    )
                    max_sharpe_weights_df["Weight"] = max_sharpe_weights_df["Weight"] * 100
                    max_sharpe_weights_df = max_sharpe_weights_df.sort_values(
                        "Weight", ascending=False
                    )
                    st.dataframe(
                        max_sharpe_weights_df,
                        hide_index=True,
                        column_config={"Weight": st.column_config.NumberColumn(format="%.2f%%")},
                    )

        except Exception as e:
            st.error(f"Error generating frontier: {str(e)}")
            st.info("Ensure portfolio has sufficient data and valid returns.")


def main() -> None:
    run_dashboard()


if __name__ == "__main__":
    main()
