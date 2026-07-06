"""Alert and notification system for job execution."""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from datetime import UTC, datetime
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Protocol

from src.monitoring import ErrorSeverity, JobExecution, JobStatus


class AlertChannel(str, Enum):
    """Alert notification channels."""

    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    LOG = "log"


class AlertRule(Enum):
    """Alert triggering rules."""

    JOB_FAILED = "job_failed"
    JOB_PARTIAL = "job_partial"
    LOW_SUCCESS_RATE = "low_success_rate"
    SLOW_EXECUTION = "slow_execution"
    CRITICAL_ERROR = "critical_error"
    HIGH_ERROR_COUNT = "high_error_count"


@dataclass
class AlertConfig:
    """Alert configuration."""

    channel: AlertChannel
    enabled: bool = True
    min_severity: ErrorSeverity = ErrorSeverity.WARNING

    # Email config
    smtp_host: str | None = None
    smtp_port: int = 587
    sender_email: str | None = None
    sender_password: str | None = None
    recipient_emails: list[str] | None = None

    # Slack config
    webhook_url: str | None = None

    # Thresholds
    low_success_rate_threshold: float = 70.0
    slow_execution_threshold_seconds: float = 3600.0
    high_error_count_threshold: int = 5


class AlertMessage:
    """Alert message to send."""

    def __init__(
        self,
        rule: AlertRule,
        job: JobExecution,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.WARNING,
    ):
        """Initialize alert message."""
        self.rule = rule
        self.job = job
        self.message = message
        self.severity = severity
        self.timestamp = datetime.now(UTC).isoformat()

    def format_email_body(self) -> str:
        """Format message for email."""
        lines = [
            f"Alert: {self.rule.value.upper()}",
            f"Severity: {self.severity.value.upper()}",
            f"Time: {self.timestamp}",
            f"Job ID: {self.job.job_id}",
            f"Run Date: {self.job.run_date}",
            f"Status: {self.job.status.value}",
            "",
            f"Message: {self.message}",
            "",
            "Job Metrics:",
            f"  - Duration: {self.job.metrics.duration_seconds:.2f}s",
            f"  - Tickers Processed: {self.job.metrics.tickers_processed}",
            f"  - Success Rate: {self.job.metrics.success_rate():.1f}%",
            f"  - Errors: {len(self.job.metrics.errors)}",
        ]

        if self.job.metrics.errors:
            lines.append("")
            lines.append("Recent Errors:")
            for error in self.job.metrics.errors[-3:]:
                lines.append(f"  - {error.timestamp}: {error.message}")

        return "\n".join(lines)

    def format_slack_message(self) -> dict[str, Any]:
        """Format message for Slack."""
        color = {
            ErrorSeverity.INFO: "36a64f",
            ErrorSeverity.WARNING: "ffa500",
            ErrorSeverity.ERROR: "ff0000",
            ErrorSeverity.CRITICAL: "8b0000",
        }.get(self.severity, "808080")

        return {
            "attachments": [
                {
                    "color": color,
                    "title": f"{self.rule.value.upper()} - {self.severity.value.upper()}",
                    "text": self.message,
                    "fields": [
                        {
                            "title": "Job ID",
                            "value": self.job.job_id,
                            "short": True,
                        },
                        {
                            "title": "Status",
                            "value": self.job.status.value,
                            "short": True,
                        },
                        {
                            "title": "Duration",
                            "value": f"{self.job.metrics.duration_seconds:.2f}s",
                            "short": True,
                        },
                        {
                            "title": "Success Rate",
                            "value": f"{self.job.metrics.success_rate():.1f}%",
                            "short": True,
                        },
                    ],
                    "ts": int(datetime.fromisoformat(self.timestamp).timestamp()),
                }
            ]
        }


class Alerter(Protocol):
    """Protocol for alert senders."""

    def send(self, message: AlertMessage) -> bool:
        """Send alert message."""
        ...


class EmailAlerter:
    """Send alerts via email."""

    def __init__(self, config: AlertConfig):
        """Initialize email alerter."""
        self.config = config

    def send(self, message: AlertMessage) -> bool:
        """Send alert via email."""
        if not self.config.enabled:
            return False

        if not all(
            [
                self.config.smtp_host,
                self.config.sender_email,
                self.config.sender_password,
                self.config.recipient_emails,
            ]
        ):
            return False

        smtp_host = self.config.smtp_host
        sender_email = self.config.sender_email
        sender_password = self.config.sender_password
        recipient_emails = self.config.recipient_emails
        assert smtp_host and sender_email and sender_password and recipient_emails

        try:
            msg = MIMEText(message.format_email_body())
            msg["Subject"] = f"[{message.severity.value.upper()}] Job Alert: {message.rule.value}"
            msg["From"] = sender_email
            msg["To"] = ", ".join(recipient_emails)

            with smtplib.SMTP(smtp_host, self.config.smtp_port) as server:
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(
                    sender_email,
                    recipient_emails,
                    msg.as_string(),
                )

            return True
        except Exception as e:
            print(f"Failed to send email alert: {e}")
            return False


