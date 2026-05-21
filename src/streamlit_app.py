"""Streamlit dashboard for Prophet-based portfolio forecasts."""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache

import altair as alt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.database import get_supabase_client
from src.efficient_frontier import EfficientFrontier
from src.settings import SUPABASE_TABLE_NAME

st.set_page_config(page_title="Portfolio Forecast Dashboard", layout="wide")


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
    """Calculate portfolio-level metrics."""
    if perf_df.empty:
        return {}
    
    # Group by evaluation date and sum returns
    daily_returns = perf_df.groupby("evaluation_date").apply(
        lambda x: pd.Series({
            "actual_return": x["actual_price"].pct_change().mean(),
            "predicted_return": x["predicted_price"].pct_change().mean(),
        })
    )
    
    metrics = {}
    if not daily_returns.empty:
        metrics["sharpe_actual"] = float(
            daily_returns["actual_return"].mean() / (daily_returns["actual_return"].std() + 1e-8) * np.sqrt(252)
        )
        metrics["sharpe_predicted"] = float(
            daily_returns["predicted_return"].mean() / (daily_returns["predicted_return"].std() + 1e-8) * np.sqrt(252)
        )
        metrics["volatility_actual"] = float(daily_returns["actual_return"].std() * np.sqrt(252))
        metrics["volatility_predicted"] = float(daily_returns["predicted_return"].std() * np.sqrt(252))
    
    return metrics


@st.cache_data(ttl=300)
def load_supabase_predictions() -> pd.DataFrame:
    """Return latest Supabase rows (one per ticker per date)."""
    client = get_supabase_client()
    if client is None:
        return pd.DataFrame()

    response = (
        client.table(SUPABASE_TABLE_NAME)
        .select("*")
        .order("as_of_date", desc=True)
        .order("created_at", desc=True)
        .execute()
    )
    data = getattr(response, "data", None)
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if "as_of_date" in df.columns:
        df["as_of_date"] = pd.to_datetime(df["as_of_date"]).dt.date
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"])

    df = df.sort_values(["as_of_date", "created_at"], ascending=[True, False])
    df = df.drop_duplicates(subset=["as_of_date", "ticker"], keep="first")

    if "actual_prices_last_month" in df.columns:
        df["actual_prices_last_month"] = df["actual_prices_last_month"].apply(_parse_price_history)

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
    prices = row.get("actual_prices_last_month", [])
    if prices:
        return float(prices[-1])
    return None


def build_price_history(row: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    prices = row.get("actual_prices_last_month", [])
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


@lru_cache(maxsize=1)
def compute_prediction_performance(data_json: str) -> pd.DataFrame:
    """Compare past predictions against actual outcomes using successive days."""
    df = pd.read_json(data_json, orient="records", convert_dates=False)
    if df.empty:
        return df

    df["as_of_date"] = pd.to_datetime(df["as_of_date"]).dt.date
    if "actual_prices_last_month" in df.columns:
        df["actual_prices_last_month"] = df["actual_prices_last_month"].apply(_parse_price_history)
    df = df.sort_values(["ticker", "as_of_date"])

    records: list[dict[str, object]] = []

    for ticker, group in df.groupby("ticker"):
        group = group.reset_index(drop=True)
        for idx in range(len(group) - 1):
            current = group.loc[idx]

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
                }
            )

    perf_df = pd.DataFrame(records)
    if perf_df.empty:
        return perf_df

    perf_df["absolute_error"] = perf_df["error"].abs()
    perf_df["error_pct"] = perf_df["error"] / perf_df["predicted_price"]
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

    fig = px.pie(
        chart_df,
        names="ticker",
        values="portfolio_weight",
        hole=0.3,
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
        index="ticker",
        columns="evaluation_date",
        values="error_pct",
        aggfunc="mean"
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
            hovertemplate="Ticker: %{y}<br>Date: %{x}<br>Error: %{z:.2f}%<extra></extra>"
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
        index="evaluation_date",
        columns="ticker",
        values="error_pct"
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
            hovertemplate="Ticker 1: %{y}<br>Ticker 2: %{x}<br>Correlation: %{z:.2f}<extra></extra>"
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
    
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=data["error_pct"],
        name="Error Distribution",
        nbinsx=20,
        marker=dict(color="rgba(31, 119, 180, 0.7)"),
        hovertemplate="Error Range: %{x:.1f}%<br>Count: %{y}<extra></extra>"
    ))
    
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
    long_df = pd.DataFrame({
        "Date": list(data["evaluation_date"]) + list(data["evaluation_date"]),
        "Cumulative Return": list(data["actual_cumulative"].fillna(0)) + list(data["predicted_cumulative"].fillna(0)),
        "Type": ["Actual"] * len(data) + ["Predicted"] * len(data),
    })
    
    chart = (
        alt.Chart(long_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("Date:T", title="Date"),
            y=alt.Y("Cumulative Return:Q", title="Cumulative Return (%)", scale=alt.Scale(zero=False)),
            color=alt.Color("Type:N", title="Type", scale=alt.Scale(domain=["Actual", "Predicted"], range=["#1f77b4", "#ff7f0e"])),
            tooltip=["Date:T", "Type:N", alt.Tooltip("Cumulative Return:Q", format=".2f")]
        )
    )
    
    return chart


