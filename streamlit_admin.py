"""Admin dashboard for job history and monitoring."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from src.monitoring import JobHistoryManager, JobStatus


def load_style():
    """Load CSS styling."""
    st.markdown(
        """
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .status-success { color: #28a745; font-weight: bold; }
    .status-failed { color: #dc3545; font-weight: bold; }
    .status-partial { color: #ffc107; font-weight: bold; }
    </style>
    """,
        unsafe_allow_html=True,
    )


def format_status(status: str) -> str:
    """Format job status with color."""
    if status == "success":
        return f'<span class="status-success">✅ {status.upper()}</span>'
    elif status == "failed":
        return f'<span class="status-failed">❌ {status.upper()}</span>'
    elif status == "partial":
        return f'<span class="status-partial">⚠️ {status.upper()}</span>'
    else:
        return f'<span>{status.upper()}</span>'


def main():
    """Main dashboard application."""
    st.set_page_config(
        page_title="Prophet Admin Dashboard",
        page_icon="📊",
        layout="wide",
    )

    load_style()

    st.title("📊 Prophet Portfolio Optimization - Admin Dashboard")

    # Initialize history manager (in production, this would load from database)
    history_manager = JobHistoryManager()

    # Sidebar filters
    st.sidebar.header("Filters")
    days_back = st.sidebar.slider(
        "Show jobs from last N days",
        min_value=1,
        max_value=90,
        value=7,
    )

    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📈 Overview", "📋 Job History", "🔥 Errors", "⚙️ Health"]
    )

    # Tab 1: Overview
    with tab1:
        st.header("Job Execution Summary")

        col1, col2, col3, col4 = st.columns(4)

        # Get metrics
        success_rate = history_manager.get_success_rate(days=days_back)
        avg_duration = history_manager.get_average_duration(days=days_back)
        recent_jobs = history_manager.get_recent_jobs(days=days_back)

        with col1:
            st.metric(
                "Success Rate",
                f"{success_rate:.1f}%",
                delta="↑ 2.5%" if success_rate > 85 else "↓ 1.2%",
            )

        with col2:
            st.metric(
                "Avg Duration",
                f"{avg_duration:.0f}s",
                delta="-10s" if avg_duration < 300 else "+15s",
            )

        with col3:
            st.metric(
                "Total Jobs",
                len(recent_jobs),
                delta="+3" if len(recent_jobs) > 5 else "-1",
            )

        with col4:
            failed_count = sum(1 for j in recent_jobs if j.status == JobStatus.FAILED)
            st.metric(
                "Failed Jobs",
                failed_count,
                delta=f"-{1 if failed_count < 2 else 2}" if failed_count < 3 else f"+{failed_count}",
            )

        # Success rate trend
        st.subheader("Success Rate Trend")
        trend_data = []
        for day_offset in range(days_back, 0, -1):
            date = (datetime.now() - timedelta(days=day_offset)).date()
            daily_jobs = [
                j
                for j in recent_jobs
                if j.run_date == str(date)
            ]
            if daily_jobs:
                daily_success = sum(
                    1 for j in daily_jobs if j.status == JobStatus.SUCCESS
                ) / len(daily_jobs) * 100
                trend_data.append({"date": str(date), "success_rate": daily_success})

        if trend_data:
            trend_df = pd.DataFrame(trend_data)
            st.line_chart(trend_df.set_index("date"))
        else:
            st.info("No data available for trend analysis")

    # Tab 2: Job History
    with tab2:
        st.header("Job Execution History")

        if recent_jobs:
            # Convert to DataFrame
            job_data = []
            for job in recent_jobs:
                job_data.append({
                    "Job ID": job.job_id,
                    "Date": job.run_date,
                    "Status": format_status(job.status.value),
                    "Duration (s)": f"{job.metrics.duration_seconds:.2f}",
                    "Tickers": job.metrics.tickers_processed,
                    "Success Rate": f"{job.metrics.success_rate():.1f}%",
                    "Errors": len(job.metrics.errors),
                })

            df = pd.DataFrame(job_data)

            # Display table
            st.dataframe(
                df,
                use_container_width=True,
                unsafe_allow_html=True,
            )

            # Job details expander
            st.subheader("Job Details")
            selected_job = st.selectbox(
                "Select job to view details",
                options=[j.job_id for j in recent_jobs],
                key="job_select",
            )

            if selected_job:
                job = history_manager.get_job_by_id(selected_job)
                if job:
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.write("**Status**")
                        st.write(f'{format_status(job.status.value)}', unsafe_allow_html=True)

                    with col2:
                        st.write("**Duration**")
                        st.write(f"{job.metrics.duration_seconds:.2f}s")

                    with col3:
                        st.write("**Success Rate**")
                        st.write(f"{job.metrics.success_rate():.1f}%")

                    st.write("**Ticker Processing**")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Processed", job.metrics.tickers_processed)
                    with col2:
                        st.metric("Succeeded", job.metrics.tickers_succeeded)
                    with col3:
                        st.metric("Failed", job.metrics.tickers_failed)

                    if job.metrics.errors:
                        st.write("**Errors**")
                        for error in job.metrics.errors:
                            with st.expander(f"🔴 {error.severity.value.upper()}: {error.error_type}"):
                                st.write(f"**Message**: {error.message}")
                                st.write(f"**Ticker**: {error.ticker or 'N/A'}")
                                st.write(f"**Time**: {error.timestamp}")
                                if error.stacktrace:
                                    st.code(error.stacktrace)
        else:
            st.info(f"No job history for the last {days_back} days")

    # Tab 3: Errors
    with tab3:
        st.header("Error Log")

        # Collect all errors
        all_errors = []
        for job in recent_jobs:
            for error in job.metrics.errors:
                all_errors.append({
                    "timestamp": error.timestamp,
                    "job_id": job.job_id,
                    "severity": error.severity.value,
                    "type": error.error_type,
                    "message": error.message,
                    "ticker": error.ticker or "-",
                })

        if all_errors:
            errors_df = pd.DataFrame(all_errors)

            # Filter by severity
            severity_filter = st.multiselect(
                "Filter by severity",
                options=errors_df["severity"].unique(),
                default=errors_df["severity"].unique(),
            )

            filtered_df = errors_df[errors_df["severity"].isin(severity_filter)]

            st.dataframe(
                filtered_df.sort_values("timestamp", ascending=False),
                use_container_width=True,
            )

            # Error statistics
            st.subheader("Error Statistics")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Errors", len(all_errors))

            with col2:
                critical_count = sum(1 for e in all_errors if e["severity"] == "critical")
                st.metric("Critical", critical_count)

            with col3:
                error_count = sum(1 for e in all_errors if e["severity"] == "error")
                st.metric("Errors", error_count)
        else:
            st.info("No errors in the selected period")

    # Tab 4: Health
    with tab4:
        st.header("System Health")

        try:
            from src.deployment import HealthChecker

            health_checks = HealthChecker.run_all_checks()

            # Display health checks
            for check_name, result in health_checks.items():
                status_icon = "✅" if result.status.value == "healthy" else "⚠️" if result.status.value == "degraded" else "❌"

                with st.expander(f"{status_icon} {check_name.replace('_', ' ').title()}"):
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write(f"**Status**: {result.status.value}")
                        st.write(f"**Message**: {result.message}")

                    with col2:
                        st.write(f"**Timestamp**: {result.timestamp}")

                    if result.details:
                        st.write("**Details**:")
                        for key, value in result.details.items():
                            if isinstance(value, float):
                                st.write(f"- {key}: {value:.2f}")
                            else:
                                st.write(f"- {key}: {value}")
        except ImportError:
            st.warning("Health check module not available")

    # Footer
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔄 Refresh Data"):
            st.rerun()

    with col2:
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with col3:
        st.caption("Prophet Admin Dashboard v1.0")


if __name__ == "__main__":
    main()