class SlackAlerter:
    """Send alerts to Slack."""

    def __init__(self, config: AlertConfig):
        """Initialize Slack alerter."""
        self.config = config

    def send(self, message: AlertMessage) -> bool:
        """Send alert to Slack."""
        if not self.config.enabled or not self.config.webhook_url:
            return False

        try:
            import requests

            payload = message.format_slack_message()
            response = requests.post(self.config.webhook_url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to send Slack alert: {e}")
            return False


class LogAlerter:
    """Log alerts to file."""

    def __init__(self, config: AlertConfig, log_file: str = "alerts.log"):
        """Initialize log alerter."""
        self.config = config
        self.log_file = log_file

    def send(self, message: AlertMessage) -> bool:
        """Log alert."""
        if not self.config.enabled:
            return False

        try:
            with open(self.log_file, "a") as f:
                f.write(f"{message.timestamp} | {message.severity.value} | {message.rule.value}\n")
                f.write(f"{message.message}\n")
                f.write("-" * 80 + "\n")
            return True
        except Exception as e:
            print(f"Failed to log alert: {e}")
            return False


class AlertManager:
    """Manage alerts and notifications."""

    def __init__(self):
        """Initialize alert manager."""
        self.alerters: list[tuple[AlertChannel, Alerter]] = []
        self.rules_config: dict[AlertRule, dict[str, Any]] = {}

    def register_alerter(self, channel: AlertChannel, alerter: Alerter) -> None:
        """Register an alerter."""
        self.alerters.append((channel, alerter))

    def configure_rule(self, rule: AlertRule, config: dict[str, Any]) -> None:
        """Configure alert rule."""
        self.rules_config[rule] = config

    def check_and_alert(self, job: JobExecution) -> list[AlertMessage]:
        """Check job against alert rules and send alerts."""
        alerts: list[AlertMessage] = []

        # Job failed
        if job.status == JobStatus.FAILED:
            alert = AlertMessage(
                AlertRule.JOB_FAILED,
                job,
                f"Job {job.job_id} failed on {job.run_date}",
                ErrorSeverity.CRITICAL,
            )
            alerts.append(alert)

        # Job partial
        if job.status == JobStatus.PARTIAL:
            alert = AlertMessage(
                AlertRule.JOB_PARTIAL,
                job,
                f"Job {job.job_id} completed with {job.metrics.tickers_failed} failed tickers",
                ErrorSeverity.ERROR,
            )
            alerts.append(alert)

        # Low success rate
        success_rate = job.metrics.success_rate()
        threshold = self.rules_config.get(AlertRule.LOW_SUCCESS_RATE, {}).get("threshold", 70.0)
        if success_rate < threshold:
            alert = AlertMessage(
                AlertRule.LOW_SUCCESS_RATE,
                job,
                f"Success rate {success_rate:.1f}% is below threshold {threshold}%",
                ErrorSeverity.WARNING,
            )
            alerts.append(alert)

        # Slow execution
        duration_threshold = self.rules_config.get(AlertRule.SLOW_EXECUTION, {}).get(
            "threshold_seconds", 3600.0
        )
        if job.metrics.duration_seconds > duration_threshold:
            alert = AlertMessage(
                AlertRule.SLOW_EXECUTION,
                job,
                f"Job took {job.metrics.duration_seconds:.2f}s (threshold: {duration_threshold}s)",
                ErrorSeverity.WARNING,
            )
            alerts.append(alert)

        # High error count
        error_threshold = self.rules_config.get(AlertRule.HIGH_ERROR_COUNT, {}).get("threshold", 5)
        if len(job.metrics.errors) > error_threshold:
            alert = AlertMessage(
                AlertRule.HIGH_ERROR_COUNT,
                job,
                f"Job has {len(job.metrics.errors)} errors (threshold: {error_threshold})",
                ErrorSeverity.ERROR,
            )
            alerts.append(alert)

        # Critical errors
        critical_errors = [e for e in job.metrics.errors if e.severity == ErrorSeverity.CRITICAL]
        if critical_errors:
            for error in critical_errors:
                alert = AlertMessage(
                    AlertRule.CRITICAL_ERROR,
                    job,
                    f"Critical error: {error.message}",
                    ErrorSeverity.CRITICAL,
                )
                alerts.append(alert)

        # Send alerts
        for alert in alerts:
            self.send_alert(alert)

        return alerts

    def send_alert(self, message: AlertMessage) -> bool:
        """Send alert through all registered alerters."""
        success = False
        for _channel, alerter in self.alerters:
            if alerter.send(message):
                success = True

        return success

    def get_alerter(self, channel: AlertChannel) -> Alerter | None:
        """Get alerter for specific channel."""
        for ch, alerter in self.alerters:
            if ch == channel:
                return alerter
        return None