def create_weight_history_chart(df: pd.DataFrame) -> go.Figure | None:
    """Create portfolio weight history over time."""
    if df.empty or "as_of_date" not in df.columns:
        return None
    
    df_sorted = df.sort_values("as_of_date")
    
    fig = go.Figure()
    for ticker in df_sorted["ticker"].unique():
        ticker_data = df_sorted[df_sorted["ticker"] == ticker].sort_values("as_of_date")
        fig.add_trace(go.Scatter(
            x=ticker_data["as_of_date"],
            y=ticker_data["portfolio_weight"],
            name=ticker,
            mode="lines+markers",
            hovertemplate="Date: %{x}<br>Weight: %{y:.2f}<extra></extra>"
        ))
    
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
    output.append(date_df[["ticker", "predicted_price", "predicted_return", "portfolio_weight"]].to_csv(index=False))
    
    return "\n".join(output)


def run_dashboard() -> None:
    """Run the enhanced dashboard with tabbed interface."""
    st.title("📊 Portfolio Forecast Dashboard")
    st.caption(
        "Advanced portfolio analysis with predictions, metrics, and visualizations."
    )

    # Load data
    df = load_supabase_predictions()
    if df.empty:
        st.info("No prediction data available. Run the optimisation pipeline to populate Supabase.")
        return

    # Create two columns: date selector and export button
    col1, col2 = st.columns([3, 1])
    
    with col1:
        available_dates = sorted(df["as_of_date"].unique(), reverse=True)
        selected_date = st.selectbox(
            "Select as-of date", 
            options=available_dates, 
            format_func=lambda d: d.strftime("%Y-%m-%d")
        )

    with col2:
        date_df = df[df["as_of_date"] == selected_date].copy().sort_values("ticker")
        perf_df = compute_prediction_performance(df.to_json(orient="records", date_format="iso"))
        
        csv_data = export_to_csv(perf_df, date_df)
        st.download_button(
            label="📥 Export CSV",
            data=csv_data,
            file_name=f"portfolio_analysis_{selected_date}.csv",
            mime="text/csv"
        )

    # Create tabbed interface
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📈 Overview",
        "🎯 Prediction Accuracy",
        "📊 Advanced Analytics",
        "⚙️ Performance Metrics",
        "🎯 Efficient Frontier"
    ])

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
                st.caption("Current portfolio allocation")
        
        with col2:
            summary_table = date_df[["ticker", "predicted_price", "predicted_return", "portfolio_weight"]].copy()
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
            format="YYYY-MM-DD"
        )
        
        weight_df = df[(df["as_of_date"] >= date_range[0]) & (df["as_of_date"] <= date_range[1])].copy()
        weight_chart = create_weight_history_chart(weight_df)
        if weight_chart:
            st.plotly_chart(weight_chart, use_container_width=True)
        else:
            st.info("No weight history available for selected date range.")

    # ========================================================================
    # TAB 2: PREDICTION ACCURACY
    # ========================================================================
    with tab2:
        tickers = date_df["ticker"].tolist()
        selected_ticker = st.selectbox(
            "Select ticker for detail analysis",
            options=tickers,
            index=0
        )

        ticker_row = date_df.set_index("ticker").loc[selected_ticker]
        latest_actual = _latest_actual_price(ticker_row)

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Latest Actual Price",
                f"${latest_actual:.2f}" if latest_actual is not None else "—"
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
            min_price = float(ticker_perf_for_trend[["actual_price", "predicted_price"]].min().min())
            max_price = float(ticker_perf_for_trend[["actual_price", "predicted_price"]].max().max())
            default_min = min_price * 0.8
            default_max = max_price * 1.2
            slider_min = float(round(default_min * 0.9, 2))
            slider_max = float(round(default_max * 1.1, 2))

            y_min, y_max = st.slider(
                "Price range (y-axis)",
                min_value=slider_min,
                max_value=slider_max,
                value=(float(round(default_min, 2)), float(round(default_max, 2))),
                key=f"price_slider_{selected_ticker}"
            )

            long_df_trend = ticker_perf_for_trend.melt(
                id_vars=["evaluation_date", "prediction_date"],
                value_vars=["actual_price", "predicted_price"],
                var_name="series",
                value_name="price",
            )
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
                            range=["#1f77b4", "#ff7f0e"],
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
                metrics_data.append({
                    "Ticker": ticker,
                    "MAPE (%)": ticker_metrics["mape"],
                    "RMSE": ticker_metrics["rmse"],
                    "MAE": ticker_metrics["mae"],
                    "Predictions": ticker_metrics["count"],
                })
            
            metrics_df = pd.DataFrame(metrics_data)
            st.dataframe(
                metrics_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "MAPE (%)": st.column_config.NumberColumn(format="%.2f%%"),
                    "RMSE": st.column_config.NumberColumn(format="$%.2f"),
                    "MAE": st.column_config.NumberColumn(format="$%.2f"),
                }
            )
            
            # Sharpe ratio and volatility if available
            if portfolio_metrics:
                st.subheader("Risk Metrics")
                
                col1, col2, col3, col4 = st.columns(4)
                
                if "sharpe_actual" in portfolio_metrics:
                    with col1:
                        st.metric(
                            "Sharpe Ratio (Actual)",
                            f"{portfolio_metrics['sharpe_actual']:.2f}"
                        )
                
                if "sharpe_predicted" in portfolio_metrics:
                    with col2:
                        st.metric(
                            "Sharpe Ratio (Predicted)",
                            f"{portfolio_metrics['sharpe_predicted']:.2f}"
                        )
                
                if "volatility_actual" in portfolio_metrics:
                    with col3:
                        st.metric(
                            "Volatility (Actual)",
                            f"{portfolio_metrics['volatility_actual']:.2f}"
                        )
                
                if "volatility_predicted" in portfolio_metrics:
                    with col4:
                        st.metric(
                            "Volatility (Predicted)",
                            f"{portfolio_metrics['volatility_predicted']:.2f}"
                        )


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
            # Extract returns data from the latest portfolio
            returns_data = {}
            for _, row in date_df.iterrows():
                ticker = row["ticker"]
                returns_data[ticker] = row["predicted_return"]
            
            # Create covariance matrix from historical returns
            # For now, use a simplified approach with returns data
            returns_series = pd.Series(returns_data)
            
            if len(returns_series) < 2:
                st.warning("Need at least 2 assets to generate frontier.")
            else:
                # Create simple covariance matrix (identity scaled by variance)
                # This uses the returns as a proxy for risk
                returns_array = returns_series.values
                # Use returns variance as diagonal elements
                cov_matrix = pd.DataFrame(
                    np.diag(np.abs(returns_array) * 0.01 + 0.001),
                    index=returns_series.index,
                    columns=returns_series.index
                )
                # Add small correlations
                for i, idx1 in enumerate(returns_series.index):
                    for j, idx2 in enumerate(returns_series.index):
                        if i < j:
                            cov_matrix.loc[idx1, idx2] = 0.3 * np.sqrt(
                                cov_matrix.loc[idx1, idx1] * cov_matrix.loc[idx2, idx2]
                            )
                            cov_matrix.loc[idx2, idx1] = cov_matrix.loc[idx1, idx2]
                
                # Generate frontier
                num_points = st.slider(
                    "Number of frontier points",
                    min_value=10,
                    max_value=100,
                    value=50,
                    step=10
                )
                
                frontier_result = EfficientFrontier.generate_frontier(
                    returns_series,
                    cov_matrix,
                    num_points=num_points,
                )
                
                # Create and display frontier plot
                st.subheader("Risk vs Return")
                
                # Get current weights if available
                current_weights = {}
                for _, row in date_df.iterrows():
                    current_weights[row["ticker"]] = row["portfolio_weight"]
                
                # Generate Plotly figure manually (since plotly may not be fully available)
                fig = go.Figure()
                
                # Extract frontier data
                volatilities = [p.volatility for p in frontier_result.frontier_points]
                returns_list = [p.expected_return for p in frontier_result.frontier_points]
                sharpe_ratios = [p.sharpe_ratio for p in frontier_result.frontier_points]
                
                # Plot frontier curve
                fig.add_trace(
                    go.Scatter(
                        x=volatilities,
                        y=returns_list,
                        mode="lines",
                        name="Efficient Frontier",
                        line=dict(color="blue", width=2),
                        hovertemplate="<b>Volatility:</b> %{x:.4f}<br>"
                        "<b>Expected Return:</b> %{y:.4f}<br>"
                        "<extra></extra>",
                    )
                )
                
                # Plot frontier points with Sharpe ratio coloring
                fig.add_trace(
                    go.Scatter(
                        x=volatilities,
                        y=returns_list,
                        mode="markers",
                        name="Portfolio Points",
                        marker=dict(
                            size=6,
                            color=sharpe_ratios,
                            colorscale="Viridis",
                            showscale=True,
                            colorbar=dict(title="Sharpe Ratio"),
                        ),
                        hovertemplate="<b>Volatility:</b> %{x:.4f}<br>"
                        "<b>Expected Return:</b> %{y:.4f}<br>"
                        "<b>Sharpe Ratio:</b> %{marker.color:.4f}<br>"
                        "<extra></extra>",
                    )
                )
                
                # Highlight minimum variance portfolio
                min_var = frontier_result.min_variance_portfolio
                fig.add_trace(
                    go.Scatter(
                        x=[min_var.volatility],
                        y=[min_var.expected_return],
                        mode="markers",
                        name="Min Variance Portfolio",
                        marker=dict(size=15, color="red", symbol="star"),
                        hovertemplate="<b>Min Variance Portfolio</b><br>"
                        f"<b>Volatility:</b> {min_var.volatility:.4f}<br>"
                        f"<b>Expected Return:</b> {min_var.expected_return:.4f}<br>"
                        f"<b>Sharpe Ratio:</b> {min_var.sharpe_ratio:.4f}<br>"
                        "<extra></extra>",
                    )
                )
                
                # Highlight maximum Sharpe portfolio
                max_sharpe = frontier_result.max_sharpe_portfolio
                fig.add_trace(
                    go.Scatter(
                        x=[max_sharpe.volatility],
                        y=[max_sharpe.expected_return],
                        mode="markers",
                        name="Max Sharpe Portfolio",
                        marker=dict(size=15, color="gold", symbol="diamond"),
                        hovertemplate="<b>Max Sharpe Portfolio</b><br>"
                        f"<b>Volatility:</b> {max_sharpe.volatility:.4f}<br>"
                        f"<b>Expected Return:</b> {max_sharpe.expected_return:.4f}<br>"
                        f"<b>Sharpe Ratio:</b> {max_sharpe.sharpe_ratio:.4f}<br>"
                        "<extra></extra>",
                    )
                )
                
                # Plot current portfolio if valid
                if len(current_weights) > 0:
                    try:
                        curr_vol, curr_ret, curr_sharpe = EfficientFrontier.calculate_portfolio_metrics(
                            current_weights,
                            returns_series,
                            cov_matrix,
                        )
                        fig.add_trace(
                            go.Scatter(
                                x=[curr_vol],
                                y=[curr_ret],
                                mode="markers",
                                name="Current Portfolio",
                                marker=dict(size=15, color="green", symbol="circle"),
                                hovertemplate="<b>Current Portfolio</b><br>"
                                f"<b>Volatility:</b> {curr_vol:.4f}<br>"
                                f"<b>Expected Return:</b> {curr_ret:.4f}<br>"
                                f"<b>Sharpe Ratio:</b> {curr_sharpe:.4f}<br>"
                                "<extra></extra>",
                            )
                        )
                    except (KeyError, ValueError):
                        pass
                
                # Update layout
                fig.update_layout(
                    title="Efficient Frontier - Risk vs Return",
                    xaxis_title="Portfolio Volatility (Risk)",
                    yaxis_title="Expected Return",
                    hovermode="closest",
                    height=600,
                    template="plotly_white",
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Display portfolio details below frontier
                st.subheader("Portfolio Allocations")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Minimum Variance Portfolio**")
                    st.metric("Volatility", f"{min_var.volatility:.4f}")
                    st.metric("Expected Return", f"{min_var.expected_return:.4f}")
                    st.metric("Sharpe Ratio", f"{min_var.sharpe_ratio:.4f}")
                    
                    st.markdown("**Weights:**")
                    min_var_weights_df = pd.DataFrame(
                        list(min_var.weights.items()),
                        columns=["Ticker", "Weight"]
                    )
                    min_var_weights_df = min_var_weights_df.sort_values("Weight", ascending=False)
                    st.dataframe(
                        min_var_weights_df,
                        hide_index=True,
                        column_config={
                            "Weight": st.column_config.NumberColumn(format="%.2f%%")
                        }
                    )
                
                with col2:
                    st.markdown("**Maximum Sharpe Ratio Portfolio**")
                    st.metric("Volatility", f"{max_sharpe.volatility:.4f}")
                    st.metric("Expected Return", f"{max_sharpe.expected_return:.4f}")
                    st.metric("Sharpe Ratio", f"{max_sharpe.sharpe_ratio:.4f}")
                    
                    st.markdown("**Weights:**")
                    max_sharpe_weights_df = pd.DataFrame(
                        list(max_sharpe.weights.items()),
                        columns=["Ticker", "Weight"]
                    )
                    max_sharpe_weights_df = max_sharpe_weights_df.sort_values("Weight", ascending=False)
                    st.dataframe(
                        max_sharpe_weights_df,
                        hide_index=True,
                        column_config={
                            "Weight": st.column_config.NumberColumn(format="%.2f%%")
                        }
                    )
        
        except Exception as e:
            st.error(f"Error generating frontier: {str(e)}")
            st.info("Ensure portfolio has sufficient data and valid returns.")


def main() -> None:
    run_dashboard()


if __name__ == "__main__":
    main()
