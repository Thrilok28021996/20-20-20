"""
Error monitoring and alerting utilities for the EyeHealth 20-20-20 SaaS application.

This module provides comprehensive error monitoring, alerting, and metrics
collection to help maintain system reliability and performance.
"""
import logging
import time
import json
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.db import models
from dataclasses import dataclass, asdict

from .exceptions import BaseApplicationError


logger = logging.getLogger(__name__)


@dataclass
class ErrorMetric:
    """Data class for error metrics."""
    error_code: str
    count: int
    last_occurrence: datetime
    first_occurrence: datetime
    affected_users: int
    severity: str
    contexts: List[Dict[str, Any]]


@dataclass
class PerformanceMetric:
    """Data class for performance metrics."""
    endpoint: str
    method: str
    avg_response_time: float
    max_response_time: float
    min_response_time: float
    request_count: int
    error_rate: float
    timestamp: datetime


class ErrorMonitor:
    """
    Centralized error monitoring and alerting system.

    Tracks error patterns, frequencies, and provides alerting mechanisms
    for critical issues.
    """

    def __init__(self):
        self.error_counts = defaultdict(int)
        self.error_metrics = {}
        self.alert_cooldowns = {}
        self.performance_metrics = defaultdict(list)

    def record_error(
        self,
        error: BaseApplicationError,
        user_id: Optional[int] = None,
        request_path: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record an error occurrence for monitoring and alerting.

        Args:
            error: The application error that occurred
            user_id: ID of the affected user
            request_path: Request path where error occurred
            additional_context: Additional context information
        """
        try:
            error_key = f"{error.error_code}:{error.__class__.__name__}"
            current_time = timezone.now()

            # Update error counts
            self.error_counts[error_key] += 1

            # Update or create error metric
            if error_key not in self.error_metrics:
                self.error_metrics[error_key] = ErrorMetric(
                    error_code=error.error_code,
                    count=1,
                    last_occurrence=current_time,
                    first_occurrence=current_time,
                    affected_users=1 if user_id else 0,
                    severity=self._determine_severity(error),
                    contexts=[]
                )
            else:
                metric = self.error_metrics[error_key]
                metric.count += 1
                metric.last_occurrence = current_time
                if user_id:
                    metric.affected_users += 1

            # Store context information (limited to prevent memory issues)
            context = {
                'timestamp': current_time.isoformat(),
                'user_id': user_id,
                'request_path': request_path,
                'error_context': error.context,
                'additional_context': additional_context
            }

            if len(self.error_metrics[error_key].contexts) < 10:
                self.error_metrics[error_key].contexts.append(context)

            # Cache metrics for external access
            self._cache_error_metrics(error_key, self.error_metrics[error_key])

            # Check for alerting conditions
            self._check_alert_conditions(error, error_key)

            # Log the error event
            self._log_error_event(error, context)

        except Exception as e:
            logger.exception(f"Failed to record error monitoring data: {e}")

    def record_performance_metric(
        self,
        endpoint: str,
        method: str,
        response_time: float,
        status_code: int
    ) -> None:
        """
        Record performance metrics for monitoring.

        Args:
            endpoint: API endpoint or view name
            method: HTTP method
            response_time: Response time in seconds
            status_code: HTTP status code
        """
        try:
            metric_key = f"{method}:{endpoint}"
            current_time = timezone.now()

            # Store performance data (keep last 100 measurements)
            if metric_key not in self.performance_metrics:
                self.performance_metrics[metric_key] = deque(maxlen=100)

            self.performance_metrics[metric_key].append({
                'response_time': response_time,
                'status_code': status_code,
                'timestamp': current_time,
                'is_error': status_code >= 400
            })

            # Cache aggregated metrics
            self._cache_performance_metrics(metric_key)

        except Exception as e:
            logger.exception(f"Failed to record performance metrics: {e}")

    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get error summary for the specified time period.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary containing error summary data
        """
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)

            # Filter recent errors
            recent_errors = {
                key: metric for key, metric in self.error_metrics.items()
                if metric.last_occurrence >= cutoff_time
            }

            # Calculate summary statistics
            total_errors = sum(metric.count for metric in recent_errors.values())
            unique_errors = len(recent_errors)
            critical_errors = sum(
                1 for metric in recent_errors.values()
                if metric.severity == 'critical'
            )

            # Top error types
            top_errors = sorted(
                recent_errors.items(),
                key=lambda x: x[1].count,
                reverse=True
            )[:5]

            return {
                'period_hours': hours,
                'total_errors': total_errors,
                'unique_error_types': unique_errors,
                'critical_errors': critical_errors,
                'top_errors': [
                    {
                        'error_code': metric.error_code,
                        'count': metric.count,
                        'severity': metric.severity,
                        'last_occurrence': metric.last_occurrence.isoformat()
                    }
                    for _, metric in top_errors
                ],
                'generated_at': timezone.now().isoformat()
            }

        except Exception as e:
            logger.exception(f"Failed to generate error summary: {e}")
            return {'error': 'Failed to generate summary'}

    def get_performance_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get performance summary for the specified time period.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary containing performance summary data
        """
        try:
            cutoff_time = timezone.now() - timedelta(hours=hours)
            summary = {}

            for endpoint, metrics in self.performance_metrics.items():
                # Filter recent metrics
                recent_metrics = [
                    m for m in metrics
                    if m['timestamp'] >= cutoff_time
                ]

                if not recent_metrics:
                    continue

                # Calculate statistics
                response_times = [m['response_time'] for m in recent_metrics]
                error_count = sum(1 for m in recent_metrics if m['is_error'])

                summary[endpoint] = {
                    'request_count': len(recent_metrics),
                    'avg_response_time': sum(response_times) / len(response_times),
                    'max_response_time': max(response_times),
                    'min_response_time': min(response_times),
                    'error_rate': (error_count / len(recent_metrics)) * 100,
                    'total_errors': error_count
                }

            return {
                'period_hours': hours,
                'endpoints': summary,
                'generated_at': timezone.now().isoformat()
            }

        except Exception as e:
            logger.exception(f"Failed to generate performance summary: {e}")
            return {'error': 'Failed to generate summary'}

    def _determine_severity(self, error: BaseApplicationError) -> str:
        """Determine error severity level."""
        if error.status_code >= 500:
            return 'critical'
        elif error.status_code >= 400:
            return 'warning'
        else:
            return 'info'

    def _check_alert_conditions(self, error: BaseApplicationError, error_key: str) -> None:
        """Check if alert conditions are met and send alerts if needed."""
        try:
            current_time = timezone.now()
            metric = self.error_metrics[error_key]

            # Check cooldown period
            cooldown_key = f"alert_cooldown:{error_key}"
            if cooldown_key in self.alert_cooldowns:
                last_alert = self.alert_cooldowns[cooldown_key]
                if current_time - last_alert < timedelta(minutes=30):
                    return  # Still in cooldown

            # Alert conditions
            should_alert = False
            alert_reason = ""

            # High frequency alerts
            if metric.count >= 10:  # 10 occurrences
                time_window = timedelta(minutes=5)
                if current_time - metric.first_occurrence <= time_window:
                    should_alert = True
                    alert_reason = f"High frequency: {metric.count} errors in 5 minutes"

            # Critical error alerts
            if metric.severity == 'critical' and metric.count >= 3:
                should_alert = True
                alert_reason = f"Critical error occurred {metric.count} times"

            # Error rate alerts
            if metric.count >= 50:  # High total count
                should_alert = True
                alert_reason = f"High error count: {metric.count} total occurrences"

            if should_alert:
                self._send_alert(error, metric, alert_reason)
                self.alert_cooldowns[cooldown_key] = current_time

        except Exception as e:
            logger.exception(f"Failed to check alert conditions: {e}")

    def _send_alert(self, error: BaseApplicationError, metric: ErrorMetric, reason: str) -> None:
        """Send alert notification for critical errors."""
        try:
            # Email alert to administrators
            if hasattr(settings, 'ADMINS') and settings.ADMINS:
                subject = f"[EyeHealth 20-20-20] Critical Error Alert: {error.error_code}"

                message = f"""
                A critical error condition has been detected in the EyeHealth 20-20-20 application.

                Error Details:
                - Error Code: {error.error_code}
                - Error Type: {error.__class__.__name__}
                - Severity: {metric.severity}
                - Alert Reason: {reason}
                - Total Occurrences: {metric.count}
                - Affected Users: {metric.affected_users}
                - First Occurrence: {metric.first_occurrence}
                - Last Occurrence: {metric.last_occurrence}

                Recent Context:
                {json.dumps(metric.contexts[-3:], indent=2)}

                Please investigate this issue promptly.

                --
                EyeHealth 20-20-20 Monitoring System
                """

                admin_emails = [admin[1] for admin in settings.ADMINS]
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    fail_silently=True
                )

            # Log the alert
            logger.critical(
                f"ALERT SENT: {reason}",
                extra={
                    'error_code': error.error_code,
                    'metric': asdict(metric),
                    'alert_reason': reason
                }
            )

        except Exception as e:
            logger.exception(f"Failed to send alert: {e}")

    def _cache_error_metrics(self, error_key: str, metric: ErrorMetric) -> None:
        """Cache error metrics for external access."""
        try:
            cache_key = f"error_metric:{error_key}"
            cache.set(cache_key, asdict(metric), timeout=3600)  # 1 hour
        except Exception as e:
            logger.warning(f"Failed to cache error metrics: {e}")

    def _cache_performance_metrics(self, metric_key: str) -> None:
        """Cache aggregated performance metrics."""
        try:
            metrics = self.performance_metrics[metric_key]
            if not metrics:
                return

            # Calculate aggregated metrics
            recent_metrics = list(metrics)[-50:]  # Last 50 measurements
            response_times = [m['response_time'] for m in recent_metrics]
            error_count = sum(1 for m in recent_metrics if m['is_error'])

            aggregated = {
                'endpoint': metric_key,
                'request_count': len(recent_metrics),
                'avg_response_time': sum(response_times) / len(response_times),
                'max_response_time': max(response_times),
                'min_response_time': min(response_times),
                'error_rate': (error_count / len(recent_metrics)) * 100,
                'last_updated': timezone.now().isoformat()
            }

            cache_key = f"performance_metric:{metric_key}"
            cache.set(cache_key, aggregated, timeout=300)  # 5 minutes

        except Exception as e:
            logger.warning(f"Failed to cache performance metrics: {e}")

    def _log_error_event(self, error: BaseApplicationError, context: Dict[str, Any]) -> None:
        """Log error event with structured data."""
        logger.error(
            f"Error recorded: {error.error_code}",
            extra={
                'error_code': error.error_code,
                'error_class': error.__class__.__name__,
                'error_message': error.message,
                'user_message': error.user_message,
                'status_code': error.status_code,
                'context': context,
                'monitoring_event': True
            }
        )


class PerformanceMonitor:
    """
    Performance monitoring and metrics collection.
    """

    def __init__(self):
        self.request_times = defaultdict(list)
        self.active_requests = {}

    def start_request_timing(self, request_id: str, endpoint: str, method: str) -> None:
        """Start timing a request."""
        self.active_requests[request_id] = {
            'start_time': time.time(),
            'endpoint': endpoint,
            'method': method
        }

    def end_request_timing(self, request_id: str, status_code: int) -> Optional[float]:
        """End timing a request and record metrics."""
        if request_id not in self.active_requests:
            return None

        request_data = self.active_requests.pop(request_id)
        response_time = time.time() - request_data['start_time']

        # Record performance metric
        error_monitor.record_performance_metric(
            endpoint=request_data['endpoint'],
            method=request_data['method'],
            response_time=response_time,
            status_code=status_code
        )

        return response_time

    def get_slow_requests(self, threshold: float = 1.0) -> List[Dict[str, Any]]:
        """Get requests that exceeded the response time threshold."""
        slow_requests = []

        for endpoint, times in self.request_times.items():
            slow_times = [t for t in times if t['response_time'] > threshold]
            if slow_times:
                slow_requests.append({
                    'endpoint': endpoint,
                    'slow_request_count': len(slow_times),
                    'avg_slow_time': sum(t['response_time'] for t in slow_times) / len(slow_times),
                    'max_slow_time': max(t['response_time'] for t in slow_times)
                })

        return sorted(slow_requests, key=lambda x: x['avg_slow_time'], reverse=True)


class HealthChecker:
    """
    System health monitoring and checks.
    """

    def __init__(self):
        self.checks = {}
        self.last_check_results = {}

    def register_check(self, name: str, check_function: Callable[[], bool], interval: int = 300) -> None:
        """
        Register a health check function.

        Args:
            name: Name of the health check
            check_function: Function that returns True if healthy
            interval: Check interval in seconds
        """
        self.checks[name] = {
            'function': check_function,
            'interval': interval,
            'last_run': None,
            'last_result': None
        }

    def run_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {}
        current_time = timezone.now()

        for name, check_config in self.checks.items():
            # Check if we need to run this check
            if (check_config['last_run'] is None or
                (current_time - check_config['last_run']).total_seconds() >= check_config['interval']):

                try:
                    result = check_config['function']()
                    check_config['last_result'] = result
                    check_config['last_run'] = current_time

                    results[name] = {
                        'status': 'healthy' if result else 'unhealthy',
                        'last_check': current_time.isoformat(),
                        'check_passed': result
                    }

                except Exception as e:
                    logger.exception(f"Health check {name} failed: {e}")
                    results[name] = {
                        'status': 'error',
                        'last_check': current_time.isoformat(),
                        'error': str(e),
                        'check_passed': False
                    }
            else:
                # Return cached result
                results[name] = {
                    'status': 'healthy' if check_config['last_result'] else 'unhealthy',
                    'last_check': check_config['last_run'].isoformat() if check_config['last_run'] else None,
                    'check_passed': check_config['last_result'],
                    'cached': True
                }

        return results

    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        check_results = self.run_checks()

        total_checks = len(check_results)
        passed_checks = sum(1 for result in check_results.values() if result['check_passed'])

        overall_status = 'healthy'
        if passed_checks == 0:
            overall_status = 'critical'
        elif passed_checks < total_checks:
            overall_status = 'degraded'

        return {
            'overall_status': overall_status,
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'failed_checks': total_checks - passed_checks,
            'check_results': check_results,
            'timestamp': timezone.now().isoformat()
        }


# Global instances
error_monitor = ErrorMonitor()
performance_monitor = PerformanceMonitor()
health_checker = HealthChecker()


# Default health checks
def database_health_check() -> bool:
    """Check database connectivity."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            return True
    except Exception:
        return False


def cache_health_check() -> bool:
    """Check cache connectivity."""
    try:
        from django.core.cache import cache
        test_key = "health_check_test"
        cache.set(test_key, "test_value", 30)
        return cache.get(test_key) == "test_value"
    except Exception:
        return False


def disk_space_health_check() -> bool:
    """Check available disk space."""
    try:
        import shutil
        total, used, free = shutil.disk_usage(settings.BASE_DIR)
        free_percentage = (free / total) * 100
        return free_percentage > 10  # At least 10% free space
    except Exception:
        return False


# Register default health checks
health_checker.register_check('database', database_health_check, interval=60)
health_checker.register_check('cache', cache_health_check, interval=60)
health_checker.register_check('disk_space', disk_space_health_check, interval=300)