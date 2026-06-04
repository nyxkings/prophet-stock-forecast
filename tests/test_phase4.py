"""Tests for monitoring, alerts, and deployment utilities."""

from __future__ import annotations

import json

import pytest

from src.alerts import (
    AlertChannel,
    AlertConfig,
    AlertManager,
    AlertMessage,
    AlertRule,
    LogAlerter,
)
from src.deployment import DeploymentUtils, HealthChecker, HealthStatus
from src.monitoring import (
    ErrorSeverity,
    JobExecution,
    JobHistoryManager,
    JobLogger,
    JobStatus,
)


class TestJobMonitoring:
    """Test job monitoring system."""

    def test_job_logger_creation(self):
        """Test job logger initialization."""
        logger = JobLogger("job_001", "2024-01-15")

        assert logger.job_id == "job_001"
        assert logger.run_date == "2024-01-15"
        assert logger.status == JobStatus.PENDING

    def test_job_logger_start(self):
        """Test starting job logging."""
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()

        assert logger.status == JobStatus.RUNNING
        assert logger.metrics.start_time is not None

    def test_job_error_recording(self):
        """Test error recording."""
        logger = JobLogger("job_001", "2024-01-15")
        logger.add_error(
            message="Test error",
            error_type="test",
            severity=ErrorSeverity.ERROR,
            ticker="AAPL",
        )

        assert len(logger.metrics.errors) == 1
        assert logger.metrics.errors[0].message == "Test error"
        assert logger.metrics.errors[0].ticker == "AAPL"

    def test_ticker_tracking(self):
        """Test ticker processing tracking."""
        logger = JobLogger("job_001", "2024-01-15")

        logger.record_ticker_processed(success=True)
        logger.record_ticker_processed(success=True)
        logger.record_ticker_processed(success=False)

        assert logger.metrics.tickers_processed == 3
        assert logger.metrics.tickers_succeeded == 2
        assert logger.metrics.tickers_failed == 1

    def test_prediction_recording(self):
        """Test prediction count recording."""
        logger = JobLogger("job_001", "2024-01-15")

        logger.record_prediction(count=5)
        logger.record_prediction(count=3)

        assert logger.metrics.predictions_made == 8

    def test_job_completion(self):
        """Test job completion."""
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        logger.record_ticker_processed(success=True)
        logger.record_prediction(count=1)

        job = logger.finish(success=True)

        assert job.status == JobStatus.SUCCESS
        assert job.metrics.end_time is not None
        assert job.metrics.duration_seconds >= 0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        logger = JobLogger("job_001", "2024-01-15")

        logger.record_ticker_processed(success=True)
        logger.record_ticker_processed(success=True)
        logger.record_ticker_processed(success=False)

        job = logger.finish()

        assert pytest.approx(job.metrics.success_rate(), rel=0.01) == 66.67

    def test_job_execution_serialization(self):
        """Test job execution serialization."""
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        logger.record_ticker_processed(success=True)

        job = logger.finish()
        job_dict = job.to_dict()

        assert job_dict["job_id"] == "job_001"
        assert job_dict["status"] == "success"
        assert "metrics" in job_dict

    def test_job_execution_json(self):
        """Test job execution JSON conversion."""
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        job = logger.finish()

        json_str = job.to_json()
        parsed = json.loads(json_str)

        assert parsed["job_id"] == "job_001"
        assert parsed["status"] == "success"

    def test_job_execution_deserialization(self):
        """Test job execution deserialization."""
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        logger.record_ticker_processed(success=True)
        original_job = logger.finish()

        job_dict = original_job.to_dict()
        restored_job = JobExecution.from_dict(job_dict)

        assert restored_job.job_id == original_job.job_id
        assert restored_job.status == original_job.status


class TestJobHistory:
    """Test job history management."""

    def test_history_manager_creation(self):
        """Test history manager initialization."""
        manager = JobHistoryManager()

        assert manager.max_history_days == 90
        assert len(manager.history) == 0

    def test_add_job(self):
        """Test adding job to history."""
        manager = JobHistoryManager()
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        job = logger.finish()

        manager.add_job(job)

        assert len(manager.history) == 1

    def test_get_job_by_id(self):
        """Test retrieving job by ID."""
        manager = JobHistoryManager()
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        job = logger.finish()

        manager.add_job(job)
        retrieved = manager.get_job_by_id("job_001")

        assert retrieved is not None
        assert retrieved.job_id == "job_001"

    def test_success_rate(self):
        """Test calculating success rate."""
        manager = JobHistoryManager()

        # Add successful job
        logger1 = JobLogger("job_001", "2024-01-15")
        logger1.start()
        logger1.record_ticker_processed(success=True)
        manager.add_job(logger1.finish(success=True))

        # Add failed job
        logger2 = JobLogger("job_002", "2024-01-16")
        logger2.start()
        manager.add_job(logger2.finish(success=False))

        success_rate = manager.get_success_rate(days=7)
        assert pytest.approx(success_rate, rel=0.01) == 50.0

    def test_average_duration(self):
        """Test average job duration calculation."""
        manager = JobHistoryManager()

        for i in range(3):
            logger = JobLogger(f"job_{i}", "2024-01-15")
            logger.start()
            manager.add_job(logger.finish())

        avg_duration = manager.get_average_duration(days=7)
        assert avg_duration >= 0

    def test_to_dataframe(self):
        """Test converting history to DataFrame."""
        manager = JobHistoryManager()
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        logger.record_ticker_processed(success=True)
        manager.add_job(logger.finish())

        df = manager.to_dataframe()
        assert not df.empty
        assert "job_id" in df.columns


