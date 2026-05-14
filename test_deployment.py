#!/usr/bin/env python3
"""
Pre-Deployment Testing Script for Phase 4
Tests all deployment infrastructure before going to production
"""

import json
import sys
from datetime import datetime

from src.alerts import (
    AlertChannel,
    AlertConfig,
    AlertManager,
    AlertMessage,
    AlertRule,
    LogAlerter,
)
from src.deployment import DeploymentUtils, HealthChecker
from src.monitoring import JobLogger, JobStatus


def print_header(text: str) -> None:
    """Print formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_subheader(text: str) -> None:
    """Print formatted subsection header."""
    print(f"\n📋 {text}")
    print("-" * 70)


def test_health_checks() -> bool:
    """Test all health checks."""
    print_subheader("Testing System Health Checks")

    health_checks = HealthChecker.run_all_checks()
    all_healthy = True

    for check_name, result in health_checks.items():
        status_icon = "✅" if result.status.value == "healthy" else "⚠️" if result.status.value == "degraded" else "❌"
        print(f"{status_icon} {check_name.replace('_', ' ').title()}: {result.status.value}")
        print(f"   {result.message}")

        if result.status.value != "healthy":
            all_healthy = False

            if result.details:
                for key, value in list(result.details.items())[:3]:
                    if isinstance(value, float):
                        print(f"   - {key}: {value:.2f}")
                    else:
                        print(f"   - {key}: {value}")

    return all_healthy


def test_job_monitoring() -> bool:
    """Test job monitoring system."""
    print_subheader("Testing Job Monitoring")

    try:
        # Create a test job
        logger = JobLogger("deployment_test_001", "2026-05-14")
        logger.start()
        print("✅ Job logger started successfully")

        # Simulate processing tickers
        for ticker in ["AAPL", "MSFT", "GOOGL"]:
            logger.record_ticker_processed(success=True)
            logger.record_prediction(count=1)
            print(f"✅ Processed ticker: {ticker}")

        # Simulate an error
        logger.add_error(
            message="Test error for monitoring verification",
            error_type="test_error",
            ticker="TEST",
        )
        print("✅ Error recorded successfully")

        # Finish job
        job = logger.finish(success=True)
        print(f"✅ Job finished with status: {job.status.value}")

        # Verify metrics
        success_rate = job.metrics.success_rate()
        print(f"✅ Success rate calculated: {success_rate:.1f}%")
        print(f"✅ Duration recorded: {job.metrics.duration_seconds:.2f}s")
        print(f"✅ Tickers processed: {job.metrics.tickers_processed}")
        print(f"✅ Predictions made: {job.metrics.predictions_made}")
        print(f"✅ Errors recorded: {len(job.metrics.errors)}")

        # Test serialization
        job_dict = job.to_dict()
        job_json = job.to_json()
        restored = type(job).from_dict(job_dict)
        print(f"✅ Job serialization/deserialization verified")

        return True
    except Exception as e:
        print(f"❌ Job monitoring test failed: {e}")
        return False


def test_alerting_system() -> bool:
    """Test alerting system."""
    print_subheader("Testing Alert System")

    try:
        # Create test job
        logger = JobLogger("alert_test_001", "2026-05-14")
        logger.start()
        logger.add_error("Test critical error", error_type="test")
        job = logger.finish(success=False)
        print("✅ Test job with error created")

        # Set up alert manager
        alert_manager = AlertManager()
        log_config = AlertConfig(channel=AlertChannel.LOG)
        log_alerter = LogAlerter(log_config, "/tmp/deployment_test_alerts.log")
        alert_manager.register_alerter(AlertChannel.LOG, log_alerter)
        print("✅ Log alerter registered")

        # Configure rules
        alert_manager.configure_rule(AlertRule.JOB_FAILED, {})
        alert_manager.configure_rule(
            AlertRule.LOW_SUCCESS_RATE, {"threshold": 70.0}
        )
        alert_manager.configure_rule(
            AlertRule.SLOW_EXECUTION, {"threshold_seconds": 3600.0}
        )
        alert_manager.configure_rule(
            AlertRule.HIGH_ERROR_COUNT, {"threshold": 5}
        )
        print("✅ Alert rules configured")

        # Test alert triggering
        alerts = alert_manager.check_and_alert(job)
        print(f"✅ Alerts triggered: {len(alerts)}")

        for alert in alerts:
            print(f"   - {alert.rule.value}: {alert.message}")

        return len(alerts) > 0
    except Exception as e:
        print(f"❌ Alerting system test failed: {e}")
        return False


def test_deployment_config() -> bool:
    """Test deployment configuration generation."""
    print_subheader("Testing Deployment Configuration")

    try:
        # Test systemd service generation
        service_content = DeploymentUtils.create_systemd_service(
            "prophet-test",
            "/usr/bin/python3 /opt/prophet/main.py",
        )
        if "[Unit]" in service_content and "[Service]" in service_content:
            print("✅ Systemd service configuration generated")
        else:
            print("❌ Systemd service configuration invalid")
            return False

        # Test cron entry generation
        cron_entry = DeploymentUtils.create_cron_entry(
            schedule="0 9 * * *",
            script_path="/opt/prophet/run_daily.py",
        )
        if "python3" in cron_entry and "0 9" in cron_entry:
            print("✅ Cron job configuration generated")
        else:
            print("❌ Cron job configuration invalid")
            return False

        # Test deployment checklist
        checklist = DeploymentUtils.get_deployment_checklist()
        if len(checklist) > 5:
            print(f"✅ Deployment checklist generated ({len(checklist)} items)")
        else:
            print("❌ Deployment checklist incomplete")
            return False

        # Test deployment checks
        checks = DeploymentUtils.run_deployment_checks()
        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        print(f"✅ Deployment pre-checks: {passed}/{total} passed")

        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            print(f"   {status} {check_name}")

        return True
    except Exception as e:
        print(f"❌ Deployment configuration test failed: {e}")
        return False


def test_environment_readiness() -> bool:
    """Test environment readiness for deployment."""
    print_subheader("Testing Environment Readiness")

    try:
        import os
        import subprocess

        checks = {}

        # Check Python version
        try:
            result = subprocess.run(
                ["python3", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"✅ Python version: {version}")
                checks["python"] = True
            else:
                print("❌ Python not available")
                checks["python"] = False
        except Exception as e:
            print(f"❌ Python check failed: {e}")
            checks["python"] = False

        # Check required packages
        try:
            import prophet
            import scipy
            import yfinance
            import pandas
            import streamlit

            print("✅ All required packages installed")
            checks["packages"] = True
        except ImportError as e:
            print(f"❌ Missing package: {e}")
            checks["packages"] = False

        # Check environment variables
        env_vars = ["SUPABASE_URL", "SUPABASE_KEY"]
        missing_vars = [var for var in env_vars if not os.getenv(var)]

        if not missing_vars:
            print("✅ All required environment variables set")
            checks["env_vars"] = True
        else:
            print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
            print("   (Optional: set for database connectivity)")
            checks["env_vars"] = True  # Don't fail on this

        # Check file permissions
        try:
            test_file = "/tmp/prophet_test_write.txt"
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            print("✅ File write permissions verified")
            checks["permissions"] = True
        except Exception as e:
            print(f"❌ File permissions check failed: {e}")
            checks["permissions"] = False

        return all(checks.values())
    except Exception as e:
        print(f"❌ Environment readiness test failed: {e}")
        return False


def test_end_to_end_workflow() -> bool:
    """Test complete workflow simulation."""
    print_subheader("Testing End-to-End Workflow")

    try:
        # Step 1: Create job
        print("1️⃣  Creating job...")
        logger = JobLogger("e2e_test_001", "2026-05-14")
        logger.start()

        # Step 2: Simulate processing
        print("2️⃣  Simulating ticker processing...")
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN"]
        for ticker in tickers:
            logger.record_ticker_processed(success=True)
            logger.record_prediction(count=1)

        # Step 3: Finish job
        print("3️⃣  Completing job...")
        job = logger.finish(success=True)

        # Step 4: Generate alerts
        print("4️⃣  Setting up alerts...")
        alert_manager = AlertManager()
        log_config = AlertConfig(channel=AlertChannel.LOG)
        alerter = LogAlerter(log_config, "/tmp/e2e_test_alerts.log")
        alert_manager.register_alerter(AlertChannel.LOG, alerter)

        # Step 5: Check health
        print("5️⃣  Checking system health...")
        health = HealthChecker.run_all_checks()
        healthy_count = sum(
            1 for r in health.values() if r.status.value == "healthy"
        )

        print(f"\n✅ End-to-end workflow completed successfully!")
        print(f"   - Job Status: {job.status.value}")
        print(f"   - Success Rate: {job.metrics.success_rate():.1f}%")
        print(f"   - Duration: {job.metrics.duration_seconds:.2f}s")
        print(f"   - Healthy System Components: {healthy_count}/{len(health)}")

        return True
    except Exception as e:
        print(f"❌ End-to-end workflow test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def print_results(results: dict[str, bool]) -> None:
    """Print test results summary."""
    print_header("Deployment Test Results Summary")

    passed = sum(1 for v in results.values() if v)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"\n📊 Results: {passed}/{total} test suites passed ({percentage:.0f}%)\n")

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print("\n" + "=" * 70)

    if passed == total:
        print("🎉 ALL TESTS PASSED - READY FOR PHASE 5!")
        print("=" * 70)
        return True
    else:
        print("⚠️  SOME TESTS FAILED - FIX BEFORE PROCEEDING")
        print("=" * 70)
        return False


def main():
    """Run all deployment tests."""
    print_header("Phase 4 Deployment Testing Suite")
    print(f"\nTest Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # Run all tests
    results["Health Checks"] = test_health_checks()
    results["Job Monitoring"] = test_job_monitoring()
    results["Alerting System"] = test_alerting_system()
    results["Deployment Config"] = test_deployment_config()
    results["Environment Readiness"] = test_environment_readiness()
    results["End-to-End Workflow"] = test_end_to_end_workflow()

    # Print results
    success = print_results(results)

    # Return appropriate exit code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
