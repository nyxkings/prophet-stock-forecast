"""Production deployment and health check utilities."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import psutil


class HealthStatus(str, Enum):
    """Health check status."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str
    timestamp: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "details": self.details or {},
        }


class HealthChecker:
    """Health checks for production system."""

    @staticmethod
    def check_disk_space(warning_threshold: float = 80.0) -> HealthCheckResult:
        """Check disk space usage."""
        try:
            usage = psutil.disk_usage("/")
            percent = usage.percent

            if percent >= 95:
                status = HealthStatus.UNHEALTHY
                message = f"Disk usage critical: {percent:.1f}%"
            elif percent >= warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"Disk usage high: {percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk usage normal: {percent:.1f}%"

            return HealthCheckResult(
                name="disk_space",
                status=status,
                message=message,
                timestamp=datetime.utcnow().isoformat(),
                details={
                    "total_gb": usage.total / (1024**3),
                    "used_gb": usage.used / (1024**3),
                    "free_gb": usage.free / (1024**3),
                    "percent": percent,
                },
            )
        except Exception as e:
            return HealthCheckResult(
                name="disk_space",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check disk space: {e}",
                timestamp=datetime.utcnow().isoformat(),
            )

    @staticmethod
    def check_memory(warning_threshold: float = 80.0) -> HealthCheckResult:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()
            percent = memory.percent

            if percent >= 95:
                status = HealthStatus.UNHEALTHY
                message = f"Memory usage critical: {percent:.1f}%"
            elif percent >= warning_threshold:
                status = HealthStatus.DEGRADED
                message = f"Memory usage high: {percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {percent:.1f}%"

            return HealthCheckResult(
                name="memory",
                status=status,
                message=message,
                timestamp=datetime.utcnow().isoformat(),
                details={
                    "total_gb": memory.total / (1024**3),
                    "used_gb": memory.used / (1024**3),
                    "available_gb": memory.available / (1024**3),
                    "percent": percent,
                },
            )
        except Exception as e:
            return HealthCheckResult(
                name="memory",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check memory: {e}",
                timestamp=datetime.utcnow().isoformat(),
            )

    @staticmethod
    def check_cpu() -> HealthCheckResult:
        """Check CPU usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            load_avg = psutil.getloadavg()

            if cpu_percent >= 90:
                status = HealthStatus.UNHEALTHY
                message = f"CPU usage critical: {cpu_percent:.1f}%"
            elif cpu_percent >= 75:
                status = HealthStatus.DEGRADED
                message = f"CPU usage high: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"CPU usage normal: {cpu_percent:.1f}%"

            return HealthCheckResult(
                name="cpu",
                status=status,
                message=message,
                timestamp=datetime.utcnow().isoformat(),
                details={
                    "percent": cpu_percent,
                    "load_1m": load_avg[0],
                    "load_5m": load_avg[1],
                    "load_15m": load_avg[2],
                },
            )
        except Exception as e:
            return HealthCheckResult(
                name="cpu",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check CPU: {e}",
                timestamp=datetime.utcnow().isoformat(),
            )

    @staticmethod
    def check_process_count() -> HealthCheckResult:
        """Check number of processes."""
        try:
            process_count = len(psutil.pids())

            if process_count > 500:
                status = HealthStatus.DEGRADED
                message = f"High process count: {process_count}"
            else:
                status = HealthStatus.HEALTHY
                message = f"Normal process count: {process_count}"

            return HealthCheckResult(
                name="processes",
                status=status,
                message=message,
                timestamp=datetime.utcnow().isoformat(),
                details={"count": process_count},
            )
        except Exception as e:
            return HealthCheckResult(
                name="processes",
                status=HealthStatus.UNHEALTHY,
                message=f"Failed to check processes: {e}",
                timestamp=datetime.utcnow().isoformat(),
            )

    @staticmethod
    def run_all_checks() -> dict[str, HealthCheckResult]:
        """Run all health checks."""
        return {
            "disk_space": HealthChecker.check_disk_space(),
            "memory": HealthChecker.check_memory(),
            "cpu": HealthChecker.check_cpu(),
            "processes": HealthChecker.check_process_count(),
        }


class DeploymentUtils:
    """Utilities for production deployment."""

    @staticmethod
    def create_systemd_service(
        service_name: str,
        script_path: str,
        user: str = "ubuntu",
        working_dir: str = "/home/ubuntu/prophet",
    ) -> str:
        """Generate systemd service file content."""
        return f"""[Unit]