class TestAlerts:
    """Test alert system."""

    def test_alert_message_creation(self):
        """Test alert message creation."""
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        job = logger.finish(success=False)

        message = AlertMessage(
            AlertRule.JOB_FAILED,
            job,
            "Test failure",
            ErrorSeverity.CRITICAL,
        )

        assert message.rule == AlertRule.JOB_FAILED
        assert message.severity == ErrorSeverity.CRITICAL

    def test_alert_message_email_format(self):
        """Test alert message email formatting."""
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        logger.add_error("Test error", error_type="test")
        job = logger.finish(success=False)

        message = AlertMessage(
            AlertRule.JOB_FAILED,
            job,
            "Test failure",
            ErrorSeverity.CRITICAL,
        )

        email_body = message.format_email_body()
        assert "JOB_FAILED" in email_body
        assert "job_001" in email_body

    def test_alert_message_slack_format(self):
        """Test alert message Slack formatting."""
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        job = logger.finish()

        message = AlertMessage(
            AlertRule.JOB_FAILED,
            job,
            "Test failure",
            ErrorSeverity.CRITICAL,
        )

        slack_msg = message.format_slack_message()
        assert "attachments" in slack_msg
        assert len(slack_msg["attachments"]) > 0

    def test_log_alerter(self, tmp_path):
        """Test log alerter."""
        log_file = tmp_path / "alerts.log"
        config = AlertConfig(channel=AlertChannel.LOG)
        alerter = LogAlerter(config, str(log_file))

        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        job = logger.finish()

        message = AlertMessage(
            AlertRule.JOB_FAILED,
            job,
            "Test failure",
            ErrorSeverity.ERROR,
        )

        result = alerter.send(message)
        assert result is True
        assert log_file.exists()

    def test_alert_manager(self):
        """Test alert manager."""
        manager = AlertManager()

        # Configure rules
        manager.configure_rule(
            AlertRule.LOW_SUCCESS_RATE,
            {"threshold": 70.0},
        )

        assert AlertRule.LOW_SUCCESS_RATE in manager.rules_config

    def test_alert_manager_check_failed_job(self):
        """Test alert manager detecting failed jobs."""
        manager = AlertManager()
        config = AlertConfig(channel=AlertChannel.LOG)
        alerter = LogAlerter(config, "/tmp/test.log")
        manager.register_alerter(AlertChannel.LOG, alerter)

        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        job = logger.finish(success=False)

        alerts = manager.check_and_alert(job)
        assert len(alerts) > 0
        assert alerts[0].rule == AlertRule.JOB_FAILED


class TestDeployment:
    """Test deployment utilities."""

    def test_systemd_service_generation(self):
        """Test systemd service file generation."""
        content = DeploymentUtils.create_systemd_service(
            "prophet",
            "/opt/prophet/run.py",
        )

        assert "[Unit]" in content
        assert "[Service]" in content
        assert "[Install]" in content
        assert "prophet" in content

    def test_cron_entry_generation(self):
        """Test cron entry generation."""
        entry = DeploymentUtils.create_cron_entry()

        assert "python3" in entry
        assert "*" in entry  # cron schedule contains asterisks

    def test_deployment_checklist(self):
        """Test deployment checklist."""
        checklist = DeploymentUtils.get_deployment_checklist()

        assert len(checklist) > 0
        assert all("item" in item for item in checklist)
        assert all("description" in item for item in checklist)

    def test_health_checker_disk_space(self):
        """Test disk space health check."""
        result = HealthChecker.check_disk_space()

        assert result.name == "disk_space"
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
        assert result.details is not None

    def test_health_checker_memory(self):
        """Test memory health check."""
        result = HealthChecker.check_memory()

        assert result.name == "memory"
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
        assert result.details is not None

    def test_health_checker_cpu(self):
        """Test CPU health check."""
        result = HealthChecker.check_cpu()

        assert result.name == "cpu"
        assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY]
        assert result.details is not None

    def test_health_checker_all_checks(self):
        """Test running all health checks."""
        results = HealthChecker.run_all_checks()

        assert "disk_space" in results
        assert "memory" in results
        assert "cpu" in results
        assert "processes" in results


class TestEdgeCases:
    """Test edge cases."""

    def test_zero_tickers_success_rate(self):
        """Test success rate with no tickers."""
        logger = JobLogger("job_001", "2024-01-15")
        job = logger.finish()

        assert job.metrics.success_rate() == 0.0

    def test_multiple_errors(self):
        """Test multiple error recording."""
        logger = JobLogger("job_001", "2024-01-15")

        for i in range(5):
            logger.add_error(f"Error {i}")

        assert len(logger.metrics.errors) == 5

    def test_partial_job_status(self):
        """Test partial job status (some success, some failure)."""
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        logger.record_ticker_processed(success=True)
        logger.record_ticker_processed(success=False)

        job = logger.finish()

        assert job.status == JobStatus.PARTIAL

    def test_job_execution_to_from_dict(self):
        """Test job serialization round trip."""
        logger = JobLogger("job_001", "2024-01-15")
        logger.start()
        logger.record_ticker_processed(success=True)
        logger.add_error("Test error")
        original = logger.finish()

        # Round trip through dict
        dict_form = original.to_dict()
        restored = JobExecution.from_dict(dict_form)

        assert restored.job_id == original.job_id
        assert restored.status == original.status
        assert len(restored.metrics.errors) == len(original.metrics.errors)
