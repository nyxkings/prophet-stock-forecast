"""Job execution monitoring and logging system."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import pandas as pd


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class ErrorSeverity(str, Enum):
    """Error severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class JobError:
    """Error record for job execution."""

    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    severity: ErrorSeverity = ErrorSeverity.ERROR
    message: str = ""
    error_type: str = ""
    ticker: str | None = None
    stacktrace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "severity": self.severity.value,
            "message": self.message,
            "error_type": self.error_type,
            "ticker": self.ticker,
            "stacktrace": self.stacktrace,
        }


@dataclass
class JobMetrics:
    """Metrics for job execution."""

    start_time: str
    end_time: str | None = None
    duration_seconds: float = 0.0
    tickers_processed: int = 0
    tickers_succeeded: int = 0
    tickers_failed: int = 0
    predictions_made: int = 0
    errors: list[JobError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "tickers_processed": self.tickers_processed,
            "tickers_succeeded": self.tickers_succeeded,
            "tickers_failed": self.tickers_failed,
            "predictions_made": self.predictions_made,
            "errors": [e.to_dict() for e in self.errors],
        }

    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.tickers_processed == 0:
            return 0.0
        return (self.tickers_succeeded / self.tickers_processed) * 100


@dataclass
class JobExecution:
    """Complete job execution record."""

    job_id: str
    run_date: str
    status: JobStatus
    metrics: JobMetrics
    result_summary: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "run_date": self.run_date,
            "status": self.status.value,
            "metrics": self.metrics.to_dict(),
            "result_summary": self.result_summary,
            "created_at": self.created_at,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JobExecution:
        """Create from dictionary."""
        metrics = JobMetrics(
            start_time=data["metrics"]["start_time"],
            end_time=data["metrics"]["end_time"],
            duration_seconds=data["metrics"]["duration_seconds"],
            tickers_processed=data["metrics"]["tickers_processed"],
            tickers_succeeded=data["metrics"]["tickers_succeeded"],
            tickers_failed=data["metrics"]["tickers_failed"],
            predictions_made=data["metrics"]["predictions_made"],
            errors=[
                JobError(
                    timestamp=e["timestamp"],
                    severity=ErrorSeverity(e["severity"]),
                    message=e["message"],
                    error_type=e["error_type"],
                    ticker=e["ticker"],
                    stacktrace=e["stacktrace"],
                )
                for e in data["metrics"]["errors"]
            ],
        )

        return cls(
            job_id=data["job_id"],
            run_date=data["run_date"],
            status=JobStatus(data["status"]),
            metrics=metrics,
            result_summary=data.get("result_summary", {}),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
        )


class JobLogger:
    """Logger for job execution tracking."""

    def __init__(self, job_id: str, run_date: str):
        """Initialize job logger."""
        self.job_id = job_id
        self.run_date = run_date
        self.metrics = JobMetrics(start_time=datetime.now(UTC).isoformat())
        self.status = JobStatus.PENDING

    def start(self) -> None:
        """Mark job as running."""
        self.status = JobStatus.RUNNING
        self.metrics.start_time = datetime.now(UTC).isoformat()

    def add_error(
        self,
        message: str,
        error_type: str = "generic",
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        ticker: str | None = None,
        stacktrace: str | None = None,
    ) -> None:
        """Add error to job log."""
        error = JobError(
            severity=severity,
            message=message,
            error_type=error_type,
            ticker=ticker,
            stacktrace=stacktrace,
        )
        self.metrics.errors.append(error)

    def record_ticker_processed(self, success: bool = True) -> None:
        """Record ticker processing."""
        self.metrics.tickers_processed += 1
        if success:
            self.metrics.tickers_succeeded += 1
        else:
            self.metrics.tickers_failed += 1

    def record_prediction(self, count: int = 1) -> None:
        """Record predictions made."""
        self.metrics.predictions_made += count

    def finish(
        self, success: bool = True, result_summary: dict[str, Any] | None = None
    ) -> JobExecution:
        """Finish job logging."""
        self.metrics.end_time = datetime.now(UTC).isoformat()

        start = datetime.fromisoformat(self.metrics.start_time)
        end = datetime.fromisoformat(self.metrics.end_time)
        self.metrics.duration_seconds = (end - start).total_seconds()

        self.status = JobStatus.SUCCESS if success else JobStatus.FAILED
        if self.metrics.tickers_failed > 0 and self.metrics.tickers_succeeded > 0:
            self.status = JobStatus.PARTIAL

        return JobExecution(
            job_id=self.job_id,
            run_date=self.run_date,
            status=self.status,
            metrics=self.metrics,
            result_summary=result_summary or {},
        )


class JobHistoryManager:
    """Manage job execution history."""

    def __init__(self, max_history_days: int = 90):
        """Initialize history manager."""
        self.max_history_days = max_history_days
        self.history: list[JobExecution] = []

    def add_job(self, job: JobExecution) -> None:
        """Add job to history."""
        self.history.append(job)

    def get_recent_jobs(self, days: int = 7) -> list[JobExecution]:
        """Get jobs from last N days."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        return [job for job in self.history if datetime.fromisoformat(job.created_at) >= cutoff]

    def get_job_by_id(self, job_id: str) -> JobExecution | None:
        """Get specific job by ID."""
        for job in self.history:
            if job.job_id == job_id:
                return job
        return None

    def get_success_rate(self, days: int = 7) -> float:
        """Get success rate for recent jobs."""
        recent_jobs = self.get_recent_jobs(days)
        if not recent_jobs:
            return 0.0

        successful = sum(1 for job in recent_jobs if job.status == JobStatus.SUCCESS)
        return (successful / len(recent_jobs)) * 100

    def get_average_duration(self, days: int = 7) -> float:
        """Get average job duration in seconds."""
        recent_jobs = self.get_recent_jobs(days)
        if not recent_jobs:
            return 0.0

        total_duration = sum(job.metrics.duration_seconds for job in recent_jobs)
        return total_duration / len(recent_jobs)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert history to DataFrame."""
        if not self.history:
            return pd.DataFrame()

        data = [job.to_dict() for job in self.history]
        return pd.json_normalize(data)

    def cleanup_old_records(self) -> int:
        """Remove jobs older than max_history_days."""
        cutoff = datetime.now(UTC) - timedelta(days=self.max_history_days)
        original_len = len(self.history)

        self.history = [
            job for job in self.history if datetime.fromisoformat(job.created_at) >= cutoff
        ]

        return original_len - len(self.history)