Description=Prophet Portfolio Optimization Service
After=network.target
StartLimitInterval=0
StartLimitBurst=0

[Service]
Type=simple
Restart=always
RestartSec=10
User={user}
WorkingDirectory={working_dir}
ExecStart=/usr/bin/python3 {script_path}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

    @staticmethod
    def create_cron_entry(
        schedule: str = "0 9 * * *",
        script_path: str = "/home/ubuntu/prophet/run_daily.py",
        log_file: str = "/var/log/prophet/cron.log",
    ) -> str:
        """Generate cron job entry."""
        return f"{schedule} python3 {script_path} >> {log_file} 2>&1"

    @staticmethod
    def get_deployment_checklist() -> list[dict[str, str]]:
        """Get production deployment checklist."""
        return [
            {
                "item": "Environment Variables",
                "description": "SUPABASE_URL and SUPABASE_KEY configured",
                "verification": "echo $SUPABASE_URL",
            },
            {
                "item": "Python Environment",
                "description": "Virtual environment created and activated",
                "verification": "which python && python --version",
            },
            {
                "item": "Dependencies",
                "description": "All packages installed via poetry",
                "verification": "poetry show",
            },
            {
                "item": "Database Connection",
                "description": "Supabase connection verified",
                "verification": "python -c 'from src.database import get_supabase_client; print(get_supabase_client())'",
            },
            {
                "item": "API Keys",
                "description": "All required API keys configured",
                "verification": "Check environment variables",
            },
            {
                "item": "Log Directory",
                "description": "Log directory exists and writable",
                "verification": "mkdir -p /var/log/prophet && touch /var/log/prophet/test.log",
            },
            {
                "item": "Systemd Service",
                "description": "Service file installed at /etc/systemd/system/",
                "verification": "sudo systemctl status prophet-optimization",
            },
            {
                "item": "Cron Jobs",
                "description": "Daily cron job scheduled",
                "verification": "crontab -l",
            },
            {
                "item": "Health Check",
                "description": "System resources monitored",
                "verification": "python -c 'from src.health import HealthChecker; print(HealthChecker.run_all_checks())'",
            },
            {
                "item": "Monitoring",
                "description": "Job execution logs stored",
                "verification": "ls -la /var/log/prophet/",
            },
        ]

    @staticmethod
    def run_deployment_checks() -> dict[str, bool]:
        """Run deployment verification checks."""
        checks = {}

        # Check environment variables
        import os

        checks["env_vars"] = all(
            os.getenv(var) for var in ["SUPABASE_URL", "SUPABASE_KEY"]
        )

        # Check Python version
        try:
            result = subprocess.run(
                ["python3", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            checks["python"] = result.returncode == 0
        except Exception:
            checks["python"] = False

        # Check imports
        try:
            import prophet  # noqa
            import scipy  # noqa
            import yfinance  # noqa

            checks["dependencies"] = True
        except ImportError:
            checks["dependencies"] = False

        # Check database connection
        try:
            from src.database import get_supabase_client

            client = get_supabase_client()
            checks["database"] = client is not None
        except Exception:
            checks["database"] = False

        # Check logs directory
        checks["log_dir"] = False
        try:
            import os

            log_dir = "/var/log/prophet"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            checks["log_dir"] = os.access(log_dir, os.W_OK)
        except Exception:
            pass

        return checks


class RollbackManager:
    """Manage rollback procedures."""

    def __init__(self, backup_dir: str = "/backups/prophet"):
        """Initialize rollback manager."""
        self.backup_dir = backup_dir

    def create_backup(self, source_dir: str, backup_name: str) -> bool:
        """Create backup of deployment."""
        try:
            import shutil

            backup_path = f"{self.backup_dir}/{backup_name}"
            shutil.copytree(source_dir, backup_path)
            return True
        except Exception as e:
            print(f"Backup failed: {e}")
            return False

    def restore_backup(self, backup_name: str, target_dir: str) -> bool:
        """Restore from backup."""
        try:
            import shutil

            backup_path = f"{self.backup_dir}/{backup_name}"
            shutil.rmtree(target_dir)
            shutil.copytree(backup_path, target_dir)
            return True
        except Exception as e:
            print(f"Restore failed: {e}")
            return False

    def list_backups(self) -> list[str]:
        """List available backups."""
        try:
            import os

            if not os.path.exists(self.backup_dir):
                return []
            return sorted(os.listdir(self.backup_dir), reverse=True)
        except Exception:
            return []
